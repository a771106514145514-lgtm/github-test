"""SQLite 資料存取層：住戶/客戶資料的儲存、全文搜尋、匯出用查詢。"""
import os
import sqlite3
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH = os.path.join(DATA_DIR, 'directory.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT '',
    unit TEXT DEFAULT '',
    raw_text TEXT DEFAULT '',
    source_file_name TEXT DEFAULT '',
    source_folder_path TEXT DEFAULT '',
    source_file_id TEXT DEFAULT '',
    file_type TEXT DEFAULT '',
    confidence TEXT DEFAULT 'low',
    needs_review INTEGER DEFAULT 1,
    local_file_path TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    name, phone, address, unit, raw_text,
    content='records', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON records BEGIN
    INSERT INTO records_fts(rowid, name, phone, address, unit, raw_text)
    VALUES (new.id, new.name, new.phone, new.address, new.unit, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, name, phone, address, unit, raw_text)
    VALUES ('delete', old.id, old.name, old.phone, old.address, old.unit, old.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, name, phone, address, unit, raw_text)
    VALUES ('delete', old.id, old.name, old.phone, old.address, old.unit, old.raw_text);
    INSERT INTO records_fts(rowid, name, phone, address, unit, raw_text)
    VALUES (new.id, new.name, new.phone, new.address, new.unit, new.raw_text);
END;

CREATE TABLE IF NOT EXISTS scan_jobs (
    id TEXT PRIMARY KEY,
    folder_id TEXT,
    status TEXT DEFAULT 'running',
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    current_file TEXT DEFAULT '',
    error TEXT DEFAULT '',
    started_at TEXT,
    finished_at TEXT
);
"""


def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


_now = now_iso


def insert_record(rec: dict) -> int:
    conn = get_conn()
    now = _now()
    cur = conn.execute(
        """INSERT INTO records
        (name, phone, address, unit, raw_text, source_file_name, source_folder_path,
         source_file_id, file_type, confidence, needs_review, local_file_path,
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec.get('name', ''), rec.get('phone', ''), rec.get('address', ''),
            rec.get('unit', ''), rec.get('raw_text', ''), rec.get('source_file_name', ''),
            rec.get('source_folder_path', ''), rec.get('source_file_id', ''),
            rec.get('file_type', ''), rec.get('confidence', 'low'),
            1 if rec.get('needs_review', True) else 0,
            rec.get('local_file_path', ''), now, now,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_record(record_id: int, fields: dict) -> None:
    if not fields:
        return
    allowed = {'name', 'phone', 'address', 'unit', 'raw_text', 'confidence', 'needs_review'}
    set_parts = []
    values = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        set_parts.append(f'{key} = ?')
        values.append(value)
    if not set_parts:
        return
    set_parts.append('updated_at = ?')
    values.append(_now())
    values.append(record_id)
    conn = get_conn()
    conn.execute(f"UPDATE records SET {', '.join(set_parts)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_record(record_id: int):
    conn = get_conn()
    row = conn.execute('SELECT * FROM records WHERE id = ?', (record_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_all_records():
    conn = get_conn()
    conn.execute('DELETE FROM records')
    conn.commit()
    conn.close()


def search_records(q: str = '', needs_review=None, page: int = 1, page_size: int = 50):
    conn = get_conn()
    offset = max(page - 1, 0) * page_size
    params = []
    where_extra = ''
    if needs_review is not None:
        where_extra = ' AND r.needs_review = ?'
        params.append(1 if needs_review else 0)

    if q:
        sql = f"""
            SELECT r.* FROM records r
            JOIN records_fts f ON r.id = f.rowid
            WHERE records_fts MATCH ? {where_extra}
            ORDER BY r.name COLLATE NOCASE
            LIMIT ? OFFSET ?
        """
        count_sql = f"""
            SELECT COUNT(*) FROM records r
            JOIN records_fts f ON r.id = f.rowid
            WHERE records_fts MATCH ? {where_extra}
        """
        match_query = _build_fts_query(q)
        rows = conn.execute(sql, [match_query, *params, page_size, offset]).fetchall()
        total = conn.execute(count_sql, [match_query, *params]).fetchone()[0]
    else:
        sql = f"SELECT * FROM records r WHERE 1=1 {where_extra} ORDER BY r.name COLLATE NOCASE LIMIT ? OFFSET ?"
        count_sql = f"SELECT COUNT(*) FROM records r WHERE 1=1 {where_extra}"
        rows = conn.execute(sql, [*params, page_size, offset]).fetchall()
        total = conn.execute(count_sql, params).fetchone()[0]

    conn.close()
    return [dict(row) for row in rows], total


def _build_fts_query(q: str) -> str:
    """把使用者輸入轉成 FTS5 前綴比對查詢，支援部分關鍵字（例如電話後四碼、地址片段）。"""
    tokens = [t for t in q.replace('　', ' ').split() if t]
    if not tokens:
        return '""'
    return ' AND '.join(f'"{t}"*' for t in tokens)


def stats():
    conn = get_conn()
    total = conn.execute('SELECT COUNT(*) FROM records').fetchone()[0]
    needs_review = conn.execute('SELECT COUNT(*) FROM records WHERE needs_review = 1').fetchone()[0]
    conn.close()
    return {'total': total, 'needs_review': needs_review}


# ---- 掃描工作進度（供背景執行緒回報） ----

def create_job(job_id: str, folder_id: str):
    conn = get_conn()
    conn.execute(
        'INSERT INTO scan_jobs (id, folder_id, status, started_at) VALUES (?, ?, ?, ?)',
        (job_id, folder_id, 'running', _now()),
    )
    conn.commit()
    conn.close()


def update_job(job_id: str, **fields):
    if not fields:
        return
    set_parts = [f'{k} = ?' for k in fields]
    values = list(fields.values())
    values.append(job_id)
    conn = get_conn()
    conn.execute(f"UPDATE scan_jobs SET {', '.join(set_parts)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_job(job_id: str):
    conn = get_conn()
    row = conn.execute('SELECT * FROM scan_jobs WHERE id = ?', (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

"""住戶資料整理系統 - Flask 後端。

啟動方式：python app.py，然後用瀏覽器開啟 http://localhost:5000
Google 帳號連接與資料掃描需在網頁介面上手動操作，程式本身不會自動存取任何雲端硬碟資料。
"""
import os
import threading
import uuid

from flask import Flask, request, jsonify, render_template, redirect, send_file, session, abort
from openpyxl import Workbook

import db
import google_drive as gdrive
from extractors.excel_extractor import extract_excel
from extractors.pdf_extractor import extract_pdf
from extractors.image_extractor import extract_image

# 只在本機以 http://localhost 執行 OAuth 流程時需要；正式對外部署請改用 https 並移除這行。
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-please-change')

EXTRACTOR_MAP = {
    '.xlsx': extract_excel,
    '.xls': extract_excel,
    '.pdf': extract_pdf,
    '.jpg': extract_image,
    '.jpeg': extract_image,
    '.png': extract_image,
}

db.init_db()


def _callback_url() -> str:
    return request.url_root.rstrip('/') + '/auth/callback'


# ---------------- 頁面 ----------------

@app.route('/')
def index():
    return render_template('index.html')


# ---------------- Google 帳號連接 ----------------

@app.route('/auth/status')
def auth_status():
    return jsonify({
        'credentials_configured': gdrive.credentials_configured(),
        'connected': gdrive.is_connected(),
    })


@app.route('/auth/login')
def auth_login():
    try:
        flow = gdrive.build_flow(_callback_url())
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 400
    auth_url, state = flow.authorization_url(
        access_type='offline', include_granted_scopes='true', prompt='consent')
    session['oauth_state'] = state
    return redirect(auth_url)


@app.route('/auth/callback')
def auth_callback():
    try:
        flow = gdrive.build_flow(_callback_url())
        flow.fetch_token(authorization_response=request.url)
        gdrive.save_credentials(flow.credentials)
    except Exception as exc:
        return f'連接失敗：{exc}', 400
    return redirect('/')


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    gdrive.disconnect()
    return jsonify({'ok': True})


# ---------------- 資料夾選擇與掃描 ----------------

@app.route('/api/folders')
def api_folders():
    try:
        service = gdrive.get_drive_service()
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'folders': gdrive.list_top_folders(service)})


@app.route('/api/scan', methods=['POST'])
def api_scan():
    if not gdrive.is_connected():
        return jsonify({'error': '尚未連接 Google 帳號'}), 400

    data = request.get_json(force=True) or {}
    folder_input = (data.get('folder') or '').strip()
    if not folder_input:
        return jsonify({'error': '請輸入資料夾連結或資料夾 ID'}), 400

    folder_id = gdrive.parse_folder_id(folder_input)
    job_id = uuid.uuid4().hex[:12]
    db.create_job(job_id, folder_id)

    thread = threading.Thread(target=_run_scan_job, args=(job_id, folder_id), daemon=True)
    thread.start()
    return jsonify({'job_id': job_id})


@app.route('/api/scan/status')
def api_scan_status():
    job_id = request.args.get('job_id', '')
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': '找不到這個掃描工作'}), 404
    return jsonify(job)


def _run_scan_job(job_id: str, folder_id: str):
    try:
        service = gdrive.get_drive_service()
        files = list(gdrive.walk_folder(service, folder_id))
        db.update_job(job_id, total_files=len(files))

        for idx, f in enumerate(files, start=1):
            db.update_job(job_id, processed_files=idx - 1, current_file=f['name'])
            ext = os.path.splitext(f['name'])[1].lower()
            extractor = EXTRACTOR_MAP.get(ext)

            local_path = ''
            try:
                local_path = gdrive.download_file(service, f)
                if not extractor:
                    ext = os.path.splitext(local_path)[1].lower()
                    extractor = EXTRACTOR_MAP.get(ext)
                if not extractor:
                    continue
                extracted = extractor(local_path)
            except Exception as exc:  # 單一檔案失敗不應中斷整個掃描工作
                extracted = [{
                    'name': '', 'phone': '', 'address': '', 'unit': '',
                    'raw_text': f'擷取失敗：{exc}', 'confidence': 'low', 'needs_review': True,
                }]

            file_type = ext.lstrip('.').upper()
            for rec in extracted:
                db.insert_record({
                    **rec,
                    'source_file_name': f['name'],
                    'source_folder_path': f['folder_path'],
                    'source_file_id': f['id'],
                    'file_type': file_type,
                    'local_file_path': local_path,
                })

        db.update_job(job_id, processed_files=len(files), current_file='',
                       status='done', finished_at=db.now_iso())
    except Exception as exc:
        db.update_job(job_id, status='error', error=str(exc))


# ---------------- 搜尋 / 編輯 / 匯出 ----------------

def _parse_needs_review(value):
    if value == 'true':
        return True
    if value == 'false':
        return False
    return None


@app.route('/api/records')
def api_records():
    q = request.args.get('q', '').strip()
    needs_review = _parse_needs_review(request.args.get('needs_review'))
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(int(request.args.get('page_size', 50)), 200)

    records, total = db.search_records(q, needs_review, page, page_size)
    return jsonify({
        'records': records, 'total': total, 'page': page, 'page_size': page_size,
        'stats': db.stats(),
    })


@app.route('/api/records/<int:record_id>')
def api_record_detail(record_id):
    rec = db.get_record(record_id)
    if not rec:
        abort(404)
    return jsonify(rec)


@app.route('/api/records/<int:record_id>', methods=['PUT'])
def api_record_update(record_id):
    rec = db.get_record(record_id)
    if not rec:
        abort(404)
    data = request.get_json(force=True) or {}
    fields = {k: data[k] for k in ('name', 'phone', 'address', 'unit', 'raw_text') if k in data}
    if data.get('mark_reviewed'):
        fields['needs_review'] = 0
        fields['confidence'] = 'high'
    db.update_record(record_id, fields)
    return jsonify(db.get_record(record_id))


@app.route('/api/records/<int:record_id>/file')
def api_record_file(record_id):
    rec = db.get_record(record_id)
    if not rec or not rec.get('local_file_path') or not os.path.exists(rec['local_file_path']):
        abort(404)
    return send_file(rec['local_file_path'])


@app.route('/api/export')
def api_export():
    q = request.args.get('q', '').strip()
    needs_review = _parse_needs_review(request.args.get('needs_review'))
    records, _ = db.search_records(q, needs_review, page=1, page_size=200000)

    wb = Workbook()
    ws = wb.active
    ws.title = '住戶資料'
    ws.append(['姓名', '電話', '地址', '戶號', '信心度', '需複核', '來源檔案', '資料夾路徑', '檔案類型'])
    for rec in records:
        ws.append([
            rec['name'], rec['phone'], rec['address'], rec['unit'],
            rec['confidence'], '是' if rec['needs_review'] else '否',
            rec['source_file_name'], rec['source_folder_path'], rec['file_type'],
        ])

    export_path = os.path.join(db.DATA_DIR, 'export.xlsx')
    os.makedirs(db.DATA_DIR, exist_ok=True)
    wb.save(export_path)
    return send_file(export_path, as_attachment=True, download_name='住戶資料整理.xlsx')


if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)

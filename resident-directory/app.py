"""住戶資料整理系統 - Flask 後端。

啟動方式：python app.py，然後用瀏覽器開啟 http://localhost:5000
Google 帳號連接與資料掃描需在網頁介面上手動操作，程式本身不會自動存取任何雲端硬碟資料。
"""
import os
import threading
import uuid

from flask import Flask, request, jsonify, render_template, redirect, send_file, session, abort
from openpyxl import Workbook
from werkzeug.middleware.proxy_fix import ProxyFix

import db
import google_drive as gdrive
from extractors.excel_extractor import extract_excel
from extractors.pdf_extractor import extract_pdf
from extractors.image_extractor import extract_image

# 只在本機以 http://localhost 執行 OAuth 流程時需要；正式對外部署請改用 https 並移除這行。
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-please-change')
# 部署在 Render 等平台時，實際流量會先經過反向代理；沒有這行，Flask 會誤判成 http，
# 導致產生的 OAuth redirect_uri 跟 Google Cloud 設定的 https 網址對不上。
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# 一旦部署到公開網址，裡面存的是真實住戶個資，絕不能讓任何人都能連進來看。
# 設定 APP_PASSWORD 環境變數後，整個網站（含所有 API）都需要先輸入密碼才能使用。
# 本機用 http://localhost 開發、只有自己看得到時，不設定這個變數也可以照常使用。
APP_PASSWORD = os.environ.get('APP_PASSWORD')
if APP_PASSWORD:
    app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')


@app.before_request
def require_login():
    if not APP_PASSWORD:
        return
    if request.endpoint in ('login', 'static'):
        return
    if session.get('authenticated'):
        return
    if request.path.startswith('/api/') or request.path.startswith('/auth/'):
        return jsonify({'error': '請先登入'}), 401
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') and request.form.get('password') == APP_PASSWORD:
            session['authenticated'] = True
            return redirect('/')
        error = '密碼錯誤，請再試一次'
    return render_template('login.html', error=error)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('authenticated', None)
    return redirect('/login')

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
            inserted_ids = []
            for rec in extracted:
                rec_id = db.insert_record({
                    **rec,
                    'source_file_name': f['name'],
                    'source_folder_path': f['folder_path'],
                    'source_file_id': f['id'],
                    'file_type': file_type,
                    'local_file_path': local_path,
                })
                inserted_ids.append(rec_id)

            # 這個來源檔案裡的每一筆都已經是高信心度、不需要人工複核，
            # 就不用留著原始檔案佔雲端硬碟空間了（雲端部署時尤其重要，磁碟空間有限）。
            # 需複核的資料才保留原始檔，方便使用者在編輯畫面對照校正。
            if local_path and not any(rec.get('needs_review') for rec in extracted):
                try:
                    os.remove(local_path)
                    for rec_id in inserted_ids:
                        db.update_record(rec_id, {'local_file_path': ''})
                except OSError:
                    pass

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

"""Google Drive OAuth 連接與檔案存取。

使用者需自行在 Google Cloud Console 建立 OAuth 用戶端（見 README.md），
下載 credentials.json 放在本專案根目錄，程式才能顯示「連接 Google 帳號」按鈕的完整流程。
"""
import io
import os
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
DOWNLOAD_DIR = os.path.join(DATA_DIR, 'downloads')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(DATA_DIR, 'token.json')

# 唯讀權限即可，程式不會修改或刪除您雲端硬碟裡的任何檔案
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

FOLDER_MIME = 'application/vnd.google-apps.folder'

# Google 原生文件需要先匯出成一般格式才能下載
EXPORT_MAP = {
    'application/vnd.google-apps.spreadsheet': (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
    'application/vnd.google-apps.document': ('application/pdf', '.pdf'),
}

SUPPORTED_EXTENSIONS = {'.xlsx', '.xls', '.pdf', '.jpg', '.jpeg', '.png'}


def credentials_configured() -> bool:
    return os.path.exists(CREDENTIALS_PATH)


def build_flow(redirect_uri: str) -> Flow:
    if not credentials_configured():
        raise RuntimeError(
            '找不到 credentials.json，請先依 README.md 的步驟在 Google Cloud Console 建立 '
            'OAuth 用戶端並下載憑證檔案，放到 resident-directory/credentials.json'
        )
    return Flow.from_client_secrets_file(CREDENTIALS_PATH, scopes=SCOPES, redirect_uri=redirect_uri)


def save_credentials(creds: Credentials) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOKEN_PATH, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())


def load_credentials():
    if not os.path.exists(TOKEN_PATH):
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    return creds


def is_connected() -> bool:
    creds = load_credentials()
    return bool(creds and creds.valid)


def disconnect() -> None:
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)


def get_drive_service():
    creds = load_credentials()
    if not creds:
        raise RuntimeError('尚未連接 Google 帳號，請先點擊「連接 Google 帳號」')
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def parse_folder_id(folder_id_or_url: str) -> str:
    """接受使用者貼上的資料夾連結或直接輸入的資料夾 ID。"""
    value = folder_id_or_url.strip()
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', value)
    if match:
        return match.group(1)
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', value)
    if match:
        return match.group(1)
    return value


def list_top_folders(service) -> list:
    resp = service.files().list(
        q=f"mimeType='{FOLDER_MIME}' and trashed = false and 'root' in parents",
        fields='files(id, name)', pageSize=100, orderBy='name',
    ).execute()
    return resp.get('files', [])


def get_file_meta(service, file_id: str) -> dict:
    return service.files().get(fileId=file_id, fields='id, name, mimeType').execute()


def walk_folder(service, folder_id: str, path: str = ''):
    """遞迴走訪資料夾，yield 出所有支援格式的檔案 metadata（含相對路徑）。"""
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields='nextPageToken, files(id, name, mimeType, modifiedTime)',
            pageToken=page_token, pageSize=200,
        ).execute()
        for f in resp.get('files', []):
            if f['mimeType'] == FOLDER_MIME:
                yield from walk_folder(service, f['id'], f"{path}/{f['name']}")
            else:
                ext = os.path.splitext(f['name'])[1].lower()
                is_supported = ext in SUPPORTED_EXTENSIONS or f['mimeType'] in EXPORT_MAP
                if is_supported:
                    yield {**f, 'folder_path': path or '/'}
        page_token = resp.get('nextPageToken')
        if not page_token:
            break


def download_file(service, file_meta: dict) -> str:
    """下載（或匯出）單一檔案到本機快取資料夾，回傳本機路徑。"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_id = file_meta['id']
    mime_type = file_meta['mimeType']
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', file_meta['name'])
    dest_path = os.path.join(DOWNLOAD_DIR, f'{file_id}_{safe_name}')

    if mime_type in EXPORT_MAP:
        export_mime, ext = EXPORT_MAP[mime_type]
        if not dest_path.lower().endswith(ext):
            dest_path += ext
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    else:
        request = service.files().get_media(fileId=file_id)

    fh = io.FileIO(dest_path, 'wb')
    try:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    finally:
        fh.close()
    return dest_path

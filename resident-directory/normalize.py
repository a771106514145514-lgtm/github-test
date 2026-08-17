"""從擷取出的原始文字中，用關鍵字錨定 + 常見台灣格式的規則，拆出姓名/電話/地址/戶號欄位。

這是啟發式（heuristic）的規則比對，無法保證 100% 正確，特別是手寫或版面複雜的掃描件。
因此每筆資料都會附上信心度（confidence），信心不足的會標記 needs_review，
讓使用者在網頁介面上對照原始檔案手動校正。
"""
import re

PHONE_RE = re.compile(r'0\d{1,3}[-\s]?\d{3,4}[-\s]?\d{3,4}')

ADDRESS_RE = re.compile(
    r'([一-龥]{2,4}[縣市])?'
    r'[一-龥]{1,6}[鄉鎮市區]?'
    r'[一-龥0-9]{1,10}[路街道大道]'
    r'[一二三四五六七八九十0-9]{0,3}[段]?'
    r'[0-9]{0,4}[巷]?[0-9]{0,4}[弄]?'
    r'[0-9]{1,4}號'
    r'(之[0-9]{1,3})?'
    r'([0-9]{1,3}樓)?'
)

UNIT_RE = re.compile(r'(地下)?[0-9A-Za-z]{1,4}\s?[樓層](?:之[0-9]{1,3})?|[0-9]{1,3}[FB]\d{0,3}')

NAME_KEYWORDS = ['姓名', '戶長', '住戶', '承租人', '負責人', '聯絡人']
PHONE_KEYWORDS = ['電話', '手機', '聯絡電話', '市話', 'Tel', 'TEL']
ADDRESS_KEYWORDS = ['地址', '住址', '通訊地址', '戶籍地址']
UNIT_KEYWORDS = ['戶號', '樓層', '房號', '門牌', '單位']

NAME_ANCHOR_RE = re.compile(
    r'(?:' + '|'.join(NAME_KEYWORDS) + r')[:：]?\s*([一-龥]{2,5})'
)


def _find_by_keyword(text: str, keywords: list, value_re=None):
    for kw in keywords:
        idx = text.find(kw)
        if idx == -1:
            continue
        window = text[idx: idx + 40]
        if value_re:
            match = value_re.search(window)
            if match:
                return match.group(0).strip()
        else:
            after = window[len(kw):].lstrip(':： \t')
            if after:
                return after.split('\n')[0].strip()[:30]
    return None


def extract_fields_from_text(text: str) -> dict:
    text = text or ''

    name = _find_by_keyword(text, NAME_KEYWORDS)
    if not name:
        m = NAME_ANCHOR_RE.search(text)
        if m:
            name = m.group(1)

    phone = _find_by_keyword(text, PHONE_KEYWORDS, PHONE_RE)
    if not phone:
        m = PHONE_RE.search(text)
        if m:
            phone = m.group(0)

    address = _find_by_keyword(text, ADDRESS_KEYWORDS, ADDRESS_RE)
    if not address:
        m = ADDRESS_RE.search(text)
        if m:
            address = m.group(0)

    unit = _find_by_keyword(text, UNIT_KEYWORDS, UNIT_RE)
    if not unit:
        m = UNIT_RE.search(text)
        if m:
            unit = m.group(0)

    found_count = sum(1 for v in (name, phone, address, unit) if v)
    if found_count >= 3:
        confidence = 'high'
    elif found_count >= 1:
        confidence = 'medium'
    else:
        confidence = 'low'

    return {
        'name': (name or '').strip(),
        'phone': (phone or '').strip(),
        'address': (address or '').strip(),
        'unit': (unit or '').strip(),
        'confidence': confidence,
        'needs_review': confidence != 'high',
    }


# Excel 欄位標題比對用的關鍵字（依欄位名稱直接對應，比純文字規則準確許多）
EXCEL_HEADER_MAP = {
    'name': ['姓名', '名字', '戶長', '承租人', '負責人', '客戶姓名'],
    'phone': ['電話', '手機', '聯絡電話', '市話', 'phone', 'tel'],
    'address': ['地址', '住址', '通訊地址', '戶籍地址'],
    'unit': ['戶號', '樓層', '房號', '門牌', '單位', '戶別'],
}


def match_excel_header(header: str):
    if not header:
        return None
    header_norm = str(header).strip().lower()
    for field, keywords in EXCEL_HEADER_MAP.items():
        for kw in keywords:
            if kw.lower() in header_norm:
                return field
    return None

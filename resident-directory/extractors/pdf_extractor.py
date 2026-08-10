"""PDF 擷取器：一般文字型 PDF 直接抽文字層；掃描版（無文字層）自動改用 OCR。"""
import fitz  # PyMuPDF
from PIL import Image
import io

import pytesseract

from normalize import extract_fields_from_text

# 一頁若抽出的文字層少於這個字數，視為掃描件，改走 OCR
MIN_TEXT_LEN_FOR_NATIVE = 20
OCR_DPI = 300


def _ocr_page(page) -> str:
    pix = page.get_pixmap(dpi=OCR_DPI)
    img = Image.open(io.BytesIO(pix.tobytes('png')))
    return pytesseract.image_to_string(img, lang='chi_tra+eng')


def extract_pdf(file_path: str) -> list:
    records = []
    doc = fitz.open(file_path)

    for page_idx, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        used_ocr = False
        if len(text) < MIN_TEXT_LEN_FOR_NATIVE:
            text = _ocr_page(page).strip()
            used_ocr = True

        if not text:
            continue

        fields = extract_fields_from_text(text)
        if used_ocr and fields['confidence'] == 'high':
            fields['confidence'] = 'medium'
            fields['needs_review'] = True

        records.append({
            **fields,
            'raw_text': text,
            'page': page_idx,
            'used_ocr': used_ocr,
        })

    doc.close()
    return records

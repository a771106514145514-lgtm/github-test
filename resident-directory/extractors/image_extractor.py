"""圖片（JPG/PNG）擷取器：OCR 辨識繁體中文文字後，交給共用的欄位擷取規則。"""
from PIL import Image
import pytesseract

from normalize import extract_fields_from_text


def extract_image(file_path: str) -> list:
    image = Image.open(file_path)
    text = pytesseract.image_to_string(image, lang='chi_tra+eng').strip()

    if not text:
        return [{
            'name': '', 'phone': '', 'address': '', 'unit': '',
            'raw_text': '', 'confidence': 'low', 'needs_review': True,
        }]

    fields = extract_fields_from_text(text)
    # 圖片 OCR 品質變化很大（光線、手寫、歪斜），即使規則命中也降一級信心度，交由人工確認
    if fields['confidence'] == 'high':
        fields['confidence'] = 'medium'
        fields['needs_review'] = True

    return [{**fields, 'raw_text': text}]

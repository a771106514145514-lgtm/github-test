# 住戶資料整理系統

把 Google 雲端硬碟裡分散的住戶／客戶資料（Excel、PDF、掃描圖片）自動整理成統一格式，並提供快速搜尋、匯出 Excel 的功能。

- 圖片與掃描版 PDF 會自動用 OCR 辨識文字
- 姓名、電話、地址、戶號會依規則自動拆欄位；辨識信心不足的資料會標記「需複核」，可在網頁上對照原始檔案手動修正
- 所有資料只存在您自己的電腦（SQLite 資料庫），**不會**上傳或公開分享
- Google 帳號連接與資料掃描完全由您在網頁上手動觸發，程式不會自動存取雲端硬碟

---

## 一、事前準備

### 1. 安裝 Python 套件

```bash
cd resident-directory
python -m venv venv
source venv/bin/activate   # Windows 請用 venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 安裝 Tesseract OCR（圖片/掃描件文字辨識需要）

- **Mac**：`brew install tesseract tesseract-lang`
- **Ubuntu/Debian**：`sudo apt-get install tesseract-ocr tesseract-ocr-chi-tra`
- **Windows**：到 [Tesseract 官方安裝檔](https://github.com/UB-Mannheim/tesseract/wiki) 下載安裝，安裝時記得勾選「Chinese (Traditional)」語言包，並將安裝路徑加入系統 PATH

安裝完成後可執行 `tesseract --list-langs` 確認清單中有 `chi_tra`。

### 3. 建立 Google OAuth 憑證（讓「連接 Google 帳號」按鈕能運作）

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)，建立一個新專案（或使用現有專案）
2. 左側選單「API 和服務」→「已啟用的 API 和服務」→ 啟用 **Google Drive API**
3. 左側選單「API 和服務」→「OAuth 同意畫面」：
   - 使用者類型選「外部」
   - 填寫應用程式名稱（例如「住戶資料整理系統」）與您的 Email
   - 在「測試使用者」新增您自己的 Google 帳號 Email（未通過 Google 審核前，只有測試使用者能登入）
4. 左側選單「API 和服務」→「憑證」→「建立憑證」→「OAuth 用戶端 ID」：
   - 應用程式類型選「網頁應用程式」
   - 「已授權的重新導向 URI」填入：`http://localhost:5000/auth/callback`
   - 建立後下載憑證 JSON 檔
5. 將下載的檔案改名為 `credentials.json`，放到 `resident-directory/credentials.json`（此檔案已加入 `.gitignore`，不會被提交到 Git）

---

## 二、啟動程式

```bash
cd resident-directory
source venv/bin/activate
python app.py
```

用瀏覽器開啟 **http://localhost:5000**（請務必用 `localhost` 而非 `127.0.0.1`，才會與上面設定的重新導向 URI 一致）。

---

## 三、使用流程

1. **連接 Google 帳號**：點擊按鈕，會跳轉到 Google 登入／授權畫面，同意後會自動導回本頁面。權限僅為「唯讀」，程式不會修改或刪除您雲端硬碟裡的任何檔案。
2. **選擇資料夾**：把要整理的 Google 雲端硬碟資料夾連結貼到輸入框（例如 `https://drive.google.com/drive/folders/xxxxxxxx`），點擊「開始掃描與整理」。程式會遞迴掃描該資料夾與所有子資料夾內的 Excel、PDF、圖片檔案。
3. **等待處理完成**：畫面會顯示即時進度（幾/幾個檔案）。檔案數量多、圖片/掃描 PDF 多時，OCR 會需要較長時間，請耐心等候，不要關閉分頁。
4. **搜尋資料**：在搜尋框輸入姓名、電話、地址或戶號的關鍵字（支援部分關鍵字，例如電話後幾碼）。
5. **複核需確認的資料**：勾選「只顯示需複核」可篩選出信心度不足的資料，點擊「編輯」可對照原始檔案（圖片會直接預覽）手動修正欄位，確認無誤後勾選「標記為已確認」再儲存。
6. **匯出 Excel**：點擊「匯出 Excel」，會依目前的搜尋/篩選條件匯出一份 `.xlsx` 檔案。

---

## 四、資料存放位置

- 資料庫：`resident-directory/data/directory.db`（SQLite，可用任何 SQLite 工具開啟）
- 下載的原始檔案快取：`resident-directory/data/downloads/`
- Google 帳號登入憑證：`resident-directory/data/token.json`

想要重新整理某個資料夾、避免資料重複，建議在重新掃描前先刪除 `data/directory.db` 與 `data/downloads/`（或另外備份保留）。

---

## 五、已知限制

- 姓名/電話/地址/戶號的擷取是用規則比對，無法保證 100% 正確，尤其是手寫或版面複雜的表單，因此設計了「需複核」機制，請務必人工檢查標記為「中」「低」信心度的資料。
- 目前支援的檔案格式：`.xlsx` `.xls` `.pdf` `.jpg` `.jpeg` `.png`，以及 Google 試算表／文件（會自動匯出成 Excel/PDF 再處理）。
- 大量檔案（數千個以上）建議分批、分資料夾掃描，避免單次執行時間過長。

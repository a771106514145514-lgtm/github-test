# 住戶資料整理系統

把 Google 雲端硬碟裡分散的住戶／客戶資料（Excel、PDF、掃描圖片）自動整理成統一格式，並提供快速搜尋、匯出 Excel 的功能。

- 圖片與掃描版 PDF 會自動用 OCR 辨識文字
- 姓名、電話、地址、戶號會依規則自動拆欄位；辨識信心不足的資料會標記「需複核」，可在網頁上對照原始檔案手動修正
- Google 帳號連接與資料掃描完全由您在網頁上手動觸發，程式不會自動存取雲端硬碟

有兩種執行方式，請依需求選一種：

| 方式 | 適合情境 | 章節 |
|---|---|---|
| **本機執行** | 只有自己的電腦要用，不需要手機/其他裝置連線 | 一、二 |
| **雲端部署** | 電腦、手機（不管在不在同一個 Wi-Fi）都要能連到同一個網址 | 六 |

---

## 一、事前準備（本機執行適用）

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
   - 「已授權的重新導向 URI」先填入：`http://localhost:5000/auth/callback`
     （如果之後要照第六章雲端部署，記得再回來這裡多加一筆雲端網址，見第六章說明）
   - 建立後下載憑證 JSON 檔
5. 將下載的檔案改名為 `credentials.json`，放到 `resident-directory/credentials.json`（此檔案已加入 `.gitignore`，不會被提交到 Git）
6. （建議）回到「OAuth 同意畫面」，點擊「發布應用程式」改成「正式版」。停留在「測試中」狀態時，Google
   核發的登入憑證每 7 天就會失效，要重新點一次「連接 Google 帳號」；改成正式版就不會有這個限制
   （因為只有您自己使用，不需要等 Google 審核，畫面上出現「未驗證」的警告可以放心略過）。

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

---

## 六、雲端部署（電腦、手機都能連到同一個網址）

本機執行時，程式只有您自己的電腦連得到；如果想要手機（不管在不在家裡 Wi-Fi）也能開啟同一份資料，
就需要把程式部署到一台隨時開著、有公開網址的雲端主機。以下用 [Render](https://render.com) 示範
（免費方案沒有永久磁碟，重新啟動會遺失資料，因此住戶資料庫這種需要長期保存的用途建議選付費方案）。

> **費用提醒**：Render 最便宜的付費方案（Starter）約 US$7/月，加上 1GB 永久磁碟約 US$0.25/月，
> 合計每月大約 7～8 美元。若不想付費，也可以改用其他支援 Docker + 永久磁碟的平台（例如 Railway、
> Fly.io、自租 VPS），部署方式大同小異，重點是要有「永久磁碟」才不會每次重啟就把資料庫洗掉。

### 1. 這個專案已經準備好部署所需的檔案

- `Dockerfile`：內含 Tesseract OCR，**部署後就不需要在手機或電腦上另外安裝 Python/Tesseract**，
  只要用瀏覽器打開網址即可，比本機執行更省事。
- `render.yaml`：Render 的一鍵部署設定檔，已設定好永久磁碟掛載在 `/app/data`。

### 2. 部署步驟

1. 把這個 GitHub 專案 fork 或直接連結到您自己的 Render 帳號：登入 [Render](https://dashboard.render.com/)
   →「New」→「Blueprint」→ 選擇這個 GitHub repository → Render 會自動讀取 `render.yaml`。
2. 部署設定畫面會要求輸入 `APP_PASSWORD`（見下方「安全性」說明），自訂一組密碼即可，`SECRET_KEY`
   會自動產生不用管。
3. 點擊「Apply」開始部署，第一次建置（要安裝 Tesseract）大約需要幾分鐘。
4. 部署完成後，Render 會給您一個網址，例如 `https://resident-directory-xxxx.onrender.com`。

### 3. 更新 Google OAuth 設定

回到 Google Cloud Console 的 OAuth 用戶端設定（第一章第 3 步建立的那個），在「已授權的重新導向 URI」
再新增一筆：

```
https://resident-directory-xxxx.onrender.com/auth/callback
```

（換成您實際拿到的網址）儲存即可。

### 4. 上傳 credentials.json（不會進 Git，用 Render 的 Secret File 功能）

Render 的服務頁面 →「Environment」→「Secret Files」→ 新增一個檔案，檔名填 `credentials.json`，
內容貼上您下載的憑證 JSON 全文，路徑保持預設（會自動放在專案根目錄，也就是程式讀取的位置）。存檔後
服務會自動重新部署。

### 5. 開始使用

用電腦或手機瀏覽器打開 Render 給的網址，先輸入您在步驟 2 設定的 `APP_PASSWORD` 登入，
之後操作方式跟本機執行完全一樣（連接 Google 帳號、貼資料夾連結、掃描、搜尋、複核、匯出）。
不管在公司、在家、用行動網路，登入同一個網址看到的都是同一份資料。

### 安全性：為什麼一定要設定 APP_PASSWORD

本機執行時，因為只有您的電腦連得到 `localhost`，天生就沒有陌生人能存取的問題。但只要部署到公開網址，
任何知道這個網址的人都能打開網頁——而這裡面存的是真實住戶的姓名、電話、地址。因此程式加了一層密碼保護
（`APP_PASSWORD` 環境變數）：**沒有設定這個變數時完全不會擋（適合本機使用）；只要有設定，整個網站
（包含所有搜尋/匯出功能）都必須先輸入密碼才能使用**。部署到雲端時請務必設定，且不要把網址和密碼一起
分享出去。

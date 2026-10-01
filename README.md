# 小黑工具箱

**離線多功能工具箱** — 打開就用，用完就關。工具在本機處理檔案，不會上傳圖片或文字。

## 功能一覽

| 工具 | 說明 | 技術 |
|------|------|------|
| AI 智慧去背 | 一鍵去除圖片背景，精準度媲美線上服務 | BiRefNet 深度學習模型 |
| PNG 轉 ICO | 上傳 PNG，自動產生 16~256px 全尺寸圖示檔 | Pillow |
| 文字轉檔工坊 | Markdown / HTML / CSV / JSON / YAML / XML / TSV 互轉，支援匯出 PDF | 純前端 JavaScript |
| QR Code 產生與辨識 | 產生 QR、自訂顏色尺寸；拖入圖片或貼上截圖讀取同圖多個 QR | qrcode.js + OpenCV |
| OCR 文字辨識 | 上傳圖片或 Ctrl+V 貼上截圖；支援繁中、簡中、日、韓及英文 | EasyOCR |
| 圖片批次處理 | 壓縮、縮圖、PNG / JPG / WebP 互轉、EXIF 管理；比較結果並下載 ZIP | Pillow + JSZip |
| PDF 工具 | 縮圖預覽、合併、抽頁、拖曳排序、旋轉、逐頁拆分；支援密碼開啟 | pypdf + PDF.js |
| 圖片標註 | 貼上截圖、箭頭、框選、畫筆、文字、馬賽克、實色遮蔽、裁切；復原／重做與 PNG/JPG/WebP 匯出 | Canvas |
| 批次檔案改名 | 新舊檔名預覽、流水號、文字取代、前後綴與日期；直接改名、持久復原與中斷恢復 | 本機檔案系統 |

QR Code 頁面同時支援圖片辨識：拖入 PNG / JPG / WebP 或 Ctrl+V 貼上截圖，可讀取同圖多個 QR 並複製內容。

## 特色

- **工具離線可用** — 零 CDN 依賴，發行包包含 AI 模型；啟動時的 GitHub 版本檢查需要網路，但失敗不影響工具
- **隱私安全** — 檔案只在你的電腦上處理，不會上傳到任何地方
- **自動更新** — 透過 GitHub Releases 檢查新版本，支援差量更新
- **一鍵啟動** — 雙擊 exe 自動開啟瀏覽器
- **快速找到工具** — 9 個工具依用途分類，支援關鍵字搜尋、收藏、最近使用；任意頁面按 `Ctrl+K` 搜尋
- **常用設定記憶** — 記住圖片、PDF 輸出方式、OCR 語言、QR 尺寸／顏色與文字格式；不儲存圖片或文件內容

## 使用方式

### 直接使用（已打包 exe）

1. 從 [Releases](https://github.com/littleblackmann/littleblacktoolbox/releases) 下載最新版 ZIP
2. 解壓縮後雙擊 `小黑工具箱.exe`
3. 瀏覽器會自動開啟 `http://127.0.0.1:5000`

圖片上傳上限為 50 MB、3000 萬像素。OCR 一次可選一種繁中／簡中／日／韓語言，並可搭配英文。

### 圖片批次處理

最多選擇 50 張、合計 50 MB 的靜態圖片。設定最大寬高後保持比例縮小，不放大小圖；填 0 表示不限制。JPG / WebP 可調整品質，PNG 使用無損壓縮。透明 PNG / WebP 保留透明；轉成 JPG 時使用所選背景色。預設移除拍攝資訊，勾選可保留 EXIF 與 ICC；拍攝方向會自動校正。

結果會顯示尺寸與處理前後大小。重新編碼不保證體積更小，請比較後下載；ZIP 中的重複檔名會自動加上序號。

可套用「分享圖片」或「去背 → 縮圖 → WebP」流程，也可為設定命名，保留最多 10 組自訂流程。批次顯示進度，失敗圖片可個別重試或一起重試；已成功的結果保留。設定、收藏與最近使用儲存在目前瀏覽器。

### 圖片標註

拖入 PNG/JPG/WebP 或 `Ctrl+V` 貼上截圖。在畫面上拖曳繪製箭頭、框線、畫筆、馬賽克或實色遮蔽；文字工具先填說明，再點擊圖片放置。裁切工具拖曳選取保留範圍，支援復原、重做與 `Ctrl+Z` / `Ctrl+Y`。最多 300 筆標註、100 步復原。

畫面依視窗縮放，匯出保留原解析度（裁切後則為所選範圍的像素大小）。PNG/WebP 保留透明，JPG 使用白色背景；複製圖片以 PNG 貼到聊天或文件。輸出合成後的圖片，不保留可還原原圖的標註圖層或 EXIF。遮蔽敏感內容請用實色遮蔽。

### 批次檔案改名

使用「選擇資料夾」或貼上完整本機路徑，讀取後勾選檔案，設定規則並按「預覽新檔名」。核對新舊名稱後再按「執行改名」。流水號依自然檔名順序排列（2 在 10 前面），保留副檔名；可搭配前後綴、文字取代與日期。

每次最多 1000 個一般檔案，僅處理指定資料夾這一層。重名、連結、無效檔名與預覽後內容變更會被擋下；執行失敗會回復原名。復原紀錄存於 `%LOCALAPPDATA%\小黑工具箱\rename-history`，重新開啟仍可使用；被其他程式修改或原名已占用時停止復原。若程式在改名途中中斷，下次在紀錄中按「復原中斷操作」。紀錄包含必要的資料夾路徑、檔名與識別資訊，不備份檔案內容。

### PDF 工具

最多加入 20 份 PDF，合計 50 MB、500 頁。勾選需要的頁面，以拖曳或箭頭排序，點擊旋轉按鈕順時針轉 90 度。「快速選頁與排序」使用卡片左上角的排列序號，例如 `3,1-2` 或 `4-1`，可一次抽頁並調整順序。

「合併／抽取」輸出一份 PDF；「每頁拆成 PDF」將選取頁面各自輸出為 PDF 並打包 ZIP。加密來源需輸入開啟密碼；輸出的新文件不保留開啟密碼。原始檔不會被覆寫。編輯已簽署文件會使原數位簽章失效。

### 開發模式

```bash
pip install -r requirements.txt
python app.py
```

開發模式首次使用 AI 功能時，相關模型可能需要下載到使用者模型快取；發行包已包含模型。

## 打包

```bash
pip install pyinstaller
```

打包時請使用 CPU 版 PyTorch，避免把數 GB 的 CUDA 函式庫包進 EXE。這台機器可用獨立建置環境：

```powershell
python -m venv --system-site-packages .venv-build
.\.venv-build\Scripts\python.exe -m pip install --no-deps torch==2.11.0+cpu --index-url https://download.pytorch.org/whl/cpu
.\.venv-build\Scripts\python.exe build.py
```

打包前請先讓 EasyOCR 下載所有語言模型：

```powershell
python -c "import easyocr; easyocr.Reader(['en'], gpu=False, detector=False)"
python -c "import easyocr; easyocr.Reader(['ch_sim','en'], gpu=False, detector=False)"
python -c "import easyocr; easyocr.Reader(['ja','en'], gpu=False, detector=False)"
python -c "import easyocr; easyocr.Reader(['ko','en'], gpu=False, detector=False)"
```

`build.py` 會檢查 BiRefNet 和所有 OCR 模型是否存在，並保留上一份 `dist` 供回復。

輸出：
- `小黑工具箱_vX.X.X.zip` — 完整安裝包
- `小黑工具箱_vX.X.X_patch.zip` — 差量更新包

正式發佈應以最新**已公開**版本的 manifest 作為差量更新基準，v1.2.0 使用 `python build.py --base-version 1.1.0` 明確指定。請勿以未發佈的本機建置為基準。

## 更新機制

使用者端：啟動時自動檢查 GitHub Releases，有新版本會在頁面頂部顯示通知，一鍵更新。

開發端：
```bash
# 1. 修改 version.json 版本號
# 2. 打包
python build.py
# 3. 上傳 Release
gh release create vX.X.X "小黑工具箱_vX.X.X.zip" "小黑工具箱_vX.X.X_patch.zip" --title "vX.X.X" --notes "更新內容"
```

## 技術架構

- **後端**：Python Flask
- **前端**：Tailwind CSS + Lucide Icons
- **AI 去背**：rembg + BiRefNet (ONNX)
- **OCR**：EasyOCR
- **打包**：PyInstaller（單資料夾模式）

## 驗證

```powershell
python -m unittest discover -s tests -v
```

前端語法檢查需 Node.js；打包後可使用合成圖片與加密 PDF 執行實際 EXE 測試：

```powershell
python scripts/check_frontend.py
python scripts/prepare_smoke_files.py
# 啟動 dist/小黑工具箱/小黑工具箱.exe 後：
python scripts/smoke_test.py
python scripts/verify_archives.py
```

`verify_archives.py` 需本機完整／差量 ZIP 和兩版 build manifest，會檢查 CRC、SHA-256、版本、更新基準及打包的前端檔案。

---

小黑專屬打造

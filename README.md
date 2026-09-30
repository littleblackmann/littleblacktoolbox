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

QR Code 頁面同時支援圖片辨識：拖入 PNG / JPG / WebP 或 Ctrl+V 貼上截圖，可讀取同圖多個 QR 並複製內容。

## 特色

- **工具離線可用** — 零 CDN 依賴，發行包包含 AI 模型；啟動時的 GitHub 版本檢查需要網路，但失敗不影響工具
- **隱私安全** — 檔案只在你的電腦上處理，不會上傳到任何地方
- **自動更新** — 透過 GitHub Releases 檢查新版本，支援差量更新
- **一鍵啟動** — 雙擊 exe 自動開啟瀏覽器

## 使用方式

### 直接使用（已打包 exe）

1. 從 [Releases](https://github.com/littleblackmann/littleblacktoolbox/releases) 下載最新版 ZIP
2. 解壓縮後雙擊 `小黑工具箱.exe`
3. 瀏覽器會自動開啟 `http://127.0.0.1:5000`

圖片上傳上限為 50 MB、3000 萬像素。OCR 一次可選一種繁中／簡中／日／韓語言，並可搭配英文。

### 圖片批次處理

最多選擇 50 張、合計 50 MB 的靜態圖片。設定最大寬高後保持比例縮小，不放大小圖；填 0 表示不限制。JPG / WebP 可調整品質，PNG 使用無損壓縮。透明 PNG / WebP 保留透明；轉成 JPG 時使用所選背景色。預設移除拍攝資訊，勾選可保留 EXIF 與 ICC；拍攝方向會自動校正。

結果會顯示尺寸與處理前後大小。重新編碼不保證體積更小，請比較後下載；ZIP 中的重複檔名會自動加上序號。

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

正式發佈應以最新**已公開**版本的 manifest 作為差量更新基準，使用 `python build.py --base-version 1.0.1` 明確指定。請勿以未發佈的本機建置為基準。

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

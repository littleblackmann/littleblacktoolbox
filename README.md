# 小黑工具箱

**離線多功能工具箱** — 打開就用，用完就關。不需要網路、不會上傳你的檔案。

## 功能一覽

| 工具 | 說明 | 技術 |
|------|------|------|
| AI 智慧去背 | 一鍵去除圖片背景，精準度媲美線上服務 | BiRefNet 深度學習模型 |
| PNG 轉 ICO | 上傳 PNG，自動產生 16~256px 全尺寸圖示檔 | Pillow |
| 文字轉檔工坊 | Markdown / HTML / CSV / JSON / YAML / XML / TSV 互轉，支援匯出 PDF | 純前端 JavaScript |
| QR Code 生成器 | 輸入文字/網址，即時產生 QR Code，支援自訂顏色與尺寸 | qrcode.js |
| OCR 文字辨識 | 上傳圖片或 Ctrl+V 貼上截圖，AI 辨識圖中文字 | EasyOCR |

## 特色

- **100% 離線運作** — 零 CDN 依賴，所有 JS 函式庫已本地化
- **隱私安全** — 檔案只在你的電腦上處理，不會上傳到任何地方
- **自動更新** — 透過 GitHub Releases 檢查新版本，支援差量更新
- **一鍵啟動** — 雙擊 exe 自動開啟瀏覽器

## 使用方式

### 直接使用（已打包 exe）

1. 從 [Releases](https://github.com/littleblackmann/littleblacktoolbox/releases) 下載最新版 ZIP
2. 解壓縮後雙擊 `小黑工具箱.exe`
3. 瀏覽器會自動開啟 `http://127.0.0.1:5000`

### 開發模式

```bash
pip install -r requirements.txt
pip install easyocr
python app.py
```

## 打包

```bash
pip install pyinstaller
python build.py
```

輸出：
- `小黑工具箱_vX.X.X.zip` — 完整安裝包
- `小黑工具箱_vX.X.X_patch.zip` — 差量更新包

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

---

小黑專屬打造

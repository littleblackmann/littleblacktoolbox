"""One catalog for navigation, discovery and recent tools."""
TOOLS = [
    dict(id='image', path='/tool/image-workshop', name='圖片批次處理', category='圖片', icon='images', color='blue', description='縮圖、壓縮、轉檔，一次處理多張圖片。', keywords='照片 JPG PNG WebP resize 壓縮 縮圖 轉檔 去背 流程'),
    dict(id='annotate', path='/tool/image-editor', name='圖片標註', category='圖片', icon='pencil', color='violet', description='裁切、箭頭、框選、文字與馬賽克。', keywords='截圖 教學 回報 編輯 遮罩 馬賽克 crop 箭頭 標註'),
    dict(id='pdf', path='/tool/pdf-workshop', name='PDF 工作坊', category='文件', icon='files', color='rose', description='選頁、排序、旋轉、合併與拆分文件。', keywords='合併文件 抽頁 文件 拆分 排序 PDF'),
    dict(id='rename', path='/tool/batch-rename', name='批次檔案改名', category='檔案', icon='folder-pen', color='amber', description='預覽新舊檔名、加流水號，支援復原。', keywords='檔案 資料夾 命名 rename 流水號 日期 取代 整理'),
    dict(id='bg', path='/tool/bg-remover', name='AI 智慧去背', category='圖片', icon='eraser', color='violet', description='在本機移除背景，保留透明圖片。', keywords='AI 背景 移除 透明 人像 商品 去背'),
    dict(id='ocr', path='/tool/ocr', name='OCR 文字辨識', category='文字', icon='scan-text', color='cyan', description='貼上截圖或加入圖片，擷取圖中文字。', keywords='文字 辨識 擷取 截圖 中文 英文 日文 韓文 OCR'),
    dict(id='text', path='/tool/text-converter', name='文字轉檔', category='文字', icon='file-text', color='emerald', description='Markdown、JSON、CSV 等格式互轉。', keywords='文字 轉檔 Markdown JSON CSV YAML XML HTML TSV'),
    dict(id='qr', path='/tool/qrcode', name='QR Code', category='其他', icon='qr-code', color='amber', description='產生 QR Code，或貼上圖片辨識內容。', keywords='QR Code 二維碼 網址 掃描 辨識 產生'),
    dict(id='ico', path='/tool/png-to-ico', name='PNG 轉 ICO', category='圖片', icon='layers', color='blue', description='將 PNG 製作成多種尺寸的 Windows 圖示。', keywords='ico icon 圖示 桌面 圖標 PNG'),
]

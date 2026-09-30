# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

# 路徑設定
HOME = os.path.expanduser('~')
PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

# rembg dynamically imports sessions. Its CLI modules pull in unused video tools.
rembg_imports = ['rembg', 'rembg.bg', 'rembg.session_factory'] + collect_submodules('rembg.sessions')
rembg_datas = collect_data_files('rembg')

# 收集依賴的 package metadata（rembg 用 importlib.metadata 查版本號）
metadata_datas = copy_metadata('pymatting') + copy_metadata('rembg') + copy_metadata('onnxruntime')

# 模型路徑
BIREFNET_MODEL = os.path.join(HOME, '.u2net', 'birefnet-general.onnx')
EASYOCR_MODEL_DIR = os.path.join(HOME, '.EasyOCR', 'model')
ICON_PATH = os.path.join(PROJECT_DIR, 'app_icon.ico')

a = Analysis(
    [os.path.join(PROJECT_DIR, 'app.py')],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=[
        # 模板和靜態檔案
        (os.path.join(PROJECT_DIR, 'templates'), 'templates'),
        (os.path.join(PROJECT_DIR, 'static'), 'static'),
        # 版本檔
        (os.path.join(PROJECT_DIR, 'version.json'), '.'),
        # 更新模組
        (os.path.join(PROJECT_DIR, 'updater'), 'updater'),
        # AI 去背模型（BiRefNet）
        (BIREFNET_MODEL, '.u2net'),
        # EasyOCR 模型（繁中 + 文字偵測）
        (EASYOCR_MODEL_DIR, os.path.join('.EasyOCR', 'model')),
    ] + rembg_datas + metadata_datas,
    hiddenimports=rembg_imports + [
        # rembg 相關（額外確保）
        'onnxruntime',
        'PIL',
        'PIL.Image',
        'scipy',
        'scipy.special',
        'scipy.ndimage',
        'skimage',
        'skimage.morphology',
        'pymatting',
        # EasyOCR 相關
        'easyocr',
        'torch',
        'torchvision',
        # PDF/QR tools and AES-protected PDFs
        'pypdf',
        'pypdf._crypt_providers._cryptography',
        'cryptography',
        'cv2',
        # 更新模組
        'updater',
        'updater.auto_updater',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'torchaudio',
        'moviepy',
        'av',
        'imageio_ffmpeg',
        'pytest',
        'IPython',
        'notebook',
        'sphinx',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='小黑工具箱',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='小黑工具箱',
)

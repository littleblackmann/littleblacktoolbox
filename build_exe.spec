# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# 路徑設定
HOME = os.path.expanduser('~')
PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

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
    ],
    hiddenimports=[
        # rembg 相關
        'rembg',
        'rembg.sessions',
        'rembg.sessions.birefnet_general',
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

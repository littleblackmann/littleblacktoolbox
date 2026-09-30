"""
小黑工具箱 - 主程式
啟動本地 Flask 伺服器，提供所有工具的統一入口。
"""

import sys
import os
import multiprocessing

# PyInstaller Windows 必需：防止子進程重複執行 main
multiprocessing.freeze_support()

import json
import base64
import webbrowser
import threading
from io import BytesIO
from flask import Flask, render_template, request, jsonify
from PIL import Image, UnidentifiedImageError

# 確保打包後也能正確找到 templates / static / 模型
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    # 設定 u2net 模型路徑
    model_dir = os.path.join(BASE_DIR, '.u2net')
    os.environ['U2NET_HOME'] = model_dir
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OCR_MODEL_DIR = (os.path.join(BASE_DIR, '.EasyOCR', 'model')
                 if getattr(sys, 'frozen', False) else None)


def create_ocr_reader(languages):
    import easyocr
    options = {'gpu': False}
    if OCR_MODEL_DIR:
        options.update(model_storage_directory=OCR_MODEL_DIR, download_enabled=False)
    return easyocr.Reader(languages, **options)

template_folder = os.path.join(BASE_DIR, 'templates')
static_folder = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
from tools_api import tools
app.register_blueprint(tools)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 最大上傳 50MB
MAX_IMAGE_PIXELS = 30_000_000
SUPPORTED_IMAGE_FORMATS = {'PNG', 'JPEG', 'WEBP'}
OCR_LANGUAGES = {'ch_tra', 'ch_sim', 'en', 'ja', 'ko'}


@app.errorhandler(413)
def upload_too_large(_error):
    return jsonify({'error': '上傳檔案合計超過 50 MB 限制'}), 413


def read_image_upload():
    """Validate the uploaded image before passing its bytes to an AI model."""
    if 'image' not in request.files:
        return None, '未收到圖片'
    image_bytes = request.files['image'].read()
    if not image_bytes:
        return None, '圖片檔案是空的'
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if image.format not in SUPPORTED_IMAGE_FORMATS:
                return None, '只支援 PNG、JPG、WebP 圖片'
            if image.width * image.height > MAX_IMAGE_PIXELS:
                return None, '圖片解析度過高（上限 3000 萬像素）'
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None, '圖片無法讀取或檔案已損壞'
    return image_bytes, None

# ─── 啟動時預載入 rembg ────────────────────────────────

rembg_remove = None
rembg_error = None
rembg_loading = threading.Event()  # 用來等待載入完成

def preload_rembg():
    """背景預載入 rembg（使用 BiRefNet 模型，品質最佳）"""
    global rembg_remove, rembg_error
    try:
        from rembg import remove, new_session
        session = new_session("birefnet-general")
        rembg_remove = lambda data: remove(data, session=session, post_process_mask=True)
        print("  [OK] AI 去背模組載入成功（BiRefNet）")
    except ImportError:
        rembg_error = 'rembg 套件未安裝，請執行: pip install rembg onnxruntime'
        print(f"  [!!] {rembg_error}")
    except Exception as e:
        rembg_error = f'載入失敗：{str(e)}'
        print(f"  [!!] {rembg_error}")
    finally:
        rembg_loading.set()  # 不管成功失敗，都標記載入結束


# ─── 啟動時預載入 EasyOCR ──────────────────────────────

ocr_reader = None
ocr_error = None
ocr_loading = threading.Event()
ocr_current_langs = None  # 記住目前載入的語言組合
ocr_lock = threading.Lock()

def preload_ocr():
    """背景預載入 EasyOCR（預設繁中+英文）"""
    global ocr_reader, ocr_error, ocr_current_langs
    try:
        reader = create_ocr_reader(['ch_tra', 'en'])
        with ocr_lock:
            ocr_reader = reader
            ocr_current_langs = ['ch_tra', 'en']
        print("  [OK] OCR 文字辨識模組載入成功（EasyOCR）")
    except ImportError:
        ocr_error = 'easyocr 套件未安裝，請執行: pip install easyocr'
        print(f"  [!!] {ocr_error}")
    except Exception as e:
        ocr_error = f'OCR 載入失敗：{str(e)}'
        print(f"  [!!] {ocr_error}")
    finally:
        ocr_loading.set()


# ─── 更新相關 ─────────────────────────────────────────

update_info_cache = None  # 快取更新檢查結果

def check_update_background():
    """背景檢查更新（啟動 5 秒後）"""
    global update_info_cache
    import time
    time.sleep(5)
    try:
        from updater.auto_updater import check_for_update
        result = check_for_update()
        if result:
            update_info_cache = result
            print(f"  [!!] 發現新版本：v{result['version']}")
        else:
            print("  [OK] 已是最新版本")
    except Exception as e:
        print(f"  [!!] 更新檢查失敗：{e}")


# ─── 頁面路由 ───────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tool/bg-remover')
def bg_remover_page():
    return render_template('bg_remover.html')

@app.route('/tool/png-to-ico')
def png_to_ico_page():
    return render_template('png_to_ico.html')

@app.route('/tool/text-converter')
def text_converter_page():
    return render_template('text_converter.html')

@app.route('/tool/qrcode')
def qrcode_page():
    return render_template('qrcode.html')

@app.route('/tool/ocr')
def ocr_page():
    return render_template('ocr.html')

# ─── API 路由 ───────────────────────────────────────

@app.route('/api/remove-bg', methods=['POST'])
def remove_bg_api():
    """AI 去背 API"""
    input_bytes, error = read_image_upload()
    if error:
        return jsonify({'error': error}), 400

    # 等待背景載入完成（最多等 60 秒）
    if not rembg_loading.is_set():
        rembg_loading.wait(timeout=60)

    if rembg_remove is None:
        error_msg = rembg_error or 'AI 去背模組尚未就緒，請稍後再試...'
        return jsonify({'error': error_msg}), 503

    try:
        output_bytes = rembg_remove(input_bytes)

        b64 = base64.b64encode(output_bytes).decode('utf-8')
        return jsonify({
            'success': True,
            'image': f'data:image/png;base64,{b64}'
        })

    except Exception as e:
        return jsonify({'error': f'處理失敗：{str(e)}'}), 500


@app.route('/api/ocr', methods=['POST'])
def ocr_api():
    """OCR 文字辨識 API"""
    global ocr_reader, ocr_current_langs

    image_bytes, error = read_image_upload()
    if error:
        return jsonify({'error': error}), 400
    try:
        requested_langs = json.loads(request.form.get('languages', '["ch_tra", "en"]'))
    except (TypeError, ValueError):
        return jsonify({'error': '語言設定格式錯誤'}), 400
    if (not isinstance(requested_langs, list) or not requested_langs or
            any(not isinstance(lang, str) or lang not in OCR_LANGUAGES for lang in requested_langs)):
        return jsonify({'error': '請選擇有效的辨識語言'}), 400
    requested_langs = sorted(set(requested_langs))
    if sum(lang != 'en' for lang in requested_langs) > 1:
        return jsonify({'error': 'EasyOCR 一次只能選一種非英語語言，可搭配英文'}), 400

    # 等待背景載入完成（最多等 120 秒，首次要下載模型）
    if not ocr_loading.is_set():
        ocr_loading.wait(timeout=120)

    try:
        # 執行 OCR
        import numpy as np
        with Image.open(BytesIO(image_bytes)) as source:
            image = source.convert('RGB')
        image_np = np.array(image)

        # Reader changes and inference share a lock so concurrent requests use
        # the requested language model instead of another request's model.
        with ocr_lock:
            if ocr_reader is None or sorted(ocr_current_langs or []) != requested_langs:
                ocr_reader = create_ocr_reader(requested_langs)
                ocr_current_langs = requested_langs
                print(f"  [OK] OCR 模型已切換語言：{requested_langs}")
            results = ocr_reader.readtext(image_np)

        # 組合辨識結果
        text_lines = [item[1] for item in results]
        full_text = '\n'.join(text_lines)

        return jsonify({
            'success': True,
            'text': full_text,
            'count': len(results)
        })

    except ImportError:
        return jsonify({'error': 'easyocr 套件未安裝，請執行: pip install easyocr'}), 503
    except Exception as e:
        return jsonify({'error': f'辨識失敗：{str(e)}'}), 500


@app.route('/api/check-update')
def check_update_api():
    """檢查是否有新版本"""
    global update_info_cache
    if update_info_cache:
        return jsonify({
            'has_update': True,
            'version': update_info_cache['version'],
            'release_notes': update_info_cache.get('release_notes', ''),
        })
    # 如果快取為空，即時檢查一次
    try:
        from updater.auto_updater import check_for_update, get_current_version
        result = check_for_update()
        if result:
            update_info_cache = result
            return jsonify({
                'has_update': True,
                'version': result['version'],
                'release_notes': result.get('release_notes', ''),
            })
        return jsonify({
            'has_update': False,
            'current_version': get_current_version(),
        })
    except Exception as e:
        return jsonify({'has_update': False, 'error': str(e)})


@app.route('/api/apply-update', methods=['POST'])
def apply_update_api():
    """觸發更新：下載 + 覆蓋 + 重啟"""
    global update_info_cache
    origin = request.headers.get('Origin')
    if origin and origin not in ('http://127.0.0.1:5000', 'http://localhost:5000'):
        return jsonify({'error': '拒絕來自其他網站的更新請求'}), 403
    if not getattr(sys, 'frozen', False):
        return jsonify({'error': '開發模式請使用 Git 更新原始碼'}), 400
    if not update_info_cache:
        return jsonify({'error': '沒有可用的更新'}), 400

    try:
        from updater.auto_updater import download_and_apply
        success = download_and_apply(
            download_url=update_info_cache['download_url'],
            new_version=update_info_cache['version'],
            full_url=update_info_cache.get('full_url'),
            is_patch=update_info_cache.get('is_patch', False),
        )
        if success:
            # 更新腳本已啟動，準備退出
            threading.Thread(target=lambda: (
                __import__('time').sleep(1),
                os._exit(0)
            ), daemon=True).start()
            return jsonify({'success': True, 'message': '更新中，程式即將重啟...'})
        else:
            return jsonify({'error': '更新下載失敗'}), 500
    except Exception as e:
        return jsonify({'error': f'更新失敗：{str(e)}'}), 500


@app.route('/api/version')
def version_api():
    """回傳目前版本號"""
    try:
        from updater.auto_updater import get_current_version
        return jsonify({'version': get_current_version()})
    except Exception:
        return jsonify({'version': '1.0.0'})


# ─── 啟動 ──────────────────────────────────────────

def open_browser_once():
    """延遲 1.5 秒後開啟瀏覽器"""
    import time
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    print("=" * 50)
    print("  小黑工具箱 正在啟動...")
    print("=" * 50)

    # 背景預載入 AI 模組
    print("  [..] 正在載入 AI 去背模組...")
    threading.Thread(target=preload_rembg, daemon=True).start()
    print("  [..] 正在載入 OCR 文字辨識模組...")
    threading.Thread(target=preload_ocr, daemon=True).start()

    # 用環境變數防止子進程重複開啟瀏覽器（子進程會繼承環境變數）
    if '__TOOLBOX_RUNNING__' not in os.environ:
        os.environ['__TOOLBOX_RUNNING__'] = '1'
        threading.Thread(target=open_browser_once, daemon=True).start()

    # 背景檢查更新
    print("  [..] 背景檢查更新中...")
    threading.Thread(target=check_update_background, daemon=True).start()

    print("  [OK] 瀏覽器即將開啟 http://127.0.0.1:5000")
    print("  按 Ctrl+C 關閉工具箱")
    print("=" * 50)

    app.run(host='127.0.0.1', port=5000, debug=False)

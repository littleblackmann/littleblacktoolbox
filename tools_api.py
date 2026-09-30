"""Local image, PDF and QR tools. All input and output stays in memory."""
import json
import re
import zipfile
from io import BytesIO

from flask import Blueprint, jsonify, render_template, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError

tools = Blueprint('tools', __name__)
MAX_PIXELS = 30_000_000
MAX_PDF_PAGES = 500
IMAGE_FORMATS = {'PNG', 'JPEG', 'WEBP'}


class InputError(ValueError):
    pass


@tools.errorhandler(InputError)
def invalid_input(error):
    return jsonify(error=str(error)), 400


def safe_name(name, default='檔案'):
    name = (name or '').replace('\\', '/').split('/')[-1]
    name = re.sub(r'[\x00-\x1f<>:"|?*]', '_', name).strip(' .')
    return name[:120] or default


def uploaded_image():
    upload = request.files.get('image')
    if not upload:
        raise InputError('請選擇圖片')
    data = upload.read()
    try:
        image = Image.open(BytesIO(data))
        if image.format not in IMAGE_FORMATS:
            raise InputError('只支援 PNG、JPG、WebP 圖片')
        if image.width * image.height > MAX_PIXELS:
            raise InputError('圖片解析度過高（上限 3000 萬像素）')
        if getattr(image, 'is_animated', False):
            raise InputError('目前支援靜態圖片，請先將動態圖片轉為單張圖片')
        image.load()
        return image, safe_name(upload.filename)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        if isinstance(error, InputError):
            raise
        raise InputError('圖片無法讀取或檔案已損壞') from error


def integer_option(key, default, low, high):
    try:
        value = int(request.form.get(key, default))
    except (ValueError, TypeError):
        raise InputError(f'{key} 必須是整數')
    if not low <= value <= high:
        raise InputError(f'{key} 必須介於 {low} 到 {high}')
    return value


@tools.get('/tool/image-workshop')
def image_page():
    return render_template('image_workshop.html')


@tools.get('/tool/pdf-workshop')
def pdf_page():
    return render_template('pdf_workshop.html')


@tools.post('/api/image-process')
def image_process():
    image, name = uploaded_image()
    original_format = image.format
    output_format = request.form.get('format', 'same').upper()
    if output_format == 'SAME':
        output_format = original_format
    if output_format not in IMAGE_FORMATS:
        raise InputError('輸出格式必須是 PNG、JPEG 或 WebP')
    quality = integer_option('quality', 85, 1, 100)
    max_width = integer_option('max_width', 0, 0, 10000)
    max_height = integer_option('max_height', 0, 0, 10000)
    background = request.form.get('background', '#ffffff')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', background):
        raise InputError('背景色格式錯誤')
    image = ImageOps.exif_transpose(image)
    save_options = {}
    if request.form.get('keep_metadata', '0') == '1':
        exif = image.getexif()
        if exif:
            save_options['exif'] = exif.tobytes()
        if image.info.get('icc_profile'):
            save_options['icc_profile'] = image.info['icc_profile']
    # Pillow can automatically carry EXIF from image.info even without kwargs.
    image.info.clear()
    image.thumbnail((max_width or image.width, max_height or image.height), Image.Resampling.LANCZOS)
    if output_format == 'JPEG':
        if image.mode in ('RGBA', 'LA', 'P'):
            rgba = image.convert('RGBA')
            flattened = Image.new('RGB', image.size, background)
            flattened.paste(rgba, mask=rgba.getchannel('A'))
            image = flattened
        else:
            image = image.convert('RGB')
        save_options.update(quality=quality, optimize=True, progressive=True)
    elif output_format == 'WEBP':
        image = image.convert('RGBA' if image.mode in ('RGBA', 'LA', 'P') else 'RGB')
        save_options.update(quality=quality, method=4)
    else:
        image = image.convert('RGBA' if image.mode in ('RGBA', 'LA', 'P') else 'RGB')
        save_options.update(optimize=True, compress_level=9)
    output = BytesIO()
    image.save(output, format=output_format, **save_options)
    output.seek(0)
    extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[output_format]
    stem = name.rsplit('.', 1)[0] or '圖片'
    response = send_file(output, mimetype=f'image/{extension if extension != "jpg" else "jpeg"}',
                         as_attachment=True, download_name=f'{stem}_processed.{extension}')
    response.headers['X-Image-Width'] = str(image.width)
    response.headers['X-Image-Height'] = str(image.height)
    return response


def pdf_reader(upload, password=''):
    from pypdf import PdfReader
    if not upload:
        raise InputError('請選擇 PDF 檔案')
    data = upload.read()
    if not data or b'%PDF-' not in data[:1024]:
        raise InputError('檔案不是有效的 PDF')
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(password):
            raise InputError('PDF 需要正確的開啟密碼')
        if not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
            raise InputError(f'每次最多處理 {MAX_PDF_PAGES} 頁 PDF，且不能是空白文件')
        return reader
    except InputError:
        raise
    except Exception as error:
        raise InputError('PDF 無法讀取，請確認檔案完整與密碼正確') from error


@tools.post('/api/pdf-info')
def pdf_info():
    reader = pdf_reader(request.files.get('file'), request.form.get('password', ''))
    return jsonify(pages=len(reader.pages), encrypted=reader.is_encrypted)


def pdf_bytes(writer):
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@tools.post('/api/pdf-process')
def pdf_process():
    from pypdf import PdfWriter
    uploads = request.files.getlist('files')
    if not 1 <= len(uploads) <= 20:
        raise InputError('請選擇 1 到 20 個 PDF 檔案')
    mode = request.form.get('mode', 'combine')
    if mode not in ('combine', 'split'):
        raise InputError('PDF 處理模式無效')
    try:
        plan = json.loads(request.form.get('plan', '[]'))
        passwords = json.loads(request.form.get('passwords', '[]'))
    except (ValueError, TypeError):
        raise InputError('PDF 頁面設定格式錯誤')
    if (not isinstance(passwords, list) or len(passwords) != len(uploads) or
            any(not isinstance(p, str) for p in passwords)):
        raise InputError('PDF 密碼設定格式錯誤')
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_PDF_PAGES:
        raise InputError(f'請選擇 1 到 {MAX_PDF_PAGES} 頁')
    readers = [pdf_reader(upload, password) for upload, password in zip(uploads, passwords)]
    if sum(len(reader.pages) for reader in readers) > MAX_PDF_PAGES:
        raise InputError(f'所有文件合計最多 {MAX_PDF_PAGES} 頁')
    seen = set()
    for entry in plan:
        if not isinstance(entry, dict):
            raise InputError('頁面設定格式錯誤')
        file_index, page_index, rotation = (entry.get(key) for key in ('file', 'page', 'rotation'))
        if (type(file_index) is not int or type(page_index) is not int or
                type(rotation) is not int or rotation not in (0, 90, 180, 270) or
                not 0 <= file_index < len(readers) or
                not 0 <= page_index < len(readers[file_index].pages)):
            raise InputError('頁碼或旋轉角度無效')
        key = (file_index, page_index)
        if key in seen:
            raise InputError('同一頁不能重複選取')
        seen.add(key)
    if len(readers) > 1:
        for index, reader in enumerate(readers):
            if reader.get_fields():
                reader.add_form_topname(f'document_{index + 1}')
    name = safe_name(request.form.get('name'), '整理後文件')
    name = re.sub(r'\.(pdf|zip)$', '', name, flags=re.I) or '整理後文件'
    try:
        if mode == 'combine':
            writer = PdfWriter()
            for entry in plan:
                writer.append(readers[entry['file']], pages=[entry['page']],
                              import_outline=False, excluded_fields=['/B'])
                if entry['rotation']:
                    writer.pages[-1].rotate(entry['rotation'])
            output = pdf_bytes(writer)
            mimetype, extension = 'application/pdf', 'pdf'
        else:
            archive = BytesIO()
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
                for index, entry in enumerate(plan):
                    writer = PdfWriter()
                    writer.append(readers[entry['file']], pages=[entry['page']],
                                  import_outline=False, excluded_fields=['/B'])
                    if entry['rotation']:
                        writer.pages[-1].rotate(entry['rotation'])
                    zipped.writestr(f'{name}_{index + 1:03d}.pdf', pdf_bytes(writer))
            output = archive.getvalue()
            mimetype, extension = 'application/zip', 'zip'
    except Exception as error:
        raise InputError('PDF 處理失敗，請確認文件完整或改用較少頁面') from error
    return send_file(BytesIO(output), mimetype=mimetype, as_attachment=True,
                     download_name=f'{name}.{extension}')


@tools.post('/api/qr-decode')
def qr_decode():
    import cv2
    import numpy as np
    image, _name = uploaded_image()
    image = ImageOps.exif_transpose(image).convert('RGBA')
    background = Image.new('RGBA', image.size, 'white')
    background.alpha_composite(image)
    background = background.convert('RGB')
    # Limit detector cost while keeping the original if already reasonably sized.
    background.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
    pixels = cv2.cvtColor(np.asarray(background), cv2.COLOR_RGB2GRAY)
    detector = cv2.QRCodeDetector()
    results = []
    detected = False
    # A quiet border also makes QR images produced by the existing generator readable.
    for candidate in (pixels, cv2.copyMakeBorder(pixels, 32, 32, 32, 32, cv2.BORDER_CONSTANT, value=255)):
        try:
            success, values, points, _straight = detector.detectAndDecodeMulti(candidate)
            detected = detected or points is not None
            if success:
                results.extend(value for value in values if value)
            if not results:
                value, points, _straight = detector.detectAndDecode(candidate)
                detected = detected or points is not None
                if value:
                    results.append(value)
        except (cv2.error, UnicodeDecodeError):
            continue
        if results:
            break
    # qrcode.js adds a UTF-8 BOM for non-ASCII content; it is an encoding marker.
    results = list(dict.fromkeys(value.removeprefix('\ufeff') for value in results))
    return jsonify(success=bool(results), results=results,
                   message=('辨識完成' if results else '找到 QR Code，但內容無法解碼；請使用較清晰的圖片'
                            if detected else '未找到可辨識的 QR Code，請確認圖片清晰且四周有留白'))

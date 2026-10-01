"""Exercise a running local EXE through HTTP using synthetic verification files."""
import argparse
import base64
import io
import json
import sys
import re
import tempfile
import zipfile
from pathlib import Path

import requests
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:5000')
    parser.add_argument('--skip-ai', action='store_true')
    options = parser.parse_args()
    if not options.url.startswith(('http://127.0.0.1:', 'http://localhost:')):
        raise SystemExit('Smoke tests target a local toolbox only')
    files = ROOT / 'build/verification'
    output = files / 'exe-results'
    output.mkdir(exist_ok=True)
    def post(path, file_key, source, **fields):
        with source.open('rb') as stream:
            result = requests.post(options.url + path, files={file_key: (source.name, stream)},
                                   data=fields, timeout=180)
        assert result.status_code == 200, (path, result.status_code, result.text[:300])
        return result
    version = requests.get(options.url + '/api/version', timeout=15).json()['version']
    assert version == json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))['version'], version
    for path in ('/', '/tool/image-workshop', '/tool/pdf-workshop', '/tool/qrcode',
                 '/tool/bg-remover', '/tool/png-to-ico', '/tool/text-converter', '/tool/ocr', '/tool/image-editor', '/tool/batch-rename'):
        response = requests.get(options.url + path, timeout=15)
        assert response.status_code == 200, path
    image = post('/api/image-process', 'image', files / '測試圖片.png',
                 format='WEBP', max_width='450', quality='85')
    (output / 'resized.webp').write_bytes(image.content)
    with Image.open(io.BytesIO(image.content)) as decoded:
        assert decoded.size == (450, 250) and decoded.mode == 'RGBA'
    assert image.headers['X-Image-Width'] == '450'
    qr = post('/api/qr-decode', 'image', files / 'generated-chinese-qr.png').json()
    assert qr['results'] == ['小黑工具箱：測試文字'], qr
    info = post('/api/pdf-info', 'file', files / '密碼測試.pdf', password='fixture-password').json()
    assert info['pages'] == 3
    plan = json.dumps([{'file': 0, 'page': 2, 'rotation': 90}, {'file': 0, 'page': 0, 'rotation': 0}])
    for mode in ('combine', 'split'):
        result = post('/api/pdf-process', 'files', files / '密碼測試.pdf', plan=plan,
                      passwords=json.dumps(['fixture-password']), mode=mode, name='驗證')
        if mode == 'combine':
            reader = PdfReader(io.BytesIO(result.content))
            assert len(reader.pages) == 2 and reader.pages[0].rotation == 90
            assert not reader.is_encrypted
            (output / 'combined.pdf').write_bytes(result.content)
        else:
            with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
                assert archive.testzip() is None and len(archive.namelist()) == 2
                assert len(PdfReader(io.BytesIO(archive.read(archive.namelist()[0]))).pages) == 1
            (output / 'split.zip').write_bytes(result.content)
    html = requests.get(options.url + '/tool/batch-rename', timeout=15).text
    token = re.search(r'name="toolbox-token" content="([^"]+)"', html).group(1)
    headers = {'X-Toolbox-Token': token, 'Origin': options.url}
    def rename(action, value):
        response = requests.post(options.url + '/api/rename/' + action, json=value, headers=headers, timeout=15)
        assert response.status_code == 200, (action, response.text)
        return response.json()
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory) / 'files'; folder.mkdir()
        (folder / 'file2.txt').write_text('two', encoding='utf-8')
        (folder / 'file10.txt').write_text('ten', encoding='utf-8')
        preview = rename('preview', dict(folder=str(folder), names=['file10.txt', 'file2.txt'], options=dict(mode='sequence', base='驗證', start=1, digits=3)))
        applied = rename('apply', dict(token=preview['token']))
        assert (folder / '驗證_001.txt').read_text() == 'two'
        assert (folder / '驗證_002.txt').read_text() == 'ten'
        rename('undo', dict(id=applied['id']))
        assert {file.name for file in folder.iterdir()} == {'file2.txt', 'file10.txt'}
    print('EXE: version, 10 pages, image, QR, encrypted PDF and real rename/undo passed', flush=True)
    if not options.skip_ai:
        ocr = post('/api/ocr', 'image', files / '測試圖片.png', languages=json.dumps(['ch_tra', 'en'])).json()
        assert ocr['count'] > 0 and '工具箱' in ocr['text'], ocr
        print('EXE: OCR passed', flush=True)
        removed = post('/api/remove-bg', 'image', files / '測試圖片.png').json()
        data = base64.b64decode(removed['image'].split(',', 1)[1])
        (output / 'removed.png').write_bytes(data)
        with Image.open(io.BytesIO(data)) as decoded:
            assert decoded.size == (900, 500) and decoded.mode == 'RGBA'
        print('EXE: BiRefNet passed', flush=True)


if __name__ == '__main__':
    main()

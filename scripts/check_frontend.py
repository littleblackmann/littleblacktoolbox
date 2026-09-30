"""Parse every rendered page's inline JavaScript plus authored static scripts."""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import app


def main():
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required for frontend syntax checks')
    count = 0
    with tempfile.TemporaryDirectory() as directory:
        client = app.test_client()
        for path in ('/', '/tool/bg-remover', '/tool/png-to-ico', '/tool/text-converter',
                     '/tool/qrcode', '/tool/ocr', '/tool/image-workshop', '/tool/pdf-workshop'):
            html = client.get(path).get_data(as_text=True)
            for index, script in enumerate(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.S)):
                if not script.strip():
                    continue
                file = Path(directory) / f'inline_{count}.js'
                file.write_text(script, encoding='utf-8')
                result = subprocess.run([node, '--check', str(file)], capture_output=True, text=True)
                if result.returncode:
                    raise SystemExit(f'{path} inline script {index}: {result.stderr}')
                count += 1
        for file in ROOT.joinpath('static/js').glob('*.js'):
            result = subprocess.run([node, '--check', str(file)], capture_output=True, text=True)
            if result.returncode:
                raise SystemExit(f'{file.name}: {result.stderr}')
            count += 1
    print(f'JavaScript syntax: {count} scripts passed')


if __name__ == '__main__':
    main()

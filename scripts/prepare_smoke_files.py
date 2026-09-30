"""Create synthetic inputs for the packaged EXE smoke test."""
import shutil
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build/verification'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/msjh.ttc', 38)
    image = Image.new('RGBA', (900, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 70, 830, 430), radius=50, fill=(59, 130, 246, 255))
    draw.text((120, 185), '小黑工具箱 — 圖片測試', font=font, fill='white')
    image.save(OUTPUT / '測試圖片.png')
    (OUTPUT / 'duplicate').mkdir(exist_ok=True)
    image.save(OUTPUT / 'duplicate/測試圖片.png')
    pages = []
    for number in range(1, 4):
        page = Image.new('RGB', (600, 800), 'white')
        draw = ImageDraw.Draw(page)
        draw.text((60, 90), f'小黑工具箱 PDF 測試\n第 {number} 頁', font=font, fill='#1e293b')
        draw.rectangle((60, 240, 540, 650), fill=['#dbeafe', '#fce7f3', '#d1fae5'][number - 1])
        pages.append(page)
    pages[0].save(OUTPUT / '三頁測試.pdf', save_all=True, append_images=pages[1:])
    writer = PdfWriter(clone_from=OUTPUT / '三頁測試.pdf')
    writer.encrypt('fixture-password', algorithm='AES-256')
    writer.write(OUTPUT / '密碼測試.pdf')
    qr = cv2.QRCodeEncoder_create().encode('https://github.com/littleblackmann/littleblacktoolbox')
    qr = cv2.resize(qr, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
    qr = cv2.copyMakeBorder(qr, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    Image.fromarray(qr).save(OUTPUT / '網址QR.png')
    shutil.copy2(ROOT / 'tests/fixtures/generator_chinese.png', OUTPUT / 'generated-chinese-qr.png')
    print('Synthetic smoke test files ready')


if __name__ == '__main__':
    main()

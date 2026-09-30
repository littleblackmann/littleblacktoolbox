import io
import json
import unittest
import zipfile
from unittest.mock import patch
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject

import app as toolbox


def image_bytes(image, format='PNG', **options):
    stream = io.BytesIO()
    image.save(stream, format=format, **options)
    return stream.getvalue()


def pdf_bytes(widths=(200, 300, 400), password=None):
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=500)
    if password:
        writer.encrypt(password, algorithm='AES-256')
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def qr_pixels(text):
    pixels = cv2.QRCodeEncoder_create().encode(text)
    pixels = cv2.resize(pixels, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
    return cv2.copyMakeBorder(pixels, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)


def form_pdf(value):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=300)
    field = writer._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Widget'),
        NameObject('/FT'): NameObject('/Tx'), NameObject('/T'): TextStringObject('name'),
        NameObject('/V'): TextStringObject(value), NameObject('/P'): page.indirect_reference,
        NameObject('/Rect'): ArrayObject([NumberObject(v) for v in (10, 10, 100, 40)]),
    }))
    page[NameObject('/Annots')] = ArrayObject([field])
    writer._root_object[NameObject('/AcroForm')] = writer._add_object(DictionaryObject({
        NameObject('/Fields'): ArrayObject([field]),
    }))
    stream = io.BytesIO(); writer.write(stream)
    return stream.getvalue()


class NewToolTests(unittest.TestCase):
    def setUp(self):
        self.client = toolbox.app.test_client()

    def image_upload(self, route, data, **options):
        return self.client.post(route, data={'image': (io.BytesIO(data), '測試.png'), **options})

    def process_pdf(self, files, plan, mode='combine', passwords=None, **options):
        return self.client.post('/api/pdf-process', data={
            'files': [(io.BytesIO(data), f'文件{index}.pdf') for index, data in enumerate(files)],
            'plan': json.dumps(plan), 'passwords': json.dumps(passwords or [''] * len(files)),
            'mode': mode, **options,
        })

    def test_image_resize_formats_and_no_upscaling(self):
        source = image_bytes(Image.new('RGBA', (400, 200), (255, 0, 0, 128)))
        for format in ('PNG', 'JPEG', 'WEBP', 'same'):
            with self.subTest(format=format):
                result = self.image_upload('/api/image-process', source, format=format, max_width='100', max_height='100')
                self.assertEqual(result.status_code, 200)
                with Image.open(io.BytesIO(result.data)) as output:
                    self.assertEqual(output.size, (100, 50))
                    self.assertEqual(output.format, 'PNG' if format == 'same' else format)
                    if format != 'JPEG':
                        self.assertEqual(output.convert('RGBA').getpixel((10, 10))[3], 128)
        result = self.image_upload('/api/image-process', source, max_width='1000')
        self.assertEqual(Image.open(io.BytesIO(result.data)).size, (400, 200))

    def test_jpeg_alpha_is_flattened_with_selected_background(self):
        source = image_bytes(Image.new('RGBA', (20, 20), (255, 0, 0, 0)))
        result = self.image_upload('/api/image-process', source, format='JPEG', background='#00ff00', quality='100')
        with Image.open(io.BytesIO(result.data)) as output:
            self.assertEqual(output.mode, 'RGB')
            pixel = output.getpixel((10, 10))
            self.assertLess(pixel[0], 5)
            self.assertGreater(pixel[1], 250)
            self.assertLess(pixel[2], 5)

    def test_metadata_and_exif_orientation(self):
        source = Image.new('RGB', (80, 40), 'blue')
        exif = Image.Exif(); exif[274] = 6; exif[315] = 'Example Photographer'
        data = image_bytes(source, format='JPEG', exif=exif)
        for keep in ('0', '1'):
            with self.subTest(keep=keep):
                result = self.image_upload('/api/image-process', data, keep_metadata=keep)
                with Image.open(io.BytesIO(result.data)) as output:
                    self.assertEqual(output.size, (40, 80))
                    self.assertNotIn(274, output.getexif())
                    self.assertEqual(output.getexif().get(315), 'Example Photographer' if keep == '1' else None)

    def test_image_input_and_options_validation(self):
        data = image_bytes(Image.new('RGB', (4, 4)))
        for options in ({'max_width': '-1'}, {'quality': '101'}, {'max_height': 'abc'},
                        {'format': 'GIF'}, {'background': 'wrong'}):
            with self.subTest(options=options):
                self.assertEqual(self.image_upload('/api/image-process', data, **options).status_code, 400)
        self.assertEqual(self.image_upload('/api/image-process', b'bad').status_code, 400)
        animation = io.BytesIO()
        Image.new('RGB', (4, 4), 'red').save(animation, format='WEBP', save_all=True,
            append_images=[Image.new('RGB', (4, 4), 'blue')], duration=100, loop=0)
        self.assertEqual(self.image_upload('/api/image-process', animation.getvalue()).status_code, 400)
        with patch.dict(toolbox.app.config, {'MAX_CONTENT_LENGTH': 10}):
            self.assertEqual(self.image_upload('/api/image-process', data).status_code, 413)

    def test_pdf_merge_extract_reorder_and_rotation(self):
        result = self.process_pdf([pdf_bytes(), pdf_bytes((600, 700))], [
            {'file': 1, 'page': 1, 'rotation': 90},
            {'file': 0, 'page': 2, 'rotation': 270},
            {'file': 0, 'page': 0, 'rotation': 0},
        ], name='整理.pdf')
        self.assertEqual(result.status_code, 200, result.data[:200])
        reader = PdfReader(io.BytesIO(result.data))
        self.assertEqual([int(page.mediabox.width) for page in reader.pages], [700, 400, 200])
        self.assertEqual([page.rotation for page in reader.pages], [90, 270, 0])
        self.assertIn('filename*=UTF-8', result.headers['Content-Disposition'])

    def test_pdf_split_zip_has_ordered_valid_pages_and_safe_names(self):
        result = self.process_pdf([pdf_bytes()], [
            {'file': 0, 'page': 2, 'rotation': 180}, {'file': 0, 'page': 0, 'rotation': 0},
        ], mode='split', name='../整理.zip')
        self.assertEqual(result.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), ['整理_001.pdf', '整理_002.pdf'])
            first = PdfReader(io.BytesIO(archive.read('整理_001.pdf')))
            self.assertEqual(len(first.pages), 1)
            self.assertEqual(int(first.pages[0].mediabox.width), 400)
            self.assertEqual(first.pages[0].rotation, 180)

    def test_pdf_merge_preserves_values_of_identically_named_form_fields(self):
        result = self.process_pdf([form_pdf('Alice'), form_pdf('Bob')], [
            {'file': 0, 'page': 0, 'rotation': 0}, {'file': 1, 'page': 0, 'rotation': 0},
        ])
        self.assertEqual(result.status_code, 200)
        fields = PdfReader(io.BytesIO(result.data)).get_fields()
        self.assertEqual(fields['document_1.name']['/V'], 'Alice')
        self.assertEqual(fields['document_2.name']['/V'], 'Bob')

    def test_aes_pdf_requires_correct_password_and_outputs_readable_pdf(self):
        data = pdf_bytes(password='fixture-password')
        self.assertEqual(self.client.post('/api/pdf-info', data={'file': (io.BytesIO(data), 'protected.pdf')}).status_code, 400)
        info = self.client.post('/api/pdf-info', data={'file': (io.BytesIO(data), 'protected.pdf'), 'password': 'fixture-password'})
        self.assertEqual(info.json['pages'], 3)
        self.assertTrue(info.json['encrypted'])
        result = self.process_pdf([data], [{'file': 0, 'page': 1, 'rotation': 0}], passwords=['fixture-password'])
        self.assertEqual(result.status_code, 200)
        self.assertFalse(PdfReader(io.BytesIO(result.data)).is_encrypted)

    def test_pdf_rejects_invalid_plan_files_and_limits(self):
        data = pdf_bytes()
        for plan in ([], [{'file': 1, 'page': 0, 'rotation': 0}],
                     [{'file': 0, 'page': 3, 'rotation': 0}], [{'file': 0, 'page': 0, 'rotation': 45}],
                     [{'file': 0, 'page': 0, 'rotation': 0}] * 2, [None], [{'file': True, 'page': 0, 'rotation': 0}]):
            with self.subTest(plan=plan):
                self.assertEqual(self.process_pdf([data], plan).status_code, 400)
        self.assertEqual(self.process_pdf([b'not PDF'], [{'file': 0, 'page': 0, 'rotation': 0}]).status_code, 400)
        self.assertEqual(self.process_pdf([data], [{'file': 0, 'page': 0, 'rotation': 0}], mode='bad').status_code, 400)
        oversized = pdf_bytes([200] * 501)
        self.assertEqual(self.client.post('/api/pdf-info', data={'file': (io.BytesIO(oversized), 'big.pdf')}).status_code, 400)

    def test_qr_reads_url_unicode_multiple_and_no_quiet_border(self):
        for value in ('https://example.com/toolbox', '小黑工具箱：測試文字'):
            with self.subTest(value=value):
                pixels = qr_pixels(value)
                result = self.image_upload('/api/qr-decode', image_bytes(Image.fromarray(pixels)))
                self.assertEqual(result.status_code, 200)
                self.assertIn(value, result.json['results'])
        left, right = qr_pixels('first'), qr_pixels('second')
        canvas = np.full((max(left.shape[0], right.shape[0]), left.shape[1] + right.shape[1] + 80), 255, dtype=np.uint8)
        canvas[:left.shape[0], :left.shape[1]] = left
        canvas[:right.shape[0], left.shape[1] + 80:] = right
        result = self.image_upload('/api/qr-decode', image_bytes(Image.fromarray(canvas)))
        self.assertEqual(set(result.json['results']), {'first', 'second'})
        cropped = qr_pixels('borderless')[60:-60, 60:-60]
        result = self.image_upload('/api/qr-decode', image_bytes(Image.fromarray(cropped)))
        self.assertIn('borderless', result.json['results'])

    def test_qr_blank_and_invalid_image(self):
        result = self.image_upload('/api/qr-decode', image_bytes(Image.new('RGB', (200, 200), 'white')))
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json['success'])
        self.assertEqual(result.json['results'], [])
        self.assertEqual(self.image_upload('/api/qr-decode', b'wrong').status_code, 400)

    def test_qr_generator_chinese_round_trip(self):
        data = Path(__file__).with_name('fixtures').joinpath('generator_chinese.png').read_bytes()
        result = self.image_upload('/api/qr-decode', data)
        self.assertEqual(result.json['results'], ['小黑工具箱：測試文字'])


if __name__ == '__main__':
    unittest.main()

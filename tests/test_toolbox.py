import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

import app as toolbox
import build
from updater import auto_updater


def png_bytes():
    stream = io.BytesIO()
    Image.new('RGB', (4, 4), 'red').save(stream, format='PNG')
    return stream.getvalue()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = toolbox.app.test_client()

    def upload(self, route, data, **fields):
        return self.client.post(route, data={
            'image': (io.BytesIO(data), 'photo.png'), **fields,
        })

    def test_all_pages_load(self):
        for path in ('/', '/tool/bg-remover', '/tool/png-to-ico',
                     '/tool/text-converter', '/tool/qrcode', '/tool/ocr',
                     '/tool/image-workshop', '/tool/pdf-workshop'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_invalid_images_are_rejected_before_model_work(self):
        for route in ('/api/remove-bg', '/api/ocr'):
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route).status_code, 400)
                self.assertEqual(self.upload(route, b'not an image').status_code, 400)
                self.assertEqual(self.upload(route, b'').status_code, 400)

    def test_background_removal_uses_valid_image(self):
        with patch.object(toolbox, 'rembg_remove', return_value=png_bytes()), \
                patch.object(toolbox, 'rembg_loading') as loading:
            loading.is_set.return_value = True
            result = self.upload('/api/remove-bg', png_bytes())
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json['image'].startswith('data:image/png;base64,'))

    def test_ocr_validates_languages_and_reads_image(self):
        toolbox.ocr_loading.set()
        self.assertEqual(self.upload('/api/ocr', png_bytes(), languages='bad').status_code, 400)
        self.assertEqual(self.upload('/api/ocr', png_bytes(), languages='[]').status_code, 400)
        self.assertEqual(self.upload('/api/ocr', png_bytes(), languages='["other"]').status_code, 400)
        self.assertEqual(self.upload('/api/ocr', png_bytes(), languages='["ja", "ko"]').status_code, 400)
        reader = Mock()
        reader.readtext.return_value = [(None, '測試', 0.9)]
        with patch.object(toolbox, 'ocr_reader', reader), \
                patch.object(toolbox, 'ocr_current_langs', ['ch_tra', 'en']):
            result = self.upload('/api/ocr', png_bytes(), languages='["en", "ch_tra"]')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['text'], '測試')
        reader.readtext.assert_called_once()

    def test_cross_site_update_request_is_rejected(self):
        result = self.client.post('/api/apply-update', headers={'Origin': 'https://example.com'})
        self.assertEqual(result.status_code, 403)

    def test_packaged_ocr_uses_bundled_models_without_download(self):
        fake_easyocr = Mock()
        with patch.dict('sys.modules', {'easyocr': fake_easyocr}), \
                patch.object(toolbox, 'OCR_MODEL_DIR', 'bundled-models'):
            toolbox.create_ocr_reader(['ja', 'en'])
        fake_easyocr.Reader.assert_called_once_with(
            ['ja', 'en'], gpu=False, model_storage_directory='bundled-models',
            download_enabled=False)


class UpdateArchiveTests(unittest.TestCase):
    def make_archive(self, entries):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        stream.seek(0)
        return zipfile.ZipFile(stream)

    def test_full_release_and_matching_patch(self):
        prefix = auto_updater.APP_NAME + '/'
        version = json.dumps({'version': '1.0.2'})
        with self.make_archive({prefix + '_internal/version.json': version,
                                prefix + 'app.exe': b'app'}) as zf:
            auto_updater._validate_archive(zf, '1.0.2', False)
        with self.make_archive({prefix + '_internal/version.json': version,
                                prefix + 'patch_info.json': json.dumps({
                                    'from_version': '1.0.1', 'to_version': '1.0.2',
                                })}) as zf, patch.object(auto_updater, 'get_current_version', return_value='1.0.1'):
            auto_updater._validate_archive(zf, '1.0.2', True)

    def test_rejects_path_traversal_and_incompatible_patch(self):
        prefix = auto_updater.APP_NAME + '/'
        version = json.dumps({'version': '1.0.2'})
        for entries, patch_mode in (
            ({prefix + '_internal/version.json': version, prefix + '../escape.txt': 'x'}, False),
            ({prefix + '_internal/version.json': version}, True),
            ({prefix + '_internal/version.json': json.dumps({'version': '9.9.9'})}, False),
        ):
            with self.subTest(entries=entries), self.make_archive(entries) as zf:
                with self.assertRaises(ValueError):
                    auto_updater._validate_archive(zf, '1.0.2', patch_mode)

    def test_patch_contains_base_version_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist = Path(temp_dir) / 'dist'
            dist.mkdir()
            (dist / 'version.json').write_text('{"version":"1.0.2"}', encoding='utf-8')
            patch_zip = Path(temp_dir) / 'patch.zip'
            with patch.object(build, 'PATCH_ZIP', str(patch_zip)), \
                    patch.object(build, 'APP_VERSION', '1.0.2'):
                build.create_patch_zip(str(dist), {}, {'version.json': 'new'}, '1.0.1')
            with zipfile.ZipFile(patch_zip) as zf:
                metadata = json.loads(zf.read(build.APP_NAME + '/patch_info.json'))
            self.assertEqual(metadata, {'from_version': '1.0.1', 'to_version': '1.0.2'})


if __name__ == '__main__':
    unittest.main()

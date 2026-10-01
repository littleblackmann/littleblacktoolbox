"""Real temporary-file tests: no user documents are touched."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app
import rename_api


class RenameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'files'; self.root.mkdir()
        self.history = Path(self.temp.name) / 'history'
        self.original_state = app.config.get('RENAME_STATE_DIR')
        app.config['RENAME_STATE_DIR'] = str(self.history)
        self.client = app.test_client()
        self.headers = {'X-Toolbox-Token': app.config['LOCAL_ACTION_TOKEN']}
        rename_api._plans.clear()

    def tearDown(self):
        if self.original_state is None: app.config.pop('RENAME_STATE_DIR', None)
        else: app.config['RENAME_STATE_DIR'] = self.original_state
        self.temp.cleanup()

    def write(self, name, text):
        self.root.joinpath(name).write_text(text, encoding='utf-8')

    def post(self, action, **value):
        return self.client.post('/api/rename/' + action, json=value, headers=self.headers)

    def preview(self, names, **options):
        return self.post('preview', folder=str(self.root), names=names, options=options)

    def test_sequence_natural_order_preserve_extensions_apply_and_undo(self):
        self.write('截圖10.PNG', 'ten'); self.write('截圖2.jpg', 'two')
        result = self.preview(['截圖10.PNG', '截圖2.jpg'], mode='sequence', base='旅遊', start=7, digits=3)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['entries'], [{'old': '截圖2.jpg', 'new': '旅遊_007.jpg'}, {'old': '截圖10.PNG', 'new': '旅遊_008.PNG'}])
        applied = self.post('apply', token=result.json['token']); self.assertEqual(applied.status_code, 200, applied.json)
        self.assertEqual(self.root.joinpath('旅遊_007.jpg').read_text(), 'two')
        # Simulate reopening the app: the journal is on disk, no memory plan needed.
        rename_api._plans.clear()
        undone = self.post('undo', id=applied.json['id']); self.assertEqual(undone.status_code, 200, undone.json)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'截圖2.jpg', '截圖10.PNG'})
        self.assertEqual(self.root.joinpath('截圖10.PNG').read_text(), 'ten')

    def test_replace_prefix_suffix_and_modified_date(self):
        self.write('old_1.txt', 'original')
        result = self.preview(['old_1.txt'], find='old', replace='new', prefix='前_', suffix='_後', date='modified')
        date = rename_api.datetime.fromtimestamp(self.root.joinpath('old_1.txt').stat().st_mtime).strftime('%Y%m%d')
        self.assertEqual(result.json['entries'][0]['new'], f'前_{date}_new_1_後.txt')

    def test_conflicts_invalid_names_paths_and_changed_source_rejected(self):
        self.write('a.txt', 'one'); self.write('b.txt', 'two')
        for options in ({'find': 'a', 'replace': 'b'}, {'prefix': '../'}, {'mode': 'sequence', 'base': 'CON', 'digits': True}, {'mode': 'bad'}, {'suffix': ':'}):
            with self.subTest(options=options): self.assertEqual(self.preview(['a.txt'], **options).status_code, 400)
        self.assertEqual(self.preview(['../a.txt']).status_code, 400)
        self.assertEqual(self.post('list', folder='relative').status_code, 400)
        preview = self.preview(['a.txt'], prefix='new_')
        self.write('a.txt', 'changed')
        self.assertEqual(self.post('apply', token=preview.json['token']).status_code, 400)
        self.assertEqual(self.root.joinpath('a.txt').read_text(), 'changed')

    def test_preview_is_single_use_and_new_destination_blocks_apply(self):
        self.write('a.txt', 'one')
        preview = self.preview(['a.txt'], prefix='new_')
        self.write('new_a.txt', 'unrelated')
        self.assertEqual(self.post('apply', token=preview.json['token']).status_code, 400)
        self.assertEqual(self.post('apply', token=preview.json['token']).status_code, 400)
        self.assertEqual(self.root.joinpath('new_a.txt').read_text(), 'unrelated')

    def test_case_only_rename_and_swaps_keep_contents(self):
        self.write('a.txt', 'one'); self.write('b.txt', 'two')
        root = self.root.resolve()
        entries = [dict(old='a.txt', new='b.txt', identity=rename_api.identity(root / 'a.txt')), dict(old='b.txt', new='a.txt', identity=rename_api.identity(root / 'b.txt'))]
        journal = self.history / 'swap.json'; self.history.mkdir()
        with app.app_context(): rename_api.transact(root, entries, journal, {})
        self.assertEqual((root / 'b.txt').read_text(), 'one'); self.assertEqual((root / 'a.txt').read_text(), 'two')
        preview = self.preview(['a.txt'], find='a', replace='A')
        applied = self.post('apply', token=preview.json['token']); self.assertEqual(applied.status_code, 200, applied.json)
        self.assertIn('A.txt', [p.name for p in root.iterdir()])
        self.assertEqual(self.post('undo', id=applied.json['id']).status_code, 200)

    def test_partial_failure_rolls_back_all_files(self):
        self.write('a.txt', 'one'); self.write('b.txt', 'two')
        preview = self.preview(['a.txt', 'b.txt'], prefix='new_')
        original = rename_api.move_no_replace
        counter = 0
        def fail_once(source, target):
            nonlocal counter
            counter += 1
            if counter == 4: raise PermissionError('test-only locked file')
            return original(source, target)
        with patch.object(rename_api, 'move_no_replace', side_effect=fail_once): result = self.post('apply', token=preview.json['token'])
        self.assertEqual(result.status_code, 400)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'a.txt', 'b.txt'})
        self.assertEqual((self.root / 'a.txt').read_text(), 'one')
        self.assertEqual((self.root / 'b.txt').read_text(), 'two')

    def test_undo_failure_remains_retryable_and_changed_content_is_protected(self):
        self.write('a.txt', 'one'); self.write('b.txt', 'two')
        preview = self.preview(['a.txt', 'b.txt'], prefix='new_')
        applied = self.post('apply', token=preview.json['token'])
        original = rename_api.move_no_replace
        counter = 0
        def fail_once(source, target):
            nonlocal counter
            counter += 1
            if counter == 3: raise PermissionError('test-only locked file')
            return original(source, target)
        with patch.object(rename_api, 'move_no_replace', side_effect=fail_once): result = self.post('undo', id=applied.json['id'])
        self.assertEqual(result.status_code, 400)
        record = json.loads((self.history / f"{applied.json['id']}.json").read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'completed')
        self.write('new_a.txt', 'changed after rename')
        self.assertEqual(self.post('undo', id=applied.json['id']).status_code, 400)
        self.assertEqual((self.root / 'new_a.txt').read_text(), 'changed after rename')

    def test_interrupted_operation_recovery_from_disk(self):
        self.write('a.txt', 'one'); self.write('b.txt', 'two')
        identities = [rename_api.identity(self.root / name) for name in ['a.txt', 'b.txt']]
        os.rename(self.root / 'a.txt', self.root / '.test-staged.tmp')
        os.rename(self.root / 'b.txt', self.root / 'new_b.txt')
        record_id = '1' * 32; self.history.mkdir()
        record = dict(id=record_id, folder=str(self.root), status='running', operation='apply', created='2026-10-01', entries=[], active=[dict(old='a.txt', new='new_a.txt', temporary='.test-staged.tmp', identity=identities[0]), dict(old='b.txt', new='new_b.txt', temporary='.test-other.tmp', identity=identities[1])])
        (self.history / f'{record_id}.json').write_text(json.dumps(record), encoding='utf-8')
        result = self.post('recover', id=record_id); self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'a.txt', 'b.txt'})
        self.assertEqual((self.root / 'b.txt').read_text(), 'two')

    def test_cross_origin_and_missing_token_cannot_access_files(self):
        self.assertEqual(self.client.post('/api/rename/list', json={'folder': str(self.root)}).status_code, 403)
        headers = self.headers | {'Origin': 'https://example.com'}
        self.assertEqual(self.client.post('/api/rename/list', json={'folder': str(self.root)}, headers=headers).status_code, 403)
        self.assertEqual(self.client.get('/api/rename/history', headers=self.headers, base_url='http://attacker.example').status_code, 403)
        self.assertEqual(self.client.post('/api/rename/list', json={'folder': str(self.root)}, headers=self.headers | {'Origin': 'http://localhost:8000'}).status_code, 403)

    def test_hardlinks_and_reserved_names_are_rejected(self):
        self.write('a.txt', 'one'); os.link(self.root / 'a.txt', self.root / 'linked.txt')
        self.assertEqual(self.preview(['a.txt', 'linked.txt'], prefix='new_').status_code, 400)
        for name in ('CON.txt', 'COM¹.txt', 'NUL .txt', 'trailing.'):
            with self.subTest(name=name), self.assertRaises(rename_api.RenameError): rename_api.valid_name(name)


if __name__ == '__main__': unittest.main()

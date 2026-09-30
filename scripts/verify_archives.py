"""Verify release CRCs/hashes, current frontend assets, and public patch baseline."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from updater import auto_updater


def digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(chunk)
    return result.hexdigest()


def main():
    version = json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))['version']
    manifest = json.loads((ROOT / f'build_manifest_v{version}.json').read_text(encoding='utf-8'))
    base = json.loads((ROOT / 'build_manifest_v1.0.1.json').read_text(encoding='utf-8'))
    prefix = auto_updater.APP_NAME + '/'
    report = {'version': version, 'base_version': '1.0.1', 'files': len(manifest), 'assets': []}
    for suffix in ('', '_patch'):
        path = ROOT / f'小黑工具箱_v{version}{suffix}.zip'
        with zipfile.ZipFile(path) as archive:
            with patch.object(auto_updater, 'get_current_version', return_value='1.0.1'):
                auto_updater._validate_archive(archive, version, bool(suffix))
            for entry in archive.infolist():
                relative = entry.filename.removeprefix(prefix)
                with archive.open(entry) as stream:
                    actual = digest(stream)  # ZipFile validates CRC while reading.
                if relative == 'patch_info.json':
                    continue
                assert actual == manifest[relative], relative
            if not suffix:
                assert set(archive.namelist()) == {prefix + name for name in manifest}
                for directory in ('templates', 'static'):
                    for source in ROOT.joinpath(directory).rglob('*'):
                        if source.is_file():
                            relative = '_internal/' + source.relative_to(ROOT).as_posix()
                            with source.open('rb') as stream:
                                assert digest(stream) == manifest[relative], relative
            else:
                required = {prefix + name for name, value in manifest.items() if base.get(name) != value}
                assert required <= set(archive.namelist()), 'Patch is missing changed files'
        with path.open('rb') as stream:
            sha256 = digest(stream)
        report['assets'].append({'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha256})
        print(f'{path.name}: CRC, hashes and version passed', flush=True)
    destination = ROOT / 'build/verification/archive-report.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

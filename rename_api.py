"""Previewed, journaled renames of regular files inside one local directory."""
import ctypes
import json
import os
import re
import secrets
import stat
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

rename_tools = Blueprint('rename_tools', __name__)
_lock = threading.RLock()
_plans = {}
MAX_FILES = 1000
MAX_PLAN_AGE = 15 * 60


class RenameError(ValueError):
    pass


@rename_tools.errorhandler(RenameError)
def invalid(error):
    return jsonify(error=str(error)), 400


@rename_tools.errorhandler(OSError)
def filesystem_error(error):
    return jsonify(error=f'無法操作檔案：{error.strerror or str(error)}'), 400


@rename_tools.before_request
def local_request():
    if not request.path.startswith('/api/rename/'):
        return
    expected = current_app.config['LOCAL_ACTION_TOKEN']
    host = request.host.split(':')[0].lower()
    origin = request.headers.get('Origin')
    if host not in ('127.0.0.1', 'localhost'):
        return jsonify(error='請從本機工具箱頁面操作檔案'), 403
    # Some desktop browser bridges normalize loopback Origin without its port.
    # The unpredictable per-process token remains mandatory for every request.
    accepted_origins = {request.host_url.rstrip('/'), f'{request.scheme}://{host}'}
    if origin and origin not in accepted_origins:
        current_app.logger.warning('Rejected file action Origin %s (expected %s)', origin, request.host_url.rstrip('/'))
        return jsonify(error='拒絕來自其他網站的檔案操作'), 403
    if not secrets.compare_digest(request.headers.get('X-Toolbox-Token', ''), expected):
        return jsonify(error='頁面授權已過期，請重新整理工具頁面後重試'), 403
    if request.method == 'POST' and not request.is_json:
        return jsonify(error='請使用工具箱的操作介面'), 415


def state_dir():
    override = current_app.config.get('RENAME_STATE_DIR') or os.getenv('TOOLBOX_RENAME_STATE_DIR')
    directory = Path(override) if override else Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / '小黑工具箱' / 'rename-history'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def folder_path(value):
    if not isinstance(value, str) or not value.strip():
        raise RenameError('請選擇資料夾，或貼上完整資料夾路徑')
    raw = value.strip().strip('"')
    candidate = Path(raw)
    if not candidate.is_absolute() or raw.startswith(('\\\\', '//')):
        raise RenameError('請使用本機資料夾的完整路徑')
    if candidate.is_symlink():
        raise RenameError('請選擇實際資料夾，不使用資料夾連結')
    root = candidate.resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor):
        raise RenameError('請選擇包含檔案的資料夾，不使用磁碟根目錄')
    for key in ('WINDIR', 'ProgramFiles', 'ProgramFiles(x86)'):
        protected = os.getenv(key)
        if protected and root.is_relative_to(Path(protected).resolve()):
            raise RenameError('請選擇自己的檔案資料夾，不操作系統或程式安裝目錄')
    return root


def identity(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise RenameError(f'{path.name} 不是可改名的一般檔案')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def valid_name(name):
    if (not name or len(name.encode('utf-16-le')) // 2 > 255 or
            re.search(r'[\x00-\x1f<>:"/\\|?*]', name) or name.endswith((' ', '.')) or
            name.split('.')[0].rstrip(' .').upper() in {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in '123456789¹²³'], *[f'LPT{i}' for i in '123456789¹²³']}):
        raise RenameError(f'檔名無效：{name[:80] or "空白檔名"}')


def natural_key(value):
    return [(0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r'(\d+)', value)]


def files_in(root):
    entries = sorted(root.iterdir(), key=lambda path: natural_key(path.name))
    files = []
    for path in entries:
        try:
            ident = identity(path)
        except RenameError:
            continue
        files.append(dict(name=path.name, size=ident[2], identity=ident))
        if len(files) > MAX_FILES:
            raise RenameError(f'資料夾最多 {MAX_FILES} 個檔案，請先分批整理')
    return files


def data():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise RenameError('操作設定格式錯誤')
    return value


@rename_tools.get('/tool/batch-rename')
def page():
    return render_template('batch_rename.html')


@rename_tools.post('/api/rename/list')
def list_files():
    root = folder_path(data().get('folder'))
    return jsonify(folder=str(root), files=[{k: v for k, v in item.items() if k != 'identity'} for item in files_in(root)])


def integer(options, key, default, low, high):
    value = options.get(key, default)
    if type(value) is not int or not low <= value <= high:
        raise RenameError(f'{key} 必須是 {low} 到 {high} 的整數')
    return value


def make_plan(root, names, options):
    if not isinstance(names, list) or not 1 <= len(names) <= MAX_FILES or any(not isinstance(n, str) for n in names):
        raise RenameError('請選擇要改名的檔案')
    if len({n.casefold() for n in names}) != len(names):
        raise RenameError('檔案不能重複選取')
    files = {entry['name']: entry for entry in files_in(root)}
    if any(name not in files for name in names):
        raise RenameError('檔案清單已變更，請重新讀取資料夾')
    if len({tuple(files[name]['identity'][:2]) for name in names}) != len(names):
        raise RenameError('選取的檔案含有指向同一檔案的硬連結，請分開處理')
    if not isinstance(options, dict):
        raise RenameError('改名設定格式錯誤')
    for key in ('prefix', 'suffix', 'find', 'replace', 'base'):
        if not isinstance(options.get(key, ''), str) or len(options.get(key, '')) > 150:
            raise RenameError('命名文字最多 150 個字元')
    start = integer(options, 'start', 1, 0, 999999)
    digits = integer(options, 'digits', 3, 1, 6)
    mode = options.get('mode', 'keep')
    date_mode = options.get('date', 'none')
    if mode not in ('keep', 'sequence') or date_mode not in ('none', 'today', 'modified'):
        raise RenameError('命名模式無效')
    if mode == 'sequence' and not options.get('base', '').strip():
        raise RenameError('請輸入流水號的基本名稱')
    plans = []
    for index, name in enumerate(sorted(names, key=natural_key)):
        path = root / name
        stem, extension = os.path.splitext(name)
        if mode == 'sequence':
            stem = f"{options['base']}_{start + index:0{digits}d}"
        elif options.get('find'):
            stem = stem.replace(options['find'], options.get('replace', ''))
        if date_mode != 'none':
            date = datetime.now() if date_mode == 'today' else datetime.fromtimestamp(path.stat().st_mtime)
            stem = date.strftime('%Y%m%d') + '_' + stem
        new = options.get('prefix', '') + stem + options.get('suffix', '') + extension
        valid_name(new)
        plans.append(dict(old=name, new=new, identity=files[name]['identity']))
    changed = [entry for entry in plans if entry['old'] != entry['new']]
    targets = [entry['new'].casefold() for entry in plans]
    if len(set(targets)) != len(targets):
        raise RenameError('產生了重複檔名，請調整命名規則')
    sources = {entry['old'].casefold() for entry in changed}
    occupied = {path.name.casefold() for path in root.iterdir()} - sources
    if any(entry['new'].casefold() in occupied for entry in changed):
        raise RenameError('新檔名與未選取的檔案或資料夾重名，請調整命名規則')
    return plans


@rename_tools.post('/api/rename/preview')
def preview():
    value = data()
    root = folder_path(value.get('folder'))
    with _lock:
        plan = make_plan(root, value.get('names'), value.get('options', {}))
        token = secrets.token_urlsafe(24)
        now = time.time()
        for key in list(_plans):
            if now - _plans[key]['created'] > MAX_PLAN_AGE:
                del _plans[key]
        if len(_plans) >= 100:
            del _plans[next(iter(_plans))]
        _plans[token] = dict(folder=str(root), entries=plan, created=now)
    return jsonify(token=token, entries=[dict(old=e['old'], new=e['new']) for e in plan], changed=sum(e['old'] != e['new'] for e in plan))


def journal_save(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def move_no_replace(source, destination):
    # os.rename on Windows fails if a destination exists; never use replace.
    if destination.exists():
        raise RenameError(f'檔名已存在：{destination.name}')
    os.rename(source, destination)


def transact(root, entries, journal, record):
    """Stage all names first, allowing swaps and case-only changes without overwrite."""
    for entry in entries:
        valid_name(entry['old']); valid_name(entry['new'])
        if identity(root / entry['old']) != entry['identity']:
            raise RenameError(f"{entry['old']} 已變更，請重新預覽")
    sources = {e['old'].casefold() for e in entries}
    occupied = {path.name.casefold() for path in root.iterdir()} - sources
    if any(e['new'].casefold() in occupied for e in entries):
        raise RenameError('目的檔名已存在，尚未改名；請重新預覽')
    steps = []
    previous_status = record.get('status', 'planned')
    record['active'] = [dict(e, temporary=f'.toolbox-{secrets.token_hex(16)}.tmp', position='old') for e in entries]
    record['status'] = 'running'
    journal_save(journal, record)  # Fail before touching files if journal is unwritable.
    try:
        for entry in record['active']:
            source, target = root / entry['old'], root / entry['temporary']
            if identity(source) != entry['identity']:
                raise RenameError('檔案在改名時變更，正在還原原始名稱')
            move_no_replace(source, target); steps.append((source, target))
            entry['position'] = 'temporary'; journal_save(journal, record)
        for entry in record['active']:
            source, target = root / entry['temporary'], root / entry['new']
            move_no_replace(source, target); steps.append((source, target))
            entry['position'] = 'new'; journal_save(journal, record)
    except Exception as error:
        failures = []
        for source, target in reversed(steps):
            try:
                move_no_replace(target, source)
            except Exception:
                failures.append(str(target))
        record['status'] = 'needs-recovery' if failures else ('completed' if previous_status == 'completed' else 'rolled-back')
        record['recovery_files'] = failures
        journal_save(journal, record)
        if failures:
            raise RenameError(f'改名中斷，部分檔案需復原。復原紀錄：{journal}') from error
        raise RenameError('改名未完成，已還原原始檔名；請確認檔案未被其他程式使用') from error


@rename_tools.post('/api/rename/apply')
def apply():
    token = data().get('token')
    if not isinstance(token, str):
        raise RenameError('請先產生改名預覽')
    with _lock:
        plan = _plans.pop(token, None)
        if not plan or time.time() - plan['created'] > MAX_PLAN_AGE:
            raise RenameError('預覽已過期，請重新預覽後再執行')
        entries = [e for e in plan['entries'] if e['old'] != e['new']]
        if not entries:
            raise RenameError('沒有需要改名的檔案')
        root = folder_path(plan['folder'])
        record_id = secrets.token_hex(16)
        journal = state_dir() / f'{record_id}.json'
        record = dict(id=record_id, folder=str(root), entries=entries, operation='apply', created=datetime.now().isoformat(timespec='seconds'))
        transact(root, entries, journal, record)
        record['status'] = 'completed'; journal_save(journal, record)
    return jsonify(success=True, count=len(entries), id=record_id)


def records():
    result = []
    for path in state_dir().glob('*.json'):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            if re.fullmatch(r'[a-f0-9]{32}', value['id']):
                result.append(value)
        except (ValueError, KeyError, OSError):
            continue
    return sorted(result, key=lambda r: r['created'], reverse=True)


@rename_tools.get('/api/rename/history')
def history():
    return jsonify(records=[{key: value.get(key) for key in ('id', 'folder', 'created', 'status')} | {'count': len(value.get('entries', []))} for value in records()][:30])


@rename_tools.post('/api/rename/undo')
def undo():
    record_id = data().get('id')
    if not isinstance(record_id, str) or not re.fullmatch(r'[a-f0-9]{32}', record_id):
        raise RenameError('復原紀錄無效')
    with _lock:
        journal = state_dir() / f'{record_id}.json'
        if not journal.is_file():
            raise RenameError('找不到復原紀錄')
        record = json.loads(journal.read_text(encoding='utf-8'))
        if record['status'] != 'completed':
            raise RenameError('這筆紀錄無法直接復原，請查看紀錄中的檔案狀態')
        root = folder_path(record['folder'])
        entries = [dict(old=e['new'], new=e['old'], identity=e['identity']) for e in record['entries']]
        # Refuse undo if content changed or original names are now occupied.
        record['operation'] = 'undo'
        transact(root, entries, journal, record)
        record['status'] = 'undone'; journal_save(journal, record)
    return jsonify(success=True, count=len(entries), folder=str(root))


@rename_tools.post('/api/rename/recover')
def recover():
    """Recover an interrupted apply/undo using recorded file identities."""
    record_id = data().get('id')
    if not isinstance(record_id, str) or not re.fullmatch(r'[a-f0-9]{32}', record_id):
        raise RenameError('復原紀錄無效')
    with _lock:
        journal = state_dir() / f'{record_id}.json'
        if not journal.is_file():
            raise RenameError('找不到復原紀錄')
        record = json.loads(journal.read_text(encoding='utf-8'))
        if record['status'] not in ('running', 'needs-recovery'):
            raise RenameError('這筆紀錄不需要中斷復原')
        root = folder_path(record['folder'])
        entries = []
        # Desired state: the original names of the interrupted operation.
        for active in record['active']:
            for name in (active['old'], active['temporary'], active['new']):
                valid_name(name)
            matches = {}
            for name in (active['old'], active['temporary'], active['new']):
                path = root / name
                try:
                    if identity(path) == active['identity']:
                        matches[os.path.normcase(str(path))] = path.name
                except (OSError, RenameError):
                    pass
            if len(matches) != 1:
                raise RenameError(f"無法確認 {active['old']} 的位置或內容，請查看復原紀錄：{journal}")
            original = next((entry for entry in record['entries'] if entry['identity'] == active['identity']), None)
            destination = (original['new'] if record.get('operation') == 'undo' else original['old']) if original else active['old']
            entries.append(dict(old=next(iter(matches.values())), new=destination, identity=active['identity']))
        # Include already restored files as staged entries; cycles remain safe.
        operation = record.get('operation', 'apply')
        transact(root, entries, journal, record)
        record['status'] = 'completed' if operation == 'undo' else 'rolled-back'
        journal_save(journal, record)
    return jsonify(success=True, count=len(entries), folder=str(root))


@rename_tools.post('/api/rename/choose-folder')
def choose_folder():
    if os.name != 'nt':
        raise RenameError('請貼上完整資料夾路徑')
    from ctypes import wintypes
    class BrowseInfo(ctypes.Structure):
        _fields_ = [('hwndOwner', wintypes.HWND), ('pidlRoot', ctypes.c_void_p), ('pszDisplayName', wintypes.LPWSTR), ('lpszTitle', wintypes.LPCWSTR), ('ulFlags', wintypes.UINT), ('lpfn', ctypes.c_void_p), ('lParam', ctypes.c_void_p), ('iImage', ctypes.c_int)]
    shell, ole = ctypes.windll.shell32, ctypes.windll.ole32
    shell.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BrowseInfo)]
    shell.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoInitialize(None)
    try:
        display = ctypes.create_unicode_buffer(260)
        info = BrowseInfo(None, None, display, '選擇要批次改名的資料夾', 0x41, None, None, 0)
        pointer = shell.SHBrowseForFolderW(ctypes.byref(info))
        if not pointer:
            return jsonify(folder=None)
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            if not shell.SHGetPathFromIDListW(pointer, buffer):
                raise RenameError('無法讀取資料夾，請貼上完整路徑')
            return jsonify(folder=str(folder_path(buffer.value)))
        finally:
            ole.CoTaskMemFree(pointer)
    finally:
        ole.CoUninitialize()

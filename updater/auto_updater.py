"""
自動更新模組
檢查 GitHub Releases → 下載 ZIP → 解壓覆蓋程式檔案 → 重啟

移植自台股預測分析系統，針對 Flask Web App 調整。
"""
import json
import os
import ssl
import sys
import shutil
import subprocess
import tempfile
import zipfile
from urllib.request import urlopen, Request

# ── 路徑設定 ──────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    APP_ROOT = os.path.dirname(sys.executable)
else:
    APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── GitHub 設定 ───────────────────────────────────────────────────

GITHUB_OWNER = "littleblackmann"
GITHUB_REPO = "littleblacktoolbox"
APP_NAME = "小黑工具箱"

VERSION_FILE = os.path.join(APP_ROOT, "version.json")


def _get_ssl_context():
    """Use the system trust store and certifi when available."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx


def _urlopen_safe(req, timeout=30):
    """Never download executable updates without TLS certificate checks."""
    return urlopen(req, timeout=timeout, context=_get_ssl_context())


def _validate_archive(zf: zipfile.ZipFile, new_version: str, is_patch: bool) -> None:
    """Reject unsafe or incompatible releases before extracting any files."""
    prefix = APP_NAME + '/'
    names = set()
    total_size = 0
    for member in zf.infolist():
        name = member.filename.replace('\\', '/')
        parts = name.split('/')
        if (not name.startswith(prefix) or name.startswith('/') or
                any(part in ('', '.', '..') for part in parts[:-1]) or
                ':' in name or member.is_dir() and parts[-1] not in ('',)):
            raise ValueError('更新檔包含不安全的路徑')
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError('更新檔包含不支援的符號連結')
        key = name.casefold()
        if key in names:
            raise ValueError('更新檔包含重複檔案')
        names.add(key)
        total_size += member.file_size
        if total_size > 6 * 1024 * 1024 * 1024:
            raise ValueError('更新檔解壓後過大')
    if prefix + '_internal/version.json' not in zf.namelist():
        raise ValueError('更新檔缺少版本資訊')
    version = json.loads(zf.read(prefix + '_internal/version.json')).get('version')
    if version != new_version:
        raise ValueError('更新檔版本與 Release 不符')
    if is_patch:
        metadata_name = prefix + 'patch_info.json'
        if metadata_name not in zf.namelist():
            raise ValueError('差量更新缺少基準版本資訊')
        metadata = json.loads(zf.read(metadata_name))
        if (metadata.get('from_version') != get_current_version() or
                metadata.get('to_version') != new_version):
            raise ValueError('差量更新不適用於目前版本')


def get_current_version() -> str:
    """讀取本地版本號"""
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "version.json"))
    candidates.append(VERSION_FILE)

    found_versions = []
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                v = json.load(f).get("version", "0.0.0")
                if v != "0.0.0":
                    found_versions.append(v)
        except Exception:
            continue

    if not found_versions:
        return "0.0.0"

    try:
        return max(found_versions, key=lambda v: [int(x) for x in v.split(".")])
    except (ValueError, AttributeError):
        return found_versions[0]


def _is_newer(remote: str, local: str) -> bool:
    """比較版本號"""
    try:
        r_parts = [int(x) for x in remote.split(".")]
        l_parts = [int(x) for x in local.split(".")]
        return r_parts > l_parts
    except (ValueError, AttributeError):
        return remote != local


def check_for_update() -> dict | None:
    """
    檢查 GitHub Releases 是否有新版本。

    Returns:
        None: 已是最新版或無法連線
        dict: {"version", "download_url", "full_url", "is_patch", "release_notes"}
    """
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

    try:
        req = Request(api_url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "LittleBlackToolbox-Updater/1.0",
        })
        with _urlopen_safe(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    remote_version = data.get("tag_name", "").lstrip("v")
    current = get_current_version()

    if not remote_version or not _is_newer(remote_version, current):
        return None

    # 找 ZIP 下載連結（優先 patch）
    patch_url = None
    full_url = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith("_patch.zip"):
            patch_url = asset.get("browser_download_url")
        elif name.endswith(".zip"):
            full_url = asset.get("browser_download_url")

    download_url = patch_url or full_url
    if not download_url:
        return None

    is_patch = (download_url == patch_url)

    return {
        "version": remote_version,
        "download_url": download_url,
        "full_url": full_url,
        "is_patch": is_patch,
        "release_notes": data.get("body", ""),
    }


def download_and_apply(download_url: str, new_version: str,
                       progress_callback=None,
                       full_url: str = None,
                       is_patch: bool = False) -> bool:
    """
    下載 ZIP 並透過 bat 腳本覆蓋程式目錄、重啟。

    Returns:
        True: 更新腳本已啟動，需要退出程式
        False: 更新失敗
    """
    if not getattr(sys, 'frozen', False):
        return False

    tmp_dir = tempfile.mkdtemp(prefix="toolbox_update_")
    zip_path = os.path.join(tmp_dir, "update.zip")

    try:
        # ── 下載 ──
        req = Request(download_url, headers={
            "User-Agent": "LittleBlackToolbox-Updater/1.0",
        })
        with _urlopen_safe(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(zip_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

        # ── 解壓 ──
        extract_dir = os.path.join(tmp_dir, "extracted")
        with zipfile.ZipFile(zip_path, "r") as zf:
            _validate_archive(zf, new_version, is_patch)
            zf.extractall(extract_dir)

        # 找到實際程式根目錄（可能在子資料夾裡）
        contents = os.listdir(extract_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
            source_dir = os.path.join(extract_dir, contents[0])
        else:
            source_dir = extract_dir

        # ── 寫更新 bat 腳本 ──
        bat_path = os.path.join(tmp_dir, "apply_update.bat")
        exe_path = sys.executable if getattr(sys, "frozen", False) else "python"
        pid = os.getpid()

        with open(bat_path, "w", encoding="utf-8") as bat:
            bat.write(f"""@echo off
chcp 65001 >nul
echo ======================================
echo   小黑工具箱 — 正在更新...
echo ======================================
echo.

REM 等待主程式退出（最多 15 秒）
echo 等待程式結束 (PID={pid})...
set /a WAITED=0
:WAIT_LOOP
tasklist /FI "PID eq {pid}" 2>nul | find /i "{pid}" >nul
if errorlevel 1 goto PROCESS_DEAD
if %WAITED% GEQ 15 goto FORCE_KILL
timeout /t 1 /nobreak >nul
set /a WAITED+=1
goto WAIT_LOOP

:FORCE_KILL
echo 程式未自行結束，強制終止...
taskkill /F /PID {pid} >nul 2>&1
timeout /t 2 /nobreak >nul

:PROCESS_DEAD
echo 程式已結束，開始覆蓋檔案...

REM 覆蓋程式檔案
xcopy /E /Y /I "{source_dir}\\*" "{APP_ROOT}\\" >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 檔案覆蓋失敗！
    pause
    goto CLEANUP
)

REM 更新版本號
>"{os.path.join(APP_ROOT, "version.json")}" (
    echo {{"version": "{new_version}"}}
)

echo.
echo 更新完成！正在重新啟動...
start "" "{exe_path}"

:CLEANUP
REM 清理暫存
timeout /t 3 /nobreak >nul
rd /s /q "{tmp_dir}" >nul 2>&1
del "%~f0" >nul 2>&1
""")

        # ── 啟動更新腳本 ──
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True

    except Exception as e:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        # patch 失敗 → fallback 到 full
        if is_patch and full_url:
            return download_and_apply(
                full_url, new_version,
                progress_callback=progress_callback,
                full_url=None,
                is_patch=False,
            )

        return False

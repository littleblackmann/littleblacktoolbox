"""
小黑工具箱 — 打包腳本（PyInstaller）

使用方式：
    python build.py

輸出：
    dist/小黑工具箱/                    ← 整個資料夾給對方就能用
    小黑工具箱_vX.X.X.zip              ← 完整安裝包（新用戶）
    小黑工具箱_vX.X.X_patch.zip        ← 差量更新包（已安裝用戶）
"""
import os
import sys
import json
import hashlib
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

APP_NAME = "小黑工具箱"
SPEC_FILE = "build_exe.spec"
DIST_DIR = os.path.join("dist", APP_NAME)

# 版本號從 version.json 讀取
VERSION_FILE = "version.json"
try:
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        APP_VERSION = json.load(f).get("version", "0.0.0")
except Exception:
    APP_VERSION = "0.0.0"

OUTPUT_ZIP = f"小黑工具箱_v{APP_VERSION}.zip"
PATCH_ZIP = f"小黑工具箱_v{APP_VERSION}_patch.zip"
MANIFEST_SAVE = f"build_manifest_v{APP_VERSION}.json"


def check_env():
    """確認 PyInstaller 和必要套件都已安裝"""
    try:
        import PyInstaller
        print(f"  [OK] PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  [FAIL] 請先安裝 PyInstaller：pip install pyinstaller")
        return False

    ready = True
    for pkg in ['flask', 'rembg', 'easyocr', 'pypdf', 'cv2', 'cryptography']:
        try:
            __import__(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [FAIL] 缺少套件：{pkg}")
            ready = False

    try:
        import torch
        if torch.version.cuda is not None:
            print('  [FAIL] 打包請使用 CPU 版 PyTorch，避免收進數 GB 的 CUDA 函式庫')
            ready = False
    except ImportError:
        print('  [FAIL] 缺少 PyTorch')
        ready = False

    model_root = Path.home() / '.EasyOCR' / 'model'
    required_models = ('craft_mlt_25k.pth', 'chinese.pth', 'english_g2.pth',
                       'zh_sim_g2.pth', 'japanese_g2.pth', 'korean_g2.pth')
    for model in required_models:
        if not (model_root / model).is_file():
            print(f"  [FAIL] 缺少 OCR 模型：{model_root / model}")
            ready = False
    birefnet = Path.home() / '.u2net' / 'birefnet-general.onnx'
    if not birefnet.is_file():
        print(f"  [FAIL] 缺少去背模型：{birefnet}")
        ready = False
    return ready


# ── 差量更新工具 ─────────────────────────────────────────────────

def _hash_file(filepath: str) -> str:
    """計算檔案 SHA256"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(dist_dir: str) -> dict:
    """掃描 dist 資料夾，產生 {相對路徑: sha256} 的 manifest"""
    manifest = {}
    for root, _dirs, files in os.walk(dist_dir):
        for fname in files:
            filepath = os.path.join(root, fname)
            relpath = os.path.relpath(filepath, dist_dir).replace("\\", "/")
            manifest[relpath] = _hash_file(filepath)
    return manifest


def _find_previous_manifest(current_version: str, base_version: str | None = None) -> tuple:
    """找到上一個版本的 manifest 作為 patch 基準線"""
    import glob

    best_manifest = {}
    best_version = None
    current_parts = tuple(int(x) for x in current_version.split("."))

    if base_version:
        if not all(part.isdigit() for part in base_version.split('.')):
            raise ValueError('基準版本格式錯誤')
        if tuple(int(x) for x in base_version.split('.')) >= current_parts:
            raise ValueError('基準版本必須低於新版本')
        path = Path(f'build_manifest_v{base_version}.json')
        if not path.is_file():
            raise ValueError(f'找不到指定基準：{path}')
        return json.loads(path.read_text(encoding='utf-8')), base_version

    for path in glob.glob("build_manifest_v*.json"):
        fname = os.path.basename(path)
        ver = fname.replace("build_manifest_v", "").replace(".json", "")
        if ver == current_version:
            continue
        try:
            ver_tuple = tuple(int(x) for x in ver.split("."))
        except ValueError:
            continue
        if ver_tuple >= current_parts:
            continue
        if best_version is None or ver_tuple > best_version:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    best_manifest = json.load(f)
                best_version = ver_tuple
                best_path = path
            except Exception:
                continue

    if best_manifest:
        print(f"  載入基準 manifest：{best_path}（{len(best_manifest)} 個檔案）")

    return best_manifest, '.'.join(str(x) for x in best_version) if best_version else None


def create_patch_zip(dist_dir: str, old_manifest: dict, new_manifest: dict,
                     base_version: str) -> str | None:
    """比對新舊 manifest，只把有變動的檔案打成 patch zip"""
    changed = []
    for relpath, new_hash in new_manifest.items():
        if relpath not in old_manifest or old_manifest[relpath] != new_hash:
            changed.append(relpath)

    # 強制包含 version.json
    for key in ["version.json", "_internal/version.json"]:
        if key not in changed and key in new_manifest:
            changed.append(key)
            print(f"  [PATCH] 強制加入 {key}")

    if not changed:
        print("  [PATCH] 與上次打包完全相同，不產生 patch")
        return None

    with zipfile.ZipFile(PATCH_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(f"{APP_NAME}/patch_info.json", json.dumps({
            "from_version": base_version,
            "to_version": APP_VERSION,
        }, ensure_ascii=False))
        for relpath in changed:
            filepath = os.path.join(dist_dir, relpath)
            arcname = os.path.join(APP_NAME, relpath)
            zf.write(filepath, arcname)

    patch_size = os.path.getsize(PATCH_ZIP) / 1024 / 1024
    print(f"  [PATCH] 差量更新包：{PATCH_ZIP}  ({patch_size:.1f} MB)")
    print(f"  [PATCH] 變動檔案數：{len(changed)} / {len(new_manifest)}")

    return PATCH_ZIP


# ── 主打包流程 ───────────────────────────────────────────────────

def build(base_version=None):
    print("=" * 60)
    print(f"  小黑工具箱 打包建置")
    print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  版本：v{APP_VERSION}")
    print("=" * 60)

    print("\n[0/4] 環境確認...")
    if not check_env():
        return False

    old_manifest, base_version = _find_previous_manifest(APP_VERSION, base_version)

    # Preserve the previous distribution so a failed build can be rolled back.
    if os.path.exists(DIST_DIR):
        dist_root = Path('dist').resolve()
        previous = Path(DIST_DIR).resolve()
        if previous.parent != dist_root:
            raise ValueError(f"輸出目錄不在 dist 中：{previous}")
        backup = dist_root / f"{APP_NAME}_backup_{datetime.now():%Y%m%d_%H%M%S}"
        print(f"\n  保留舊版本：{backup}")
        os.replace(previous, backup)

    print("\n[1/4] PyInstaller 打包中（約需 5～15 分鐘）...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", SPEC_FILE, "--noconfirm", "--clean"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

    if result.returncode != 0:
        print("\n[FAIL] 打包失敗！請查看上方錯誤訊息。")
        return False

    # ── 產生 manifest ──
    print("\n[2/4] 產生檔案清單 (manifest)...")
    new_manifest = generate_manifest(DIST_DIR)
    print(f"  共 {len(new_manifest)} 個檔案")

    manifest_in_dist = os.path.join(DIST_DIR, "manifest.json")
    with open(manifest_in_dist, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False)

    new_manifest["manifest.json"] = _hash_file(manifest_in_dist)

    # ── 差量更新包 ──
    if old_manifest:
        create_patch_zip(DIST_DIR, old_manifest, new_manifest, base_version)
    else:
        print("  [PATCH] 找不到前一版 manifest，無法產生差量更新包（首次打包正常）")

    # 儲存本次 manifest
    with open(MANIFEST_SAVE, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False)

    # ── 完整安裝包 ──
    print(f"\n[3/4] 壓縮完整安裝包 {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(DIST_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, "dist")
                zf.write(filepath, arcname)

    zip_size = os.path.getsize(OUTPUT_ZIP) / 1024 / 1024

    print(f"\n{'=' * 60}")
    print(f"[OK] 打包完成！")
    print(f"   資料夾：{DIST_DIR}")
    print(f"   完整包：{OUTPUT_ZIP}  ({zip_size:.0f} MB)")
    if os.path.exists(PATCH_ZIP):
        patch_size = os.path.getsize(PATCH_ZIP) / 1024 / 1024
        print(f"   差量包：{PATCH_ZIP}  ({patch_size:.1f} MB)")
    print(f"\n[NOTE] 上傳 Release 時，full + patch 都上傳：")
    print(f'   gh release create v{APP_VERSION} "{OUTPUT_ZIP}" "{PATCH_ZIP}" --title "v{APP_VERSION}" --notes "更新內容"')
    print(f"{'=' * 60}")

    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='建置小黑工具箱與差量更新包')
    parser.add_argument('--base-version', help='指定已公開 Release 的差量更新基準版本')
    sys.exit(0 if build(parser.parse_args().base_version) else 1)

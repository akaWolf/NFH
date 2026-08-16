"""Where the port's files live — in the repo checkout and in a frozen
bundle (PyInstaller onedir, tools/nfh.spec).

Two roots:

- the DATA root: `levels/*.json` and the `tools/` package are the port's
  own files (checked into the repo); the bundle ships them inside its
  program directory (`sys._MEIPASS`).
- the ASSET root: `textures/`, `audio/`, `strings/`, `fonts/` are
  extracted from the user's apk/obb and are never in the repo; they live
  next to the executable (so the bundle stays portable) — `NFH_ASSETS`
  overrides. In a checkout both roots are the repo root, which is why
  every module used to derive one ROOT; the bundle is where they split.
"""
import os, sys


def is_frozen():
    return bool(getattr(sys, 'frozen', False))


def bundle_dir():
    """the directory holding the executable (the user-facing folder of a
    onedir bundle — the extracted assets sit here)"""
    return os.path.dirname(os.path.abspath(sys.executable))


def data_root():
    """levels/ and tools/ — bundled data when frozen, the repo otherwise"""
    if is_frozen():
        return getattr(sys, '_MEIPASS', bundle_dir())
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def levels_root():
    """levels/<season>/*.json — the repo's own exports in a checkout;
    a frozen bundle generates them next to the executable on first run
    (tools/extract_assets.export_levels), so they live with the assets"""
    if is_frozen():
        return asset_root()
    return data_root()


def asset_root():
    """textures/, audio/, strings/, fonts/ — next to the executable when
    frozen (NFH_ASSETS overrides), the repo otherwise"""
    env = os.environ.get('NFH_ASSETS')
    if env:
        return env
    if is_frozen():
        return bundle_dir()
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

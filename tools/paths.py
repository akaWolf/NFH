"""Where the unpacked game data lives.

Override with NFH_DATA=/somewhere (the directory tools/extract.sh wrote to).
"""
import os, glob, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get('NFH_DATA', os.path.join(ROOT, 'data'))

APK = os.path.join(DATA, 'apk', 'assets', 'bin', 'Data')
OBB = os.path.join(DATA, 'obb', 'assets', 'bin', 'Data')

DLL = os.path.join(APK, 'Managed', 'Assembly-CSharp.dll')
GG_ASSETS = os.path.join(APK, 'globalgamemanagers.assets')   # holds the MonoScripts
GG = os.path.join(APK, 'globalgamemanagers')                 # holds BuildSettings


def scene_files():
    """level0..levelN in build order; level0 ships in the APK, the rest in the OBB."""
    fs = glob.glob(os.path.join(OBB, 'level*')) + glob.glob(os.path.join(APK, 'level*'))
    fs = [p for p in fs if re.fullmatch(r'level\d+', os.path.basename(p))]
    return sorted(fs, key=lambda p: int(os.path.basename(p)[5:]))


def asset_files():
    """the GUID-named serialized files that hold textures, audio and text assets"""
    return [p for p in glob.glob(os.path.join(OBB, '*'))
            if re.fullmatch(r'[0-9a-f]{32}', os.path.basename(p))]


def check():
    missing = [p for p in (DLL, GG_ASSETS, GG) if not os.path.exists(p)]
    if missing:
        raise SystemExit('missing %s\nrun tools/extract.sh first, or set NFH_DATA'
                         % ', '.join(missing))

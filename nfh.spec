# PyInstaller spec — the Linux/Windows bundle (docs/ROADMAP.md item 3).
#
#     pyinstaller --clean --noconfirm nfh.spec
#
# A onedir bundle: the executable plus the port's own data (levels/*.json,
# the tools/ extraction package) inside the program directory; the game's
# extracted assets (textures/, audio/, strings/, fonts/) live NEXT TO the
# executable and are produced on first run from the user's apk/obb
# (runtime/app.py's bootstrap — the game data is not distributable).
#
# SDL2/SDL2_mixer/SDL2_ttf come from the pysdl2-dll wheel when installed
# (the CI does), so the bundle carries its own libraries; without it the
# target machine's SDL is found at runtime as usual.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = os.path.abspath(SPECPATH)

datas = [(os.path.join(root, 'levels'), 'levels'),
         (os.path.join(root, 'tools'), 'tools')]
binaries = []
hiddenimports = ['sdl2.sdlmixer', 'sdl2.sdlttf', 'PIL.Image']
try:
    import sdl2dll                        # pysdl2-dll: the bundled SDL libs
    datas += collect_data_files('sdl2dll')
    binaries += collect_dynamic_libs('sdl2dll')
    hiddenimports.append('sdl2dll')
except ImportError:
    pass

a = Analysis(
    [os.path.join(root, 'runtime', 'app.py')],
    pathex=[os.path.join(root, 'runtime'), os.path.join(root, 'tools')],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=['tkinter', 'unittest', 'pydoc_data', 'test'],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='nfh',
    console=True,                         # the first-run extraction logs here
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='nfh',
)

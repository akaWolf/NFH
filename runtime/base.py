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


def sdl_open(title, width, height, headless=False):
    """SDL_Init(VIDEO) + the window + the renderer, each checked: an SDL
    that cannot reach a display (no libX11 for its x11 driver, DISPLAY
    unset, a video driver named wrong) fails SDL_Init with -1 and every
    later call returns NULL — unchecked, the app then runs its whole loop
    against a null renderer, headless and unpaced (no vsync to wait on),
    at 100% of a core with no window ever appearing: the "hang after the
    fonts" of the Linux bundle. Raises RuntimeError with SDL's own text."""
    import sdl2
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError('SDL_Init failed: %s' % sdl_error())
    flags = sdl2.SDL_WINDOW_HIDDEN if headless else sdl2.SDL_WINDOW_SHOWN
    win = sdl2.SDL_CreateWindow(title, sdl2.SDL_WINDOWPOS_CENTERED,
                                sdl2.SDL_WINDOWPOS_CENTERED, width, height,
                                flags)
    if not win:
        raise RuntimeError('SDL_CreateWindow failed: %s' % sdl_error())
    rnd = sdl2.SDL_CreateRenderer(
        win, -1, sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC)
    if not rnd:
        # no accelerated renderer (a bare X server, no GL): the software one
        rnd = sdl2.SDL_CreateRenderer(win, -1, sdl2.SDL_RENDERER_SOFTWARE)
    if not rnd:
        raise RuntimeError('SDL_CreateRenderer failed: %s' % sdl_error())
    return win, rnd


def sdl_error():
    import sdl2
    e = sdl2.SDL_GetError()
    return (e.decode('utf-8', 'replace') if isinstance(e, bytes) else str(e)) or 'no SDL error text'

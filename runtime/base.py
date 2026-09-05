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
import ctypes, os, sys


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
    drv = sdl2.SDL_GetCurrentVideoDriver()
    drv = drv.decode('utf-8', 'replace') if isinstance(drv, bytes) else str(drv or '')
    asked = os.environ.get('SDL_VIDEODRIVER')
    if drv in ('offscreen', 'dummy') and asked != drv and not headless:
        # SDL 2.0.22+ (the bundle ships 2.32) falls back to its offscreen
        # driver when no display driver comes up: SDL_Init returns 0, the
        # window is a buffer nobody shows, and the game then runs headless
        # at 100% of a core (no vsync to wait on) — the Linux bundle's
        # "hang". The offscreen fallback swallowed the real drivers'
        # errors, so ask each one again for its reason (x11: a libX*.so.6
        # SDL could not dlopen, no DISPLAY, no authorization; ...)
        sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_VIDEO)
        why = []
        for name in ('x11', 'wayland', 'KMSDRM'):
            try:
                ok = sdl2.SDL_VideoInit(name.encode()) == 0
            except Exception as e:
                why.append('%s: %s' % (name, e))
                continue
            if ok:
                sdl2.SDL_VideoQuit()
                why.append('%s: starts when named — set SDL_VIDEODRIVER=%s' % (name, name))
            else:
                why.append('%s: %s' % (name, sdl_error()))
        why.extend(_x11_probe())
        raise RuntimeError('no display: SDL fell back to its "%s" driver.\n%s'
                           % (drv, '\n'.join(why)))
    print('SDL video driver: %s' % drv, flush=True)
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
    try:
        info = sdl2.SDL_RendererInfo()
        if sdl2.SDL_GetRendererInfo(rnd, ctypes.byref(info)) == 0:
            print('SDL renderer: %s%s' % (
                info.name.decode('utf-8', 'replace') if isinstance(info.name, bytes) else info.name,
                '' if info.flags & sdl2.SDL_RENDERER_PRESENTVSYNC else ' (no vsync)'), flush=True)
    except Exception:
        pass
    return win, rnd


def sdl_error():
    import sdl2
    e = sdl2.SDL_GetError()
    return (e.decode('utf-8', 'replace') if isinstance(e, bytes) else str(e)) or 'no SDL error text'


def _x11_probe():
    """what SDL's x11 driver needs and does not say when it is "not
    available": DISPLAY, the X libraries it dlopens (libX11 and the
    extensions), and a connection to the server"""
    out = []
    disp = os.environ.get('DISPLAY')
    out.append('DISPLAY=%s' % (disp if disp else '(unset)'))
    missing = []
    for lib in ('libX11.so.6', 'libXext.so.6', 'libXcursor.so.1', 'libXi.so.6',
                'libXfixes.so.3', 'libXrandr.so.2', 'libXss.so.1'):
        try:
            ctypes.CDLL(lib)
        except OSError:
            missing.append(lib)
    if missing:
        out.append('X libraries SDL could not load: %s' % ', '.join(missing))
    if disp and 'libX11.so.6' not in missing:
        try:
            x = ctypes.CDLL('libX11.so.6')
            x.XOpenDisplay.restype = ctypes.c_void_p
            x.XOpenDisplay.argtypes = [ctypes.c_char_p]
            d = x.XOpenDisplay(None)
            if d:
                x.XCloseDisplay.argtypes = [ctypes.c_void_p]
                x.XCloseDisplay(d)
                out.append('XOpenDisplay(%s): ok' % disp)
            else:
                out.append('XOpenDisplay(%s): refused (no server there, or no '
                           'authorization — XAUTHORITY / xhost)' % disp)
        except Exception as e:
            out.append('XOpenDisplay: %s' % e)
    return out

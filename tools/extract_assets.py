"""Extract one season's runtime assets (textures, GUI sheets, audio,
strings, fonts) out of an unpacked data directory, then export its
scenes to levels/<season>/*.json — the extract_*.py + export_level.py
runs run.sh chains, callable in-process so the frozen bundle can do it
without a shell:

    python3 tools/extract_assets.py <data_dir> <out_root> <s1|s2>

`data_dir` is tools/unpack.py's output (apk/ + obb/); everything lands
under <out_root>/: textures/<season>, audio/<season>, strings/<season>,
fonts/<season>, levels/<season>.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths


def extract_season(data_dir, out_root, season, log=print):
    paths.set_data(data_dir)
    paths.check()
    import extract_textures, extract_gui, extract_audio, extract_strings
    tex = os.path.join(out_root, 'textures', season)
    log('extracting %s textures (a few minutes)...' % season)
    extract_textures.main(tex)
    pngs = sum(1 for n in os.listdir(tex) if n.endswith('.png'))
    if pngs < 10:
        # the per-texture excepts swallow a missing decoder wholesale
        raise SystemExit('texture extraction produced %d PNGs — the '
                         'decoder is broken (numpy missing?)' % pngs)
    log('extracting %s GUI sheets...' % season)
    extract_gui.main(tex, ('textures/gui/', 'textures/bubbles/',
                           'inventory/'))
    log('extracting %s audio...' % season)
    extract_audio.main(os.path.join(out_root, 'audio', season))
    log('extracting %s strings and fonts...' % season)
    extract_strings.main(os.path.join(out_root, 'strings', season),
                         os.path.join(out_root, 'fonts', season))
    export_levels(data_dir, out_root, season, log=log)
    log('%s assets ready under %s' % (season, out_root))


def export_levels(data_dir, out_root, season, log=print):
    """tools/export_level.py over every scene of the season: the file ->
    scene-name map comes from the build's own BuildSettings
    (load_scene_names); the parsed assembly/layouts are shared across the
    scenes. The module-level asset-name caches bind to one season's
    files, so they are reset when the season switches."""
    paths.set_data(data_dir)
    paths.check()
    # the running app has runtime/scene.py cached under the name
    # export_level's `from scene import Scene` wants (tools/scene.py) —
    # hand the import machinery ours, then put the app's back
    runtime_scene = sys.modules.pop('scene', None)
    try:
        import export_level
    finally:
        if runtime_scene is not None:
            sys.modules['scene'] = runtime_scene
    from cli_meta import Assembly
    from monodeser import Layouts
    from unityser import SerializedFile
    from assets import AssetIndex
    export_level.reset_season_caches()
    export_level.load_scene_names()
    out_dir = os.path.join(out_root, 'levels', season)
    os.makedirs(out_dir, exist_ok=True)
    asm = Assembly(paths.DLL)
    layouts = Layouts(asm)
    names = SerializedFile(paths.GG_ASSETS).mono_scripts()
    index = AssetIndex()
    log('exporting %s scenes...' % season)
    for p in paths.scene_files():
        base = os.path.basename(p)
        uname = export_level.SCENE_NAMES.get(base)
        name = os.path.splitext(os.path.basename(uname))[0] if uname else base
        export_level.export(p, os.path.join(out_dir, name + '.json'),
                            asm=asm, layouts=layouts, script_names=names,
                            index=index)
        log('  %s -> %s.json' % (base, name))


def main(argv):
    if len(argv) != 4 or argv[3] not in ('s1', 's2'):
        print(__doc__)
        return 1
    extract_season(argv[1], argv[2], argv[3])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

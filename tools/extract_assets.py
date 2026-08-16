"""Extract one season's runtime assets (textures, GUI sheets, audio,
strings, fonts) out of an unpacked data directory — the four
extract_*.py runs run.sh chains, callable in-process so the frozen
bundle can do it without a shell:

    python3 tools/extract_assets.py <data_dir> <out_root> <s1|s2>

`data_dir` is tools/unpack.py's output (apk/ + obb/); the assets land in
<out_root>/textures/<season>, audio/<season>, strings/<season>,
fonts/<season>.
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
    log('%s assets ready under %s' % (season, out_root))


def main(argv):
    if len(argv) != 4 or argv[3] not in ('s1', 's2'):
        print(__doc__)
        return 1
    extract_season(argv[1], argv[2], argv[3])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

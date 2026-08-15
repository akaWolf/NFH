"""Extract the localization TextAssets and the Font assets.

LocalizationManager loads TextAssets from Resources ("Localization/Final/" +
language name, LocalizationManager.cs:36); the languages are the Language
enum members. Fonts are class 128 objects whose m_FontData carries the raw
TTF bytes.

    NFH_DATA=... python3 tools/extract_strings.py strings/s1 fonts/s1
"""
import os, sys, glob, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from unityser import SerializedFile, Reader

TEXT_ASSET, FONT = 49, 128


def serialized_files():
    cands = [paths.GG_ASSETS] \
        + sorted(glob.glob(os.path.join(paths.APK, '*.assets'))) \
        + sorted(glob.glob(os.path.join(paths.OBB, '*.assets'))) \
        + sorted(glob.glob(os.path.join(paths.APK, 'Resources', '*'))) \
        + paths.asset_files()
    for p in cands:
        if not os.path.isfile(p):
            continue
        try:
            yield SerializedFile(p)
        except Exception:
            continue


def carve_font(body):
    """m_FontData is a length-prefixed byte array; find the sfnt magic and
    read the u32 length right before it"""
    for magic in (b'\x00\x01\x00\x00', b'OTTO', b'true'):
        i = body.find(magic)
        while i >= 4:
            n = struct.unpack_from('<I', body, i - 4)[0]
            if 1024 < n <= len(body) - i:
                return body[i:i + n]
            i = body.find(magic, i + 1)
    return None


def main(strings_dir, fonts_dir):
    os.makedirs(strings_dir, exist_ok=True)
    os.makedirs(fonts_dir, exist_ok=True)
    texts = fonts = 0
    for sf in serialized_files():
        for o in sf.objects:
            if o['class_id'] == TEXT_ASSET:
                r = Reader(sf.body(o), 0)
                name = r.astr()
                if not (name == 'Lang' or name.startswith('NEW_LANG')):
                    continue
                n = r.i32()                 # m_Script: length-prefixed bytes
                data = r.raw(n)
                with open(os.path.join(strings_dir, name + '.txt'), 'wb') as f:
                    f.write(data)
                texts += 1
            elif o['class_id'] == FONT:
                body = sf.body(o)
                r = Reader(body, 0)
                name = r.astr() or 'font%d' % o['path_id']
                ttf = carve_font(body)
                if ttf:
                    with open(os.path.join(fonts_dir, name + '.ttf'), 'wb') as f:
                        f.write(ttf)
                    fonts += 1
    print('%d language files -> %s, %d fonts -> %s'
          % (texts, strings_dir, fonts, fonts_dir))


if __name__ == '__main__':
    paths.check()
    main(sys.argv[1] if len(sys.argv) > 1 else 'strings',
         sys.argv[2] if len(sys.argv) > 2 else 'fonts')

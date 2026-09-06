"""The PC original's data archive (data/gamedata.bnd of the 2003/2004 games):
a plain ZIP of XML and TGA (ZenHAX, ModDB) — the seasons' level folders with
their level.xml, the animations, the menus. This is the PC side as data,
where the rest of tools/pcref reads it off video.

python3 tools/pcref/gamedata.py <gamedata.bnd> list [<substring>]
python3 tools/pcref/gamedata.py <gamedata.bnd> cat <member>
python3 tools/pcref/gamedata.py <gamedata.bnd> grep <regex> [<member substring>]
python3 tools/pcref/gamedata.py <gamedata.bnd> tags <member>   # the XML's element and attribute names, counted
"""
import re
import sys
import zipfile
from collections import Counter


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    z = zipfile.ZipFile(argv[1])
    cmd = argv[2]
    if cmd == 'list':
        sub = argv[3].lower() if len(argv) > 3 else ''
        for i in z.infolist():
            if sub in i.filename.lower():
                print('%9d  %s' % (i.file_size, i.filename))
    elif cmd == 'cat':
        sys.stdout.write(z.read(argv[3]).decode('utf-8', 'replace'))
    elif cmd == 'grep':
        rx = re.compile(argv[3], re.I)
        sub = argv[4].lower() if len(argv) > 4 else ''
        for i in z.infolist():
            if sub not in i.filename.lower() or not i.filename.lower().endswith('.xml'):
                continue
            for n, line in enumerate(z.read(i.filename).decode('utf-8', 'replace').split('\n'), 1):
                if rx.search(line):
                    print('%s:%d: %s' % (i.filename, n, line.strip()[:160]))
    elif cmd == 'tags':
        text = z.read(argv[3]).decode('utf-8', 'replace')
        tags = Counter(re.findall(r'<([A-Za-z_][\w.-]*)', text))
        attrs = Counter(re.findall(r'\s([A-Za-z_][\w.-]*)=', text))
        print('elements:', tags.most_common(60))
        print('attributes:', attrs.most_common(80))
    else:
        print(__doc__); return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

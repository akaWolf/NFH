#!/bin/sh
# Unpack the APK and OBB into data/, joining Unity's split .assets files.
# Usage: tools/extract.sh [destdir]     (default: ./data)
set -e

root=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:-$root/data}
apk=$root/neighbours-from-hell-season-1_1.5.5.apk
obb=$root/main.13.com.nordigames.nfh.obb

mkdir -p "$dest"
unzip -o -q "$apk" 'assets/bin/Data/*' -d "$dest/apk"
unzip -o -q "$obb" -d "$dest/obb"

# sharedassetsN.assets are stored as 1 MB splits; concatenate them back
python3 - "$dest" <<'PY'
import glob, os, re, sys, collections
dest = sys.argv[1]
groups = collections.defaultdict(list)
for p in glob.glob(dest + '/*/assets/bin/Data/sharedassets*.split*'):
    groups[p.split('.split')[0]].append(p)
for base, parts in groups.items():
    parts.sort(key=lambda p: int(re.search(r'split(\d+)$', p).group(1)))
    with open(base, 'wb') as out:
        for p in parts:
            out.write(open(p, 'rb').read())
    print('joined %-28s %d parts' % (os.path.basename(base), len(parts)))
PY

echo "extracted to $dest"

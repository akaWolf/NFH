"""Unpack the game's apk/obb/xapk into the layout the extraction tools
read (tools/extract.sh's job, in Python so the frozen bundle can do it on
Windows too):

    python3 tools/unpack.py <apk-or-xapk-or-dir> [destdir]

- an .apk yields  <dest>/apk/assets/bin/Data (needs the matching .obb
  beside it for <dest>/obb/...),
- an .xapk holds both (the APKPure wrapper: the apk + Android/obb/...),
- a directory is scanned for either form of either season.

Unity's files over ~1 MB ship as .splitN parts; every split set is joined
back (the same concatenation extract.sh runs).

`find_sources` classifies what a directory holds:
    {'s1': {'apk': ..., 'obb': ...} | {'xapk': ...}, 's2': ...}
Season 2 is anything naming nfh2 / "season 2"; season 1 the rest.
"""
import glob, os, re, shutil, sys, tempfile, zipfile


def _is_s2(name):
    n = name.lower().replace('+', ' ').replace('_', ' ')
    return 'nfh2' in n or re.search(r'season[ -]?2', n) is not None


def find_sources(directory):
    """the season -> source-file map for everything in `directory`"""
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, '*'))):
        low = os.path.basename(p).lower()
        season = 's2' if _is_s2(low) else 's1'
        if low.endswith('.xapk'):
            out.setdefault(season, {})['xapk'] = p
        elif low.endswith('.apk'):
            out.setdefault(season, {}).setdefault('apk', p)
        elif low.endswith('.obb'):
            out.setdefault(season, {}).setdefault('obb', p)
    # an apk without its obb (or the reverse) cannot be extracted
    for season in list(out):
        e = out[season]
        if 'xapk' not in e and ('apk' not in e or 'obb' not in e):
            del out[season]
    return out


def _extract_zip(zpath, dest, prefix=None, log=print):
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist()
                 if prefix is None or n.startswith(prefix)]
        for n in names:
            z.extract(n, dest)
    return dest


def join_splits(dest, log=print):
    """concatenate every name.split0..N back into name (extract.sh's tail)"""
    groups = {}
    for p in glob.glob(os.path.join(dest, '*', 'assets', 'bin', 'Data',
                                    '*.split*')):
        m = re.search(r'\.split(\d+)$', p)
        if not m:
            continue
        groups.setdefault(p[:m.start()], []).append((int(m.group(1)), p))
    for base, parts in sorted(groups.items()):
        parts.sort()
        with open(base, 'wb') as out:
            for _, p in parts:
                with open(p, 'rb') as f:
                    shutil.copyfileobj(f, out)
        log('joined %-28s %d parts' % (os.path.basename(base), len(parts)))


def unpack(entry, dest, log=print):
    """one season's sources ({'apk','obb'} or {'xapk'}) -> the
    <dest>/apk + <dest>/obb layout; returns dest"""
    os.makedirs(dest, exist_ok=True)
    if 'xapk' in entry:
        # the wrapper zip holds the apk and Android/obb/<pkg>/main.*.obb;
        # nested zips must be pulled to real files first
        with zipfile.ZipFile(entry['xapk']) as z:
            names = z.namelist()
            apk_name = next(n for n in names if n.lower().endswith('.apk'))
            obb_name = next(n for n in names if n.lower().endswith('.obb'))
            tmp = tempfile.mkdtemp(prefix='nfh-xapk-')
            try:
                apk = z.extract(apk_name, tmp)
                obb = z.extract(obb_name, tmp)
                log('unwrapped %s' % os.path.basename(entry['xapk']))
                _do_unpack(apk, obb, dest, log)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    else:
        _do_unpack(entry['apk'], entry['obb'], dest, log)
    join_splits(dest, log)
    return dest


def _do_unpack(apk, obb, dest, log):
    log('unpacking %s' % os.path.basename(apk))
    _extract_zip(apk, os.path.join(dest, 'apk'), prefix='assets/bin/Data/')
    log('unpacking %s' % os.path.basename(obb))
    _extract_zip(obb, os.path.join(dest, 'obb'))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    src = argv[1]
    dest = argv[2] if len(argv) > 2 else 'data'
    if os.path.isdir(src):
        sources = find_sources(src)
        if not sources:
            print('no apk/obb/xapk found in %s' % src)
            return 1
        for season, entry in sources.items():
            d = dest if len(sources) == 1 else dest + '-' + season
            unpack(entry, d)
            print('%s -> %s' % (season, d))
        return 0
    low = src.lower()
    if low.endswith('.xapk'):
        unpack({'xapk': src}, dest)
    elif low.endswith('.apk'):
        obb = next(iter(glob.glob(os.path.join(os.path.dirname(src) or '.',
                                               'main.*.obb'))), None)
        if obb is None:
            print('no main.*.obb beside %s' % src)
            return 1
        unpack({'apk': src, 'obb': obb}, dest)
    else:
        print('expected an .apk, .xapk or a directory')
        return 1
    print('extracted to %s' % dest)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

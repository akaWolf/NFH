"""set attributes in the Wine prefix's gameoptions.xml (UTF-16): gameopts.py nfh2 screen.fullscreen=false ..."""
import os, re, sys
g = sys.argv[1]
p = os.path.expanduser('%s/drive_c/users/%s/Documents/JoWooD/%s/gameoptions.xml' % (os.environ.get('WDBG_PREFIX', '~/nfh-bench/wine/nfh'), os.environ.get('USER', 'akawolf'), g.upper()))
s = open(p, 'rb').read().decode('utf-16')
for kv in sys.argv[2:]:
    key, val = kv.split('=', 1)
    tag, attr = key.split('.')
    s, n = re.subn(r'(<%s\b[^>]*\b%s=")[^"]*(")' % (tag, attr), r'\g<1>%s\2' % val, s)
    assert n == 1, kv
open(p, 'wb').write(s.encode('utf-16'))
print(s.split('\n', 2)[2][:800])

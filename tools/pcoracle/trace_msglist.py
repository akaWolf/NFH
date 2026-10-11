"""gdb (winedbg proxy): hook Loader's MsgList vtable methods (0x10025278) during clicks: which one adds a
message, called from where in game.exe, with what arguments"""
import gdb, os, re, time, struct, json
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '30'))
HOME = os.path.expanduser('~')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
lg = open(HOME + '/nfh-bench/wine/logs/winedbg.log').read()
GL = int(re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', lg).group(1), 16); DELTA = GL - 0x10000000
LD = int(re.search(r'Loader.dll @([0-9A-Fa-f]+)', lg).group(1), 16); LDELTA = LD - 0x10000000
def unrel(a):
    if GL <= a < GL + 0x100000: return 'GL+%#x' % (a - DELTA)
    if LD <= a < LD + 0x40000: return 'LD+%#x' % (a - LDELTA)
    return '%#x' % a
def as_string(p):
    try:
        if p < 0x10000 or p > 0x7fffffff: return None
        vt, b, e = struct.unpack('<III', rd(p, 12))
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 160): return None
        if not (0x400000 <= vt < 0x7f000000): return None
        s = rd(b, e - b).decode('utf-16le')
        return s if all(0x20 <= ord(c) < 0x7f for c in s) else None
    except Exception:
        return None
def describe(v):
    s = as_string(v)
    if s is not None: return s
    if 0x10000 < v < 0x7fffffff:
        try: words = struct.unpack('<24I', rd(v, 96))
        except Exception: return '%#x' % v
        found = ['+%#x:%s' % (4 * i, as_string(w)) for i, w in enumerate(words) if as_string(w) is not None]
        return '{%#x vt=%s %s}' % (v, unrel(words[0]), ' '.join(found[:5]))
    return v
def chain(ebp, n=8):
    out = []
    for i in range(n):
        try: ret = u32(ebp + 4); nxt = u32(ebp)
        except Exception: break
        out.append(unrel(ret))
        if nxt <= ebp or nxt > ebp + 0x100000: break
        ebp = nxt
    return out
state = {'tick': 0, 't0': None}
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044234 + DELTA), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time()
        if state['t0'] is None: state['t0'] = now
        if state['tick'] % 60 == 0: print('heartbeat tick', state['tick'], flush=True)
        return now - state['t0'] > secs
class M(gdb.Breakpoint):
    def __init__(self, idx, addr):
        super().__init__('*%#x' % (addr + LDELTA), internal=True); self.idx = idx
    def stop(self):
        try:
            if state['tick'] < 20: return False       # past the level's setup flood
            esp = int(gdb.parse_and_eval('$esp')); ebp = int(gdb.parse_and_eval('$ebp')); ecx = int(gdb.parse_and_eval('$ecx'))
            ch = chain(ebp)
            if not any(c.startswith('0x4') for c in ch[:3]): return False   # only calls from game.exe
            args = [describe(u32(esp + 4 + 4 * i)) for i in range(4)]
            print('tick %d MsgList[%d] this=%#x args=%s chain=%s' % (state['tick'], self.idx, ecx, args, ch[:5]), flush=True)
        except Exception as e:
            print('err', e, flush=True)
        return False
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: inf.write_memory(b, want.encode('utf-16le'))
gdb.execute('delete')
Tick()
for i, a in ((3, 0x10007e84), (7, 0x10007e17)):
    M(i, a)
gdb.execute('continue')
print('done ticks', state['tick'], flush=True)
gdb.execute('kill')

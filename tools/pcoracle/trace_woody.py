"""gdb (winedbg proxy): find GameLogic's handlers of Woody's messages — hook the path finder fcn.1000a711 and
DoAction fcn.10002cd5, log args (Strings decoded, objects scanned for Strings) and the ebp return chain"""
import gdb, os, re, time, struct, json
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '40'))
HOME = os.path.expanduser('~')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
m = re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', open(HOME + '/nfh-bench/wine/logs/winedbg.log').read())
GL = int(m.group(1), 16); DELTA = GL - 0x10000000
def ungl(a): return a - DELTA if GL <= a < GL + 0x100000 else a
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
        try:
            words = struct.unpack('<32I', rd(v, 128))
        except Exception:
            return v
        found = []
        for i, w in enumerate(words):
            s = as_string(w)
            if s is not None: found.append('+%#x:%s' % (4 * i, s))
            elif i < 4 and 0x10000 < w < 0x7fffffff:
                s2 = as_string(w) 
        if found: return '{%#x %s}' % (v, ' '.join(found[:6]))
    return v
def chain(ebp, n=8):
    out = []
    for i in range(n):
        try:
            ret = u32(ebp + 4); nxt = u32(ebp)
        except Exception:
            break
        out.append('%#x' % ungl(ret))
        if nxt <= ebp or nxt > ebp + 0x100000: break
        ebp = nxt
    return out
log = open(HOME + '/nfh-bench/wine/logs/trace_woody.jsonl', 'w')
state = {'tick': 0, 't0': None}
class Hook(gdb.Breakpoint):
    def __init__(self, addr, name, tick=False):
        super().__init__('*%#x' % (addr + DELTA), internal=True); self.name = name; self.is_tick = tick
    def stop(self):
        try:
            now = time.time()
            if self.is_tick:
                state['tick'] += 1
                if state['t0'] is None: state['t0'] = now
                if now - state['t0'] > secs: return True
                return False
            esp = int(gdb.parse_and_eval('$esp')); ebp = int(gdb.parse_and_eval('$ebp'))
            args = [describe(u32(esp + 4 + 4 * i)) for i in range(6)]
            rec = {'tick': state['tick'], 'ev': self.name, 'ret': '%#x' % ungl(u32(esp)), 'args': args, 'chain': chain(ebp)}
            log.write(json.dumps(rec, default=str) + '\n'); log.flush()
        except Exception as e:
            log.write(json.dumps({'ev': 'error', 'err': repr(e)}) + '\n')
        return False
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: inf.write_memory(b, want.encode('utf-16le'))
gdb.execute('delete')
Hook(0x10044234, 'tick', tick=True); Hook(0x1000a711, 'path'); Hook(0x10002cd5, 'action')
gdb.execute('continue')
print('done, ticks', state['tick'], flush=True)
gdb.execute('kill')

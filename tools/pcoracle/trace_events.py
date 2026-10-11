"""gdb (winedbg proxy) event tracer for NFH2's GameLogic.dll: the level tick (fcn.10044234) and the script
elements — GoTo fcn.1000e3e0, DoAction fcn.10002cd5, icon fcn.100422a5, credit fcn.1000140b, behaviour post
fcn.1004000a, SHOUT fcn.1000f977 — with their String arguments decoded and the calling step (the return
address). JSON lines to ~/nfh-bench/wine/logs/trace_<level>.jsonl. WDBG_LEVEL patches the level name at the
session start (0x408014); WDBG_SECS stops the trace that many seconds after the first tick."""
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
m = re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', open(HOME + '/nfh-bench/wine/logs/winedbg.log').read())
GL = int(m.group(1), 16); DELTA = GL - 0x10000000
print('GameLogic base %#x' % GL, flush=True)
def gl(a): return a + DELTA
def ungl(a): return a - DELTA if GL <= a < GL + 0x100000 else a
def as_string(p):
    """a core String {vtable, begin, end}: its UTF-16 text, else None"""
    try:
        if p < 0x10000 or p > 0x7fffffff: return None
        vt, b, e = struct.unpack('<III', rd(p, 12))
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 160): return None
        if not (0x400000 <= vt < 0x7f000000): return None
        s = rd(b, e - b).decode('utf-16le')
        return s if all(0x20 <= ord(c) < 0x7f for c in s) else None
    except Exception:
        return None
def decode_args(esp, n=6):
    out = []
    for i in range(n):
        v = u32(esp + 4 + 4 * i)
        s = as_string(v)
        if s is None and 0x10000 < v < 0x7fffffff:
            try: s = as_string(u32(v))   # a String** / a smart pointer
            except Exception: s = None
            if s is not None: s = '*' + s
        out.append(s if s is not None else v)
    return out
log = open(HOME + '/nfh-bench/wine/logs/trace_%s.jsonl' % (want or 'cur'), 'w')
state = {'tick': 0, 't0': None, 'n': 0}
actors = {}     # name -> object (the path finder's args[1]; +4 name, +0x2c x, +0x30 y, +0x40 anim)
class PathHook(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % gl(0x1000a711), internal=True)
    def stop(self):
        try:
            a = u32(int(gdb.parse_and_eval('$esp')) + 8); name = as_string(u32(a + 4))
            if name and name not in actors: actors[name] = a
        except Exception: pass
        return False
def actor_states():
    out = {}
    for name, a in actors.items():
        try:
            out[name] = {'x': struct.unpack('<i', rd(a + 0x2c, 4))[0], 'y': struct.unpack('<i', rd(a + 0x30, 4))[0],
                         'anim': as_string(u32(a + 0x40))}
        except Exception: pass
    return out
class Hook(gdb.Breakpoint):
    def __init__(self, addr, name, nargs=6, tick=False):
        super().__init__('*%#x' % gl(addr), internal=True)
        self.name, self.nargs, self.is_tick = name, nargs, tick
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp'))
            now = time.time()
            if self.is_tick:
                state['tick'] += 1
                if state['t0'] is None: state['t0'] = now
                rec = {'tick': state['tick'], 'wall': round(now - state['t0'], 3), 'ev': 'tick', 'actors': actor_states()}
            else:
                ret = u32(esp)
                rec = {'tick': state['tick'], 'ev': self.name, 'ret': '%#x' % ungl(ret), 'args': decode_args(esp, self.nargs)}
            log.write(json.dumps(rec) + '\n'); state['n'] += 1
            if state['n'] % 50 == 0: log.flush()
            if state['t0'] is not None and now - state['t0'] > secs:
                return True
        except Exception as e:
            log.write(json.dumps({'ev': 'error', 'name': self.name, 'err': repr(e)}) + '\n')
        return False
# the level session start in game.exe: patch the level name
gdb.Breakpoint('*0x408014')
gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp'))
sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
name = rd(b, e - b).decode('utf-16le'); print('level', name, flush=True)
if want and len(want) == len(name):
    inf.write_memory(b, want.encode('utf-16le')); print('patched to', want, flush=True)
gdb.execute('delete')
Hook(0x10044234, 'tick', tick=True)
PathHook()
Hook(0x1000e3e0, 'goto'); Hook(0x10002cd5, 'action'); Hook(0x100422a5, 'icon')
Hook(0x1000140b, 'credit'); Hook(0x1004000a, 'post'); Hook(0x1000f977, 'shout')
t1 = time.time()
gdb.execute('continue')
log.flush()
print('traced %d events, %d ticks in %.1fs wall (%.2f ticks/s)' % (state['n'], state['tick'], time.time() - (state['t0'] or t1), state['tick'] / max(0.01, time.time() - (state['t0'] or t1))), flush=True)
gdb.execute('kill')

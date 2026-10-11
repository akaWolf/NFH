"""gdb (winedbg proxy) script: the PC original as an oracle — one level run with a tick-stamped input
script and a per-tick trace.

Run through wdbg.py:
    WDBG_LEVEL=cn_b1 WDBG_SCRIPT=inputs.json WDBG_SECS=300 WDBG_CLICKS="300 300 4  283 314 4  745 550 1" \\
        python3 wdbg.py nfh2 $PWD/oracle.py 400

The script (WDBG_SCRIPT) is a JSON list of {"tick": N, "kind": "use"|"combine"|"goto", "args": [...]}:
use [object], combine [object, item], goto [room, x]. LEAD (4) ticks before N a dummy floor click is sent (xdotool at
WDBG_DUMMY, default 400 300 — a floor spot on screen); its GoToPosMsg is replaced in GameLogic's message
loop (GL+0x10044464) by a message built in scratch memory (inject2.py's layouts). The tick the game really
took it at is in its own GameLogicLog (UTF-16, ~/nfh-bench/wine/nfh/drive_c/users/<user>/Documents/JoWooD/NFH2).

The trace (~/nfh-bench/wine/logs/oracle_<level>.jsonl): per tick the actors' x/y/anim (GameLogic's actor
object: +0x2c, +0x30, +0x40 — captured from the path finder fcn.1000a711), and the script elements — GoTo
fcn.1000e3e0, DoAction fcn.10002cd5, icon fcn.100422a5, behaviour post fcn.1004000a, SHOUT fcn.1000f977 —
with the calling step's return address. The level tick is fcn.10044234 (12 a second)."""
import gdb, os, re, time, struct, json, subprocess, threading, signal
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '60'))
HOME = os.path.expanduser('~')
T = os.path.dirname(os.path.abspath(__file__))
DUMMY = os.environ.get('WDBG_DUMMY', '400 300').split()
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def wr(a, b): inf.write_memory(a, b)
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
lg = open(HOME + '/nfh-bench/wine/logs/winedbg.log').read()
GL = int(re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', lg).group(1), 16); DELTA = GL - 0x10000000
def gl(a): return a + DELTA
def ungl(a): return a - DELTA if GL <= a < GL + 0x100000 else a
def as_string(p):
    try:
        if p < 0x10000 or p > 0x7fffffff: return None
        vt, b, e = struct.unpack('<III', rd(p, 12))
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 200): return None
        if not (0x400000 <= vt < 0x7f000000): return None
        s = rd(b, e - b).decode('utf-16le', 'replace')
        return s if all(0x20 <= ord(c) < 0x7f for c in s) else None
    except Exception:
        return None
def decode_args(esp, n=4):
    out = []
    for i in range(n):
        v = u32(esp + 4 + 4 * i); s = as_string(v)
        out.append(s if s is not None else v)
    return out

# --- scratch memory and synthetic messages (inject2.py) ---
scratch = {'base': None, 'pos': 0, 'sproto': None}
def alloc_scratch():
    va = u32(0x452108)       # kernel32!VirtualAlloc through game.exe's import slot
    p = int(gdb.parse_and_eval('((unsigned int (*)(unsigned int, unsigned int, unsigned int, unsigned int))%#x)(0, 262144, 0x3000, 0x40)' % va))
    scratch['base'] = p
def salloc(n):
    n = (n + 15) & ~15
    p = scratch['base'] + scratch['pos']; scratch['pos'] += n; wr(p, b'\0' * n); return p
def make_string(text):
    """a core String {vtable, begin, end, +0xc, refcount +0x10}: the game's release deletes at zero"""
    data = text.encode('utf-16le') + b'\0\0'
    buf = salloc(len(data)); wr(buf, data)
    obj = salloc(32); wr(obj, rd(scratch['sproto'], 32))
    wr(obj + 4, struct.pack('<II', buf, buf + len(data) - 2)); wr(obj + 0x10, struct.pack('<I', 0x1000))
    return obj
def msg_use(name):
    m = salloc(0x40); wr(m, struct.pack('<IIIII', 0x453b2c, make_string(name), make_string('oracle'), 0, 0x1000)); return m
def msg_combine(obj, item):
    m = salloc(0x40); wr(m, struct.pack('<IIIIIIII', 0x453b20, make_string(obj), make_string(item), make_string('oracle'), 0, 0, 0, 0x1000)); return m
def msg_goto(room, x):
    m = salloc(0x40); wr(m, struct.pack('<IIIIIII', 0x453b38, make_string(room), 0, int(x), 0, 0, 0x1000)); return m
def build(step):
    k, a = step['kind'], step['args']
    if k == 'use': return msg_use(a[0])
    if k == 'combine': return msg_combine(a[0], a[1])
    if k == 'goto': return msg_goto(a[0], a[1])
    raise ValueError(k)

script = json.load(open(os.environ['WDBG_SCRIPT'])) if os.environ.get('WDBG_SCRIPT') else []
script.sort(key=lambda s: s['tick'])
pending = []          # messages built, waiting for a dummy click to replace
state = {'tick': 0, 't0': None, 'last': time.time(), 'n': 0}
actors = {}
log = open(HOME + '/nfh-bench/wine/logs/oracle_%s.jsonl' % (want or 'cur'), 'w')
def emit(rec):
    log.write(json.dumps(rec) + '\n'); state['n'] += 1
    if state['n'] % 50 == 0: log.flush()
def actor_states():
    out = {}
    for name, a in actors.items():
        try:
            out[name] = {'x': struct.unpack('<i', rd(a + 0x2c, 4))[0], 'y': struct.unpack('<i', rd(a + 0x30, 4))[0], 'anim': as_string(u32(a + 0x40))}
        except Exception: pass
    return out
LEAD = int(os.environ.get('WDBG_LEAD', '4'))      # ticks between the dummy's dispatch and the scripted tick
def click_dummy():
    # (the game polls the mouse at its 12 Hz: xdotool's instant click fell between two polls every other
    # time — the button is held 0.2 s; the move settles 0.3 s before; the message lands 3-4 ticks on)
    subprocess.Popen([T + '/xdotool-result/bin/xdotool', 'mousemove', DUMMY[0], DUMMY[1], 'sleep', '0.3',
                      'mousedown', '1', 'sleep', '0.2', 'mouseup', '1'],
                     env=dict(os.environ, DISPLAY=os.environ.get('WDBG_DISPLAY', ':97')))
def watchdog():
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > 8:
            print('WATCHDOG: no tick for 8 s (last tick %d)' % state['tick'], flush=True)
            os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()

class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % gl(0x10044234), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time(); state['last'] = now
        if state['t0'] is None:
            state['t0'] = now; open(HOME + '/nfh-bench/wine/logs/level_started', 'w').write('%.3f' % now)
        if state['tick'] == 20:
            alloc_scratch(); state['loop'].enabled = True
        # a dummy click two ticks ahead of each scripted message
        while script and script[0]['tick'] - LEAD <= state['tick']:
            step = script.pop(0); pending.append(step); click_dummy()
            emit({'tick': state['tick'], 'ev': 'dummy', 'for': step})
        emit({'tick': state['tick'], 'wall': round(now - state['t0'], 3), 'ev': 'tick', 'actors': actor_states()})
        return now - state['t0'] > secs
class Loop(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % gl(0x10044464), internal=True)
    def stop(self):
        try:
            ebp = int(gdb.parse_and_eval('$ebp')); msg = u32(ebp - 0x14); vt = u32(msg)
            if vt in (0x453b38, 0x453b2c, 0x453b20):      # a player's message: GoToPos / UseObject / Combine
                if scratch['sproto'] is None: scratch['sproto'] = u32(msg + 4)
                if pending:
                    step = pending.pop(0); new = build(step)
                    wr(ebp - 0x14, struct.pack('<I', new))
                    emit({'tick': state['tick'], 'ev': 'injected', 'step': step})
                    print('INJECTED tick %d: %s' % (state['tick'], step), flush=True)
                else:
                    emit({'tick': state['tick'], 'ev': 'click', 'vt': '%#x' % vt, 'a': as_string(u32(msg + 4)), 'b': as_string(u32(msg + 8)) or u32(msg + 0xc)})
        except Exception as e:
            print('loop err', repr(e), flush=True)
        return False
class PathHook(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % gl(0x1000a711), internal=True)
    def stop(self):
        try:
            a = u32(int(gdb.parse_and_eval('$esp')) + 8); name = as_string(u32(a + 4))
            if name and name not in actors: actors[name] = a
        except Exception: pass
        return False
class Hook(gdb.Breakpoint):
    def __init__(self, addr, name, nargs=4):
        super().__init__('*%#x' % gl(addr), internal=True); self.name, self.nargs = name, nargs
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp'))
            emit({'tick': state['tick'], 'ev': self.name, 'ret': '%#x' % ungl(u32(esp)), 'args': decode_args(esp, self.nargs)})
        except Exception as e:
            emit({'tick': state['tick'], 'ev': 'error', 'name': self.name, 'err': repr(e)})
        return False

gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
name = rd(b, e - b).decode('utf-16le'); print('level', name, flush=True)
if want and len(want) == len(name):
    wr(b, want.encode('utf-16le')); print('patched to', want, flush=True)
gdb.execute('delete')
lp = Loop(); lp.enabled = False; state['loop'] = lp
Tick(); PathHook()
Hook(0x1000e3e0, 'goto'); Hook(0x10002cd5, 'action'); Hook(0x100422a5, 'icon'); Hook(0x1004000a, 'post'); Hook(0x1000f977, 'shout', 5)
try:
    gdb.execute('continue')
except Exception as ex:
    print('continue ended:', repr(ex), flush=True)
log.flush()
print('done: %d ticks, %d records, %d script steps left' % (state['tick'], state['n'], len(script) + len(pending)), flush=True)
gdb.execute('kill')

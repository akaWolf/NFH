"""gdb (winedbg proxy): synthetic player messages — at GameLogic's message loop (GL+0x10044464) a dummy
floor click's message in [ebp-0x14] is replaced by a message built in scratch memory: UseObjectMsg (vtable
0x453b2c: +4 name, +8 text, refcount +0x10), CombineMsg (0x453b20: +4 object, +8 object2, +0xc text, refcount
+0x1c), GoToPosMsg (0x453b38: +4 room, +0xc x, +0x10 y, refcount +0x18); refcounts preset to 0x1000 so the
game never frees them. WDBG_PLAN: 'use:<name>;combine:<object>,<item>;goto:<room>,<x>' consumed one per
dummy in order."""
import gdb, os, re, time, struct, json
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '60'))
HOME = os.path.expanduser('~')
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
def as_string(p):
    try:
        if p < 0x10000 or p > 0x7fffffff: return None
        vt, b, e = struct.unpack('<III', rd(p, 12))
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 200): return None
        if not (0x400000 <= vt < 0x7f000000): return None
        return rd(b, e - b).decode('utf-16le', 'replace')
    except Exception:
        return None
scratch = {'base': None, 'pos': 0, 'sproto': None}
def alloc_scratch():
    va = u32(0x452108)
    p = int(gdb.parse_and_eval('((unsigned int (*)(unsigned int, unsigned int, unsigned int, unsigned int))%#x)(0, 65536, 0x3000, 0x40)' % va))
    scratch['base'] = p; wr(p, b'\0' * 4096); print('scratch at %#x' % p, flush=True)
def salloc(n):
    p = scratch['base'] + scratch['pos']; scratch['pos'] += (n + 15) & ~15; wr(p, b'\0' * ((n + 15) & ~15)); return p
def make_string(text):
    data = text.encode('utf-16le') + b'\0\0'
    buf = salloc(len(data)); wr(buf, data)
    # the String object: {vtable, begin, end, +0xc, refcount +0x10} (release 0x4103e0 deletes at zero)
    obj = salloc(32); wr(obj, rd(scratch['sproto'], 32))
    wr(obj + 4, struct.pack('<II', buf, buf + len(data) - 2))
    wr(obj + 0x10, struct.pack('<I', 0x1000))
    return obj
def msg_use(name, text='Look at it'):
    m = salloc(0x40); wr(m, struct.pack('<IIIII', 0x453b2c, make_string(name), make_string(text), 0, 0x1000)); return m
def msg_combine(obj, item, text='Use it'):
    m = salloc(0x40); wr(m, struct.pack('<IIIIIIII', 0x453b20, make_string(obj), make_string(item), make_string(text), 0, 0, 0, 0x1000)); return m
def msg_goto(room, x):
    m = salloc(0x40); wr(m, struct.pack('<IIIIIII', 0x453b38, make_string(room), 0, x, 0, 0, 0x1000)); return m
plan = [p for p in os.environ.get('WDBG_PLAN', '').split(';') if p]
state = {'tick': 0, 't0': None, 'last': time.time()}
import threading, signal
def watchdog():
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > 4:
            print('WATCHDOG: no tick for 4 s (last tick %d) -> interrupting' % state['tick'], flush=True)
            os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()
out = open(HOME + '/nfh-bench/wine/logs/inject2.jsonl', 'w')
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044234 + DELTA), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time(); state['last'] = now
        if state['t0'] is None:
            state['t0'] = now; open(HOME + '/nfh-bench/wine/logs/level_started', 'w').write('%.3f' % now)
        if state['tick'] == 20:
            alloc_scratch(); state['loop'].enabled = True
        return now - state['t0'] > secs
class Loop(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044464 + DELTA), internal=True)
    def stop(self):
        try:
            ebp = int(gdb.parse_and_eval('$ebp')); msg = u32(ebp - 0x14); vt = u32(msg)
            if vt != 0x453b38 or not plan: return False     # only dummy floor clicks are replaced
            if scratch['sproto'] is None: scratch['sproto'] = u32(msg + 4)    # a String to clone
            step = plan.pop(0); kind, arg = step.split(':', 1)
            if kind == 'use': new = msg_use(arg)
            elif kind == 'combine': o, i = arg.split(','); new = msg_combine(o, i)
            elif kind == 'goto': r, x = arg.split(','); new = msg_goto(r, int(x))
            else: return False
            wr(ebp - 0x14, struct.pack('<I', new))
            print('INJECTED tick %d: %s -> %#x (dummy %#x)' % (state['tick'], step, new, msg), flush=True)
        except Exception as e:
            print('loop err', repr(e), flush=True)
        return False
class Act(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10002cd5 + DELTA), internal=True)
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp')); a1, a2 = as_string(u32(esp + 8)), as_string(u32(esp + 12))
            if state['tick'] > 20 and (a1 == 'woody' or (a2 and a2 not in ('enter', 'leave', 'use', 'start'))):
                print('ACTION tick %d: %s %s' % (state['tick'], a1, a2), flush=True)
        except Exception: pass
        return False
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: wr(b, want.encode('utf-16le'))
gdb.execute('delete')
lp = Loop(); lp.enabled = False; state['loop'] = lp
Act(); Tick()
try:
    gdb.execute('continue')
except Exception as e:
    print('continue ended:', repr(e), flush=True)
print('done ticks', state['tick'], flush=True)
try:
    gdb.execute('info threads'); gdb.execute('thread apply all bt 10')
except Exception as e:
    print('bt failed', e)
gdb.execute('kill')

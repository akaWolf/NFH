"""gdb (winedbg proxy): capture the player messages GameLogic handles — at the message loop (GL+0x10044464,
msg in [ebp-0x14]) dump the Msg object (vtable, fields, Strings), naming the type from the next log write"""
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
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 200): return None
        if not (0x400000 <= vt < 0x7f000000): return None
        return rd(b, e - b).decode('utf-16le', 'replace')
    except Exception:
        return None
state = {'tick': 0, 't0': None, 'pending': None, 'seen': {}}
out = open(HOME + '/nfh-bench/wine/logs/msgs.jsonl', 'w')
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044234 + DELTA), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time()
        if state['t0'] is None: state['t0'] = now
        if state['tick'] == 20:
            for bp in state['late']: bp.enabled = True
        return now - state['t0'] > secs
class Loop(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044464 + DELTA), internal=True)
    def stop(self):
        try:
            ebp = int(gdb.parse_and_eval('$ebp')); msg = u32(ebp - 0x14)
            words = struct.unpack('<16I', rd(msg, 64))
            fields = {}
            for i, w in enumerate(words):
                s = as_string(w)
                if s is not None: fields['+%#x' % (4 * i)] = s
            state['pending'] = {'tick': state['tick'], 'msg': '%#x' % msg, 'vt': unrel(words[0]), 'words': ['%#x' % w for w in words], 'strings': fields}
        except Exception as e:
            state['pending'] = {'err': repr(e)}
        return False
txt = open(HOME + '/nfh-bench/pcref/r2/nfh2_game_text.txt').read()
slot = int(re.search(r'sym\.imp\.KERNEL32\.dll_WriteFile\] ; (0x45[0-9a-f]+)', txt).group(1), 16)
class WF(gdb.Breakpoint):
    def __init__(self, addr): super().__init__('*%#x' % addr, internal=True)
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp')); buf, n = u32(esp + 8), u32(esp + 12)
            t = rd(buf, min(n, 120)).decode('utf-16le', 'replace')
            if t.endswith('Msg') and state['pending'] is not None:
                p = state['pending']; p['name'] = t; state['pending'] = None
                if state['tick'] > 2 or t not in state['seen']:
                    state['seen'][t] = p['vt']
                    if state['tick'] > 2: out.write(json.dumps(p) + '\n'); out.flush()
        except Exception as e:
            pass
        return False
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: inf.write_memory(b, want.encode('utf-16le'))
gdb.execute('delete')
lp = Loop(); wf = WF(u32(slot)); lp.enabled = False; wf.enabled = False
state['late'] = [lp, wf]
Tick()
gdb.execute('continue')
print('done ticks', state['tick'], 'types', json.dumps(state['seen']), flush=True)
gdb.execute('kill')

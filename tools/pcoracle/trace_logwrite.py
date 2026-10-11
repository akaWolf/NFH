"""gdb (winedbg proxy): break on kernel32!WriteFile (game.exe's IAT slot) when the buffer holds a player
message and print the ebp return chain — the way from GameLogic's dispatcher to the log"""
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
LD = int(re.search(r'Loader.dll @([0-9A-Fa-f]+)', lg).group(1), 16)
def unrel(a):
    if GL <= a < GL + 0x100000: return 'GL+%#x' % (a - GL + 0x10000000)
    if LD <= a < LD + 0x40000: return 'LD+%#x' % (a - LD + 0x10000000)
    return '%#x' % a
def chain(ebp, n=10):
    out = []
    for i in range(n):
        try: ret = u32(ebp + 4); nxt = u32(ebp)
        except Exception: break
        out.append(unrel(ret))
        if nxt <= ebp or nxt > ebp + 0x100000: break
        ebp = nxt
    return out
state = {'tick': 0, 't0': None, 'hits': 0}
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044234 + DELTA), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time()
        if state['t0'] is None: state['t0'] = now
        return now - state['t0'] > secs
wf = u32(0x452000 + 0)   # placeholder, replaced below
class WF(gdb.Breakpoint):
    def __init__(self, addr): super().__init__('*%#x' % addr, internal=True)
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp')); ebp = int(gdb.parse_and_eval('$ebp'))
            buf, n = u32(esp + 8), u32(esp + 12)
            data = rd(buf, min(n, 400))
            txt = data.decode('utf-16le', 'replace') if n % 2 == 0 else data.decode('latin-1')
            if 'Msg' in txt and 'time' not in txt[:8]:
                state['hits'] += 1
                print('WRITE tick %d n=%d: %r' % (state['tick'], n, txt[:160]), flush=True)
                print('   chain', chain(ebp), flush=True)
                # the callers' stack args: the first frames' [ebp+8..]
        except Exception as e:
            print('wf err', e, flush=True)
        return False
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: inf.write_memory(b, want.encode('utf-16le'))
gdb.execute('delete')
# kernel32!WriteFile through game.exe's import slot: find the slot by scanning the IAT for the name
import subprocess
slot = None
for cand in range(0x452000, 0x452400, 4):
    pass
# the r2 dump named the slot: sym.imp.KERNEL32.dll_WriteFile — read from the file listing of imports
txt = open(HOME + '/nfh-bench/pcref/r2/nfh2_game_text.txt').read()
m = re.search(r'sym\.imp\.KERNEL32\.dll_WriteFile\] ; (0x45[0-9a-f]+)', txt)
slot = int(m.group(1), 16); wf = u32(slot)
print('WriteFile slot %#x -> %#x' % (slot, wf), flush=True)
Tick(); WF(wf)
gdb.execute('continue')
print('done ticks', state['tick'], 'hits', state['hits'], flush=True)
gdb.execute('kill')

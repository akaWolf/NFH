"""NFH2: the level tick's caller in game.exe — a universal tick site for every level, the tutorial 201 too
(fcn.10044234 stops after its first tick there). On the first hit of fcn.10044234 the stack's return
addresses into game.exe are printed and the first of them hooked; both are counted against the wall clock."""
import gdb, os, re, time, struct, signal, threading
port = os.environ.get('WDBG_PORT', '33333'); HOME = os.path.expanduser('~'); LOGS = os.environ.get('WDBG_LOGS', HOME + '/nfh-bench/wine/logs')
want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '60'))
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'): gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def wr(a, b):
    for i in range(0, len(b), 16): inf.write_memory(a + i, b[i:i + 16])
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
def reg(n): return int(gdb.parse_and_eval('$' + n))
lg = open(LOGS + '/winedbg.log').read()
GL = int(re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', lg).group(1), 16); DELTA = GL - 0x10000000
def gl(a): return a + DELTA
state = {'t0': None, 'tick': 0, 'last': time.time(), 'site': None, 'site_hits': 0}
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % gl(0x10044234), internal=True)
    def stop(self):
        state['tick'] += 1; state['last'] = time.time()
        if state['t0'] is None:
            state['t0'] = time.time(); open(LOGS + '/level_started', 'w').write('%.3f' % state['t0'])
        if state['tick'] == 1:
            esp = reg('esp'); rets = []
            for i in range(0, 200):
                w = u32(esp + 4 * i)
                if 0x401000 <= w < 0x452000: rets.append(w)
            print('tick 1: game.exe return addresses on the stack %s' % ['%#x' % r for r in rets], flush=True)
            if rets:
                state['site'] = rets[0]; Site(rets[0])
        return False
class Site(gdb.Breakpoint):
    def __init__(self, addr): super().__init__('*%#x' % addr, internal=True); self.addr = addr
    def stop(self):
        state['site_hits'] += 1; state['last'] = time.time()
        if state['site_hits'] % 120 == 0:
            print('site %#x hits %d, level ticks %d, %.1f s' % (self.addr, state['site_hits'], state['tick'], time.time() - state['t0']), flush=True)
        return time.time() - state['t0'] > secs
def watchdog():
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > 40:
            print('WATCHDOG (last tick %d, site hits %d)' % (state['tick'], state['site_hits']), flush=True); os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = reg('ebp'); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
name = rd(b, e - b).decode('utf-16le'); print('level', name, flush=True)
if want and len(want) == len(name): wr(b, want.encode('utf-16le')); print('patched to', want, flush=True)
gdb.execute('delete'); Tick()
try: gdb.execute('continue')
except Exception as ex: print('continue ended:', repr(ex), flush=True)
print('done: level ticks %d, site %s hits %d in %.1f s' % (state['tick'], '%#x' % state['site'] if state['site'] else None, state['site_hits'], (time.time() - state['t0']) if state['t0'] else 0), flush=True)
gdb.execute('kill')

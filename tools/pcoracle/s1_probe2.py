"""the message loop's pop: which site and which stack slot hold the popped message (NFH1)"""
import gdb, os, time, struct, signal, threading
port = os.environ.get('WDBG_PORT', '33333'); HOME = os.path.expanduser('~'); LOGS = os.environ.get('WDBG_LOGS', HOME + '/nfh-bench/wine/logs')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'): gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
def reg(n): return int(gdb.parse_and_eval('$' + n))
def as_string(p):
    try:
        if p < 0x10000 or p > 0x7fffffff: return None
        vt, b, e = struct.unpack('<III', rd(p, 12))
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 200) or not (0x400000 <= vt < 0x7f000000): return None
        s = rd(b, e - b).decode('utf-16le', 'replace'); return s if all(0x20 <= ord(c) < 0x7f for c in s) else None
    except Exception: return None
state = {'t0': None, 'tick': 0, 'last': time.time()}
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*0x43b2f5', internal=True)
    def stop(self):
        state['tick'] += 1; state['last'] = time.time()
        if state['t0'] is None: state['t0'] = time.time(); open(LOGS + '/level_started', 'w').write('%.3f' % state['t0'])
        return time.time() - state['t0'] > 40
class Site(gdb.Breakpoint):
    def __init__(self, addr): super().__init__('*%#x' % addr, internal=True); self.addr = addr; self.n = 0
    def stop(self):
        if state['t0'] is None: return False
        self.n += 1
        if self.n <= 6:
            esp = reg('esp'); words = [u32(esp + 4 * i) for i in range(12)]
            info = []
            for i, w in enumerate(words):
                try:
                    vt = u32(w) if 0x10000 < w < 0x7fffffff else 0
                    if 0x4e0000 <= vt < 0x4f0000: info.append(('[esp+%#x]' % (4 * i), '%#x' % w, 'vt %#x' % vt, as_string(u32(w + 4))))
                except Exception: pass
            print('SITE %#x #%d tick %d: ecx %#x eax %#x words %s msgs %s' % (self.addr, self.n, state['tick'], reg('ecx'), reg('eax'), ['%#x' % w for w in words], info), flush=True)
        return False
def watchdog():
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > 30: os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()
Tick()
for a in (0x43b162, 0x43b165, 0x43b176, 0x43b1fb, 0x43b1fe): Site(a)
try: gdb.execute('continue')
except Exception as ex: print('continue ended:', repr(ex), flush=True)
print('done %d ticks' % state['tick'], flush=True)
gdb.execute('kill')

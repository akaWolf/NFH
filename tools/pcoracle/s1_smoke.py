"""gdb (winedbg proxy) script: NFH1's game.exe under the oracle's harness — the first look. Finds the level
name String at the GameLogic constructor (fcn.0043ab40) and the level class factory (fcn.00439fe0),
patches it to WDBG_LEVEL (the name written to scratch memory, the String's begin/end repointed), then
traces the level: the tick (the `<time>` log writer 0x450c40 — its callers are printed on the first hits,
the level tick function among them), DoAction fcn.00477f60 (ecx = object, edx = action), GoTo
fcn.00479da0 (edx = object), SetIcon fcn.00437f70 (ecx = icon), the message loop's pops (found from the
log writers' callers). Trace: ~/nfh-bench/wine/logs/s1_<level>.jsonl.

    WDBG_LEVEL=level_peep WDBG_SECS=60 WDBG_CLICKS="414 313 4  65 116 3  750 555 1" \\
        WDBG_CMD="$W/bin/winedbg --gdb --no-start --port 33333 Z:\\home\\akawolf\\nfh-bench\\wine\\nfh1game\\bin\\game.exe" \\
        python3 wdbg.py nfh1 $PWD/s1_smoke.py 200
"""
import gdb, os, sys, time, struct, json, threading, signal
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '60'))
HOME = os.path.expanduser('~')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def wr(a, b):
    for i in range(0, len(b), 16):
        inf.write_memory(a + i, b[i:i + 16])
    if bytes(inf.read_memory(a, len(b))) != bytes(b):
        raise RuntimeError('memory write mismatch at %#x' % a)
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
def reg(n): return int(gdb.parse_and_eval('$' + n))
TEXT = (0x401000, 0x452000)
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
def stack_strings(esp, n=24):
    out = []
    for i in range(n):
        w = u32(esp + 4 * i); s = as_string(w)
        if s is not None: out.append((i, '%#x' % w, s))
        else:
            # a String held by value on the stack: the word may be the vtable itself
            s2 = as_string(esp + 4 * i)
            if s2 is not None: out.append((i, 'inline', s2))
    return out
def rets(esp, n=64):
    out = []
    for i in range(n):
        w = u32(esp + 4 * i)
        if TEXT[0] <= w < TEXT[1]: out.append('%#x' % w)
    return out

log = open(HOME + '/nfh-bench/wine/logs/s1_%s.jsonl' % (want or 'cur'), 'w')
state = {'tick': 0, 't0': None, 'last': time.time(), 'n': 0, 'patched': False}
def emit(rec):
    log.write(json.dumps(rec) + '\n'); state['n'] += 1
    if state['n'] % 20 == 0: log.flush()
class Ctor(gdb.Breakpoint):
    def __init__(self, addr, name):
        super().__init__('*%#x' % addr, internal=True); self.name = name; self.hits = 0
    def stop(self):
        self.hits += 1
        try:
            esp = reg('esp')
            ss = stack_strings(esp)
            regs = {r: '%#x' % reg(r) for r in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi')}
            rs = {r: as_string(reg(r)) for r in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi')}
            print('%s hit %d: strings %s regs %s %s' % (self.name, self.hits, ss, regs, {k: v for k, v in rs.items() if v}), flush=True)
            emit({'ev': self.name, 'hit': self.hits, 'strings': ss, 'regs': regs})
            if want and not state['patched']:
                for i, w, s in ss:
                    if s.startswith('level_') or s.startswith('tutorial_'):
                        p = u32(esp + 4 * i) if w != 'inline' else esp + 4 * i
                        b, e = u32(p + 4), u32(p + 8)
                        if len(want) == len(s):
                            wr(b, want.encode('utf-16le')); state['patched'] = True
                            print('patched %s -> %s in place at %#x' % (s, want, b), flush=True)
                        else:
                            print('level %s, want %s: lengths differ (no scratch yet)' % (s, want), flush=True)
                        break
        except Exception as ex:
            print(self.name, 'err', repr(ex), flush=True)
        return False
class TimeLog(gdb.Breakpoint):
    def __init__(self): super().__init__('*0x450c40', internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time(); state['last'] = now
        if state['t0'] is None:
            state['t0'] = now; open(HOME + '/nfh-bench/wine/logs/level_started', 'w').write('%.3f' % now)
        if state['tick'] <= 3 or state['tick'] % 600 == 0:
            esp = reg('esp')
            print('tick %d: rets %s' % (state['tick'], rets(esp)), flush=True)
            emit({'tick': state['tick'], 'ev': 'tickrets', 'rets': rets(esp)})
        emit({'tick': state['tick'], 'wall': round(now - state['t0'], 3), 'ev': 'tick'})
        return now - state['t0'] > secs
class RegHook(gdb.Breakpoint):
    """a __fastcall-ish script call: the String arguments in ecx / edx, the rest on the stack"""
    def __init__(self, addr, name, regs=('ecx', 'edx')):
        super().__init__('*%#x' % addr, internal=True); self.name, self.regs = name, regs
    def stop(self):
        try:
            esp = reg('esp')
            args = [as_string(reg(r)) or '%#x' % reg(r) for r in self.regs]
            st = [as_string(u32(esp + 4 + 4 * i)) or '%#x' % u32(esp + 4 + 4 * i) for i in range(3)]
            emit({'tick': state['tick'], 'ev': self.name, 'ret': '%#x' % u32(esp), 'args': args, 'stack': st})
            if state['n'] < 400: print(self.name, state['tick'], args, st, flush=True)
        except Exception as e:
            emit({'tick': state['tick'], 'ev': 'error', 'name': self.name, 'err': repr(e)})
        return False
def watchdog():
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > 15:
            print('WATCHDOG: no tick for 15 s (last tick %d)' % state['tick'], flush=True)
            os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()

Ctor(0x43ab40, 'gamelogic_ctor'); Ctor(0x439fe0, 'level_factory')
TimeLog()
RegHook(0x477f60, 'action'); RegHook(0x479da0, 'goto', ('edx', 'ecx')); RegHook(0x437f70, 'icon', ('ecx', 'edx'))
try:
    gdb.execute('continue')
except Exception as ex:
    print('continue ended:', repr(ex), flush=True)
log.flush()
print('done: %d ticks, %d records' % (state['tick'], state['n']), flush=True)
gdb.execute('kill')

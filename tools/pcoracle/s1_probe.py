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
HOME = os.path.expanduser('~'); LOGS = os.environ.get('WDBG_LOGS', HOME + '/nfh-bench/wine/logs')
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

log = open(LOGS + '/s1_%s.jsonl' % (want or 'cur'), 'w')
state = {'tick': 0, 't0': None, 'last': time.time(), 'n': 0, 'patched': False}
def emit(rec):
    log.write(json.dumps(rec) + '\n'); state['n'] += 1
    if state['n'] % 20 == 0: log.flush()
scratch = {'base': None, 'pos': 0}
def alloc_scratch():
    va = u32(0x4dc0f8)       # kernel32!VirtualAlloc through game.exe's import slot (0x423524)
    scratch['base'] = int(gdb.parse_and_eval('((unsigned int (*)(unsigned int, unsigned int, unsigned int, unsigned int))%#x)(0, 65536, 0x3000, 0x40)' % va))
def salloc(n):
    n = (n + 15) & ~15
    p = scratch['base'] + scratch['pos']; scratch['pos'] += n; wr(p, b'\0' * n); return p
class LevelName(gdb.Breakpoint):
    """a site where the level's name String is at hand: the session start fcn.00406970 (its stack holds
    it — scanned), the level factory's compare 0x43a2da (fcn.00413840([esp] String, [esp+4] "level_peep"))
    — the name patched to WDBG_LEVEL in place when the lengths agree, else into scratch memory with the
    String's begin / end repointed; `patch` on the first site only"""
    def __init__(self, addr, name, patch):
        super().__init__('*%#x' % addr, internal=True); self.hits = 0; self.name = name; self.patch = patch
    def stop(self):
        self.hits += 1
        try:
            esp = reg('esp')
            cands = [(i, u32(esp + 4 * i), as_string(u32(esp + 4 * i))) for i in range(40)]
            cands = [c for c in cands if c[2] is not None]
            regs = {r: as_string(reg(r)) for r in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi')}
            if self.hits <= 3 or any(c[2].startswith(('level_', 'tutorial_')) for c in cands):
                print('%s hit %d: %s regs %s' % (self.name, self.hits, [(i, '%#x' % w, s) for i, w, s in cands], {k: v for k, v in regs.items() if v}), flush=True)
            if not self.patch: return False
            if want and not state['patched']:
                for i, p, s in cands:
                    if s and (s.startswith('level_') or s.startswith('tutorial_')):
                        b, e = u32(p + 4), u32(p + 8)
                        if len(want) == len(s):
                            wr(b, want.encode('utf-16le'))
                        else:
                            if scratch['base'] is None: alloc_scratch()
                            data = want.encode('utf-16le') + b'\0\0'; buf = salloc(len(data)); wr(buf, data)
                            wr(p + 4, struct.pack('<II', buf, buf + len(data) - 2))
                        state['patched'] = True
                        print('patched %s -> %s (String at %#x)' % (s, want, p), flush=True)
                        break
        except Exception as ex:
            print('level_cmp err', repr(ex), flush=True)
        return False
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
    """the tick candidate: the GameLogic update's call of the level update (0x43b2f5 -> fcn.00439cd0),
    counted against the wall clock (12 a second expected)"""
    def __init__(self, addr=0x43b2f5): super().__init__('*%#x' % addr, internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time(); state['last'] = now
        if state['t0'] is None:
            state['t0'] = now; open(LOGS + '/level_started', 'w').write('%.3f' % now)
        if state['tick'] % 120 == 0:
            print('tick %d at %.2f s: %.2f a second' % (state['tick'], now - state['t0'], state['tick'] / (now - state['t0'])), flush=True)
        emit({'tick': state['tick'], 'wall': round(now - state['t0'], 3), 'ev': 'tick', 'actors': actor_states()})
        try:
            # the neighbour object's words that change, tick by tick (the position and animation fields)
            for name, o in list(actors.items()):
                w = [u32(o + 4 * i) for i in range(40)]
                prev = state.setdefault('words', {}).get(name)
                if prev is not None:
                    ch = {('+%#x' % (4 * i)): ('%#x' % a, '%#x' % b, as_string(b)) for i, (a, b) in enumerate(zip(prev, w)) if a != b}
                    if ch and state.get('shown', 0) < 80: print('ACTOR %s tick %d changes %s' % (name, state['tick'], ch), flush=True); state['shown'] = state.get('shown', 0) + 1
                state['words'][name] = w
        except Exception as e:
            print('nb err', repr(e), flush=True)
        return now - state['t0'] > secs
actors = {}
def actor_states():
    out = {}
    for name, a in actors.items():
        try:
            out[name] = {'w': ['%#x' % u32(a + 4 * i) for i in range(16)]}
        except Exception: pass
    return out
class Accept(gdb.Breakpoint):
    """the GameLogic update's message loop: each popped input message is accepted by the logger (0x43b18d)
    and the handler (0x43b1a3 / 0x43b1bd): `call [edx+8]` with ecx = the message — its vtable, words and
    Strings dumped for the first messages (the layouts of NFH1's GoToPosMsg / UseObjectMsg / CombineMsg)"""
    def __init__(self, addr): super().__init__('*%#x' % addr, internal=True); self.addr = addr; self.n = 0
    def stop(self):
        try:
            if state['t0'] is None: return False          # (the setup flood before the first tick)
            self.n += 1
            if self.n <= 40:
                m = reg('ecx'); words = [u32(m + 4 * i) for i in range(12)]
                strs = {('+%#x' % (4 * i)): as_string(w) for i, w in enumerate(words) if as_string(w)}
                print('MSG at %#x #%d tick %d: vt %#x words %s strings %s' % (self.addr, self.n, state['tick'], words[0], ['%#x' % w for w in words], strs), flush=True)
                emit({'tick': state['tick'], 'ev': 'msg', 'site': '%#x' % self.addr, 'vt': '%#x' % words[0], 'words': ['%#x' % w for w in words], 'strings': strs})
        except Exception as e:
            print('accept err', repr(e), flush=True)
        return False
class Mover(gdb.Breakpoint):
    """the mover's update (vtable 0x4e59e8, update 0x47cb50; ecx = the mover): its words and the objects
    they point to, to find the actor object (its animation +0x3c per lap_model.py) — the first hits"""
    def __init__(self): super().__init__('*0x47cb50', internal=True); self.n = 0
    def stop(self):
        try:
            self.n += 1
            # the mover's update takes the actor as its second stack argument ([esp+8] at the entry: `mov
            # esi, [esp+0x54]` after the 0x4c-byte prologue; `mov edi, [esi+0x38]` its gait, fcn.00444690
            # its position; the first argument, ebx, is the game logic object — +0x68 the level name)
            a = u32(reg('esp') + 8)
            if a and a not in actors.values():
                words = [u32(a + 4 * i) for i in range(32)]
                strs = {('+%#x' % (4 * i)): as_string(w) for i, w in enumerate(words) if as_string(w)}
                name = strs.get('+0x4') or ('actor%d' % len(actors))
                actors[name] = a
                print('ACTOR %s at %#x: words %s strings %s' % (name, a, ['%#x' % w for w in words], strs), flush=True)
            if self.n <= 2 or self.n % 100 == 0:
                m = reg('ecx'); words = [u32(m + 4 * i) for i in range(16)]
                inner = {}
                for i, w in enumerate(words):
                    if 0x10000 < w < 0x7fffffff:
                        try:
                            ws = [u32(w + 4 * j) for j in range(20)]
                            ss = {('+%#x' % (4 * j)): as_string(x) for j, x in enumerate(ws) if as_string(x)}
                            if ss: inner['+%#x' % (4 * i)] = (['%#x' % x for x in ws[:16]], ss)
                        except Exception: pass
                print('MOVER #%d tick %d: ecx %#x words %s inner %s' % (self.n, state['tick'], m, ['%#x' % w for w in words], inner), flush=True)
        except Exception as e:
            print('mover err', repr(e), flush=True)
        return False
class RegHook(gdb.Breakpoint):
    """a script call: the String arguments on the stack (DoAction: [esp+8] object, [esp+0xc] action — as
    GameLogic.dll's), ecx / edx kept for the calls that take them"""
    def __init__(self, addr, name, regs=('ecx', 'edx')):
        super().__init__('*%#x' % addr, internal=True); self.name, self.regs = name, regs
    def stop(self):
        try:
            esp = reg('esp')
            args = [as_string(reg(r)) or '%#x' % reg(r) for r in self.regs]
            st = [as_string(u32(esp + 4 + 4 * i)) or '%#x' % u32(esp + 4 + 4 * i) for i in range(4)]
            emit({'tick': state['tick'], 'ev': self.name, 'ret': '%#x' % u32(esp), 'args': args, 'stack': st})
            if state['n'] < 600: print(self.name, state['tick'], args, st, flush=True)
            self.hits = getattr(self, 'hits', 0) + 1
            if self.hits <= 2 and self.name == 'icon':
                o = reg('ecx'); words = [u32(o + 4 * i) for i in range(24)]
                print('  icon ecx object: %s strings %s' % (['%#x' % w for w in words], {i: as_string(w) for i, w in enumerate(words) if as_string(w)}), flush=True)
        except Exception as e:
            emit({'tick': state['tick'], 'ev': 'error', 'name': self.name, 'err': repr(e)})
        return False
def watchdog():
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > 60:
            print('WATCHDOG: no tick for 60 s (last tick %d)' % state['tick'], flush=True)
            os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()

LevelName(0x406970, 'session', True); LevelName(0x43a2da, 'factory_cmp', False)
TimeLog()
Accept(0x43b1a3); Accept(0x43b1bd); Mover()
RegHook(0x477f60, 'action'); RegHook(0x479da0, 'goto', ('edx', 'ecx')); RegHook(0x437f70, 'icon', ('ecx', 'edx'))
try:
    gdb.execute('continue')
except Exception as ex:
    print('continue ended:', repr(ex), flush=True)
log.flush()
print('done: %d ticks in %.1f s (%.2f a second), %d records' % (state['tick'], (state['last'] - state['t0']) if state['t0'] else 0, state['tick'] / ((state['last'] - state['t0']) or 1) if state['t0'] else 0, state['n']), flush=True)
gdb.execute('kill')

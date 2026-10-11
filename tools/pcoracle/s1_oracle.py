"""gdb (winedbg proxy) script: NFH1's game.exe as an oracle — one level run with a tick-stamped input script
or the port's plan, and a per-tick trace; the Season 1 twin of oracle.py (the game logic is in game.exe).

    WDBG_LEVEL=level_peep WDBG_SECS=200 WDBG_CLICKS="400 300 4  414 313 4  65 116 3  750 555 1" \\
        python3 wdbg.py nfh1 $PWD/s1_oracle.py 400       # (s1smoke.sh wraps it: S1SCRIPT=s1_oracle.py)

The level: the session start fcn.00406970 holds the level's name String on its stack (word 13 — the menu's
button name, tutorial_1 for the first), patched to WDBG_LEVEL (in place, or into VirtualAlloc'd scratch —
the IAT slot 0x4dc0f8 — with the String's begin / end repointed). The tick: the GameLogic update's call of
the level update, 0x43b2f5 -> fcn.00439cd0 (12 a second). The actors: the mover's update fcn.0047cb50 takes
the actor as its second stack argument — +4 name, +0x28 x, +0x2c y, +0x3c animation. The inputs: the
update's message loop pops each input message into [esp+0x18] at 0x43b165 (after `call [eax+0xc]`), where a
dummy floor click's GoToPosMsg (vtable 0x4e79fc: +4 room, +0xc x, +0x10 y, refcount +0x18) is replaced by
the built one — UseObjectMsg 0x4e77e4 (+4 name, +8 text, refcount +0x10), CombineMsg 0x4e7a14 (as
GameLogic.dll's: +4 object, +8 object2, +0xc text, offsets, refcount +0x1c). The script calls: DoAction
fcn.00477f60 ([esp+8] object, [esp+0xc] action), SetIcon fcn.00437f70 ([esp+4] icon). The trace:
$WDBG_LOGS/oracle_<level>.jsonl, as oracle.py's (tick records with the actors' x/y/anim, action, icon,
injected, leg); the game's own GameLogicLog records the tick of every message (loggamelogic on)."""
import gdb, os, re, sys, time, struct, json, subprocess, threading, signal
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '60'))
HOME = os.path.expanduser('~'); LOGS = os.environ.get('WDBG_LOGS', HOME + '/nfh-bench/wine/logs')
T = os.path.dirname(os.path.abspath(__file__))
DUMMY = os.environ.get('WDBG_DUMMY', '400 300').split()
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

# --- scratch memory and synthetic messages ---
VT_GOTO, VT_USE, VT_COMBINE = 0x4e79fc, 0x4e77e4, 0x4e7a14
scratch = {'base': None, 'pos': 0, 'sproto': None}
def alloc_scratch():
    va = u32(0x4dc0f8)       # kernel32!VirtualAlloc through game.exe's import slot (0x423524)
    scratch['base'] = int(gdb.parse_and_eval('((unsigned int (*)(unsigned int, unsigned int, unsigned int, unsigned int))%#x)(0, 262144, 0x3000, 0x40)' % va))
def salloc(n):
    n = (n + 15) & ~15
    p = scratch['base'] + scratch['pos']; scratch['pos'] += n; wr(p, b'\0' * n); return p
def make_string(text):
    """a core String {vtable, begin, end, +0xc, refcount +0x10} cloned from a live one"""
    data = text.encode('utf-16le') + b'\0\0'
    buf = salloc(len(data)); wr(buf, data)
    obj = salloc(32); wr(obj, rd(scratch['sproto'], 32))
    wr(obj + 4, struct.pack('<II', buf, buf + len(data) - 2)); wr(obj + 0x10, struct.pack('<I', 0x1000))
    return obj
def msg_use(name):
    m = salloc(0x40); wr(m, struct.pack('<IIIII', VT_USE, make_string(name), make_string('oracle'), 0, 0x1000)); return m
def msg_combine(obj, item, offset=(0, 0), flag18=0):
    m = salloc(0x40); wr(m, struct.pack('<IIIIiiII', VT_COMBINE, make_string(obj), make_string(item), make_string('oracle'), offset[0], offset[1], flag18, 0x1000)); return m
def msg_goto(room, x, sneak=False):
    m = salloc(0x40); wr(m, struct.pack('<IIIIIII', VT_GOTO, make_string(room), 0, int(x), 0, 1 if sneak else 0, 0x1000)); return m
def build(step):
    k, a = step['kind'], step['args']
    if k == 'use': return msg_use(a[0])
    if k == 'combine': return msg_combine(a[0], a[1], tuple(step.get('offset', (0, 0))), step.get('flag18', 0))
    if k == 'goto': return msg_goto(a[0], a[1], step.get('sneak', False))
    raise ValueError(k)

script = json.load(open(os.environ['WDBG_SCRIPT'])) if os.environ.get('WDBG_SCRIPT') else []
script.sort(key=lambda s: s['tick'])
pending = []
state = {'tick': 0, 't0': None, 'last': time.time(), 'n': 0, 'actions': {}, 'credits': [], 'declines': [], 'caught': [], 'sneak': False, 'patched': False}
actors = {}
import importlib.util
_spec = importlib.util.spec_from_file_location('pcmap_s1', os.path.join(T, 'pcmap_s1.py')); pcmap_s1 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(pcmap_s1)
sys.modules['pcmap'] = pcmap_s1          # the plan runner's `import pcmap` is the Season 1 map here
class PlanRunner:
    """the port's plan on the oracle: one leg at a time, its condition read off the trace each tick"""
    # (Woody stands in ms0-3; after a trick's action he keeps its `smile` until the next command — the
    # 202 pond's put_eel at tick 290 smiled 390 ticks, until the neighbour came up and caught him)
    STANDS = ('ms0', 'ms1', 'ms2', 'ms3', 'smile')
    TIMEOUT = 12 * 120
    def __init__(self, path, n):
        sys.path.insert(0, T)
        import pcmap
        self.m = pcmap.PCMap(n)
        self.legs = [l.split('#')[0].split() for l in open(path) if l.split('#')[0].strip()]
        self.i = 0; self.leg_start = 0; self.phase = 'idle'; self.target = None; self.results = []
        self.last_input = -100; self.tricked = {}
    def woody(self):
        return actors.get('woody') and actor_states().get('woody')
    def idle(self, w):
        # (Woody is in `actors` from his first walk on; before it he stands where the level put him)
        return w is None or w['anim'] in self.STANDS
    def acts_on(self, obj, since=0):
        """the actions logged on the object's family (the guarded / container variants) since a tick"""
        fam = self.m.family(obj)
        return sorted((t, a) for o, l in state['actions'].items() if '/' in o and self.m.family(o) == fam
                      for t, a in l if t >= since)
    def step(self, tick):
        """returns the steps to inject this tick"""
        if self.i >= len(self.legs): return []
        leg = self.legs[self.i]; op, args = leg[0], leg[1:]
        op = op.rstrip('!')
        w = self.woody()
        if self.phase == 'idle':
            self.leg_start = tick
            if op in ('take', 'use', 'usewith', 'prime', 'unlock'):
                self.phase = 'wait_idle'
            elif op == 'park':
                room, x = self.m.zone_center(args[0])
                if room is None: return self.done('no room for %s' % args[0])
                self.phase = 'parking'; self.target = args[0]
                return [{'tick': tick, 'kind': 'goto', 'args': [room, x], 'sneak': state['sneak'], 'leg': ' '.join(leg)}]
            elif op == 'whenusing':
                self.phase = 'whenusing'; self.target = self.m.station(args[0])
                if self.target is None: return self.done('no station for %s' % args[0])
            elif op == 'await':
                self.phase = 'await'; self.target = self.tricked.get(args[0], tick)
            elif op == 'wait':
                self.phase = 'wait'; self.target = tick + int(float(args[0]) * 12)
            elif op == 'until':
                self.phase = 'wait'; self.target = int(float(args[0]) * 12)
            elif op == 'sneak':
                state['sneak'] = args[0] == 'on'; return self.done('sneak %s' % args[0])
            else:
                return self.done('skipped')
        if self.phase == 'wait_idle':
            # (a take right after the item's unlock: the PC's minigame success took it already)
            if op == 'take' and self.i > 0 and self.legs[self.i - 1][0].rstrip('!') == 'unlock' \
                    and self.legs[self.i - 1][1] == args[0]:
                obj = self.m.use_target(args[0])
                if any(a == 'take' for t, a in self.acts_on(obj, self.results[-1].get('start', 0))):
                    return self.done('taken with the unlock')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout waiting for Woody')
            if not self.idle(w) or tick - self.last_input < 6: return []
            if op in ('usewith', 'prime', 'unlock') and len(args) > 1:
                obj, game = self.m.combine_target(args[0], self.m.pc_item(args[1]))
                if obj is None: return self.done('no PC object for %s' % args[0])
                step = {'tick': tick, 'kind': 'combine', 'args': [obj, self.m.pc_item(args[1])]}
            else:
                obj = self.m.use_target(args[0])
                if obj is None: return self.done('no PC object for %s' % args[0])
                step = {'tick': tick, 'kind': 'use', 'args': [obj]}
            step['leg'] = ' '.join(leg); self.target = obj; self.phase = 'acting'; self.last_input = tick
            self.acted = len(self.acts_on(obj)); self.declined = len(state['declines'])
            return [step]
        if self.phase == 'acting':
            if len(state['declines']) > self.declined: return self.done('declined')
            acts = self.acts_on(self.target)
            if len(acts) > self.acted and tick - acts[-1][0] >= 3 and self.idle(w):
                if op in ('usewith', 'use'): self.tricked[args[0]] = tick
                return self.done('ok')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
            return []
        if self.phase == 'parking':
            pr = self.m.rooms.get(self.target)
            if w is not None and self.idle(w) and tick - self.last_input >= 6 and pr and \
                    pr['x1'] - 120 <= w['x'] <= pr['x2'] + 120 and abs(w['y'] - pr['floor']) <= 150:
                return self.done('ok')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
            return []
        if self.phase == 'whenusing':
            acts = self.acts_on(self.target, self.leg_start)
            if acts and acts[-1][1] != 'leave': return self.done('ok')
            return []
        if self.phase == 'await':
            if any(t >= self.target for t in state['credits']): return self.done('ok')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
            return []
        if self.phase == 'wait':
            if tick >= self.target: return self.done('ok')
            return []
        return []
    def done(self, why):
        leg = ' '.join(self.legs[self.i])
        self.results.append({'leg': leg, 'why': why, 'start': self.leg_start, 'tick': state['tick']})
        print('LEG %-40s %s at tick %d' % (leg, why, state['tick']), flush=True)
        emit({'tick': state['tick'], 'ev': 'leg', 'leg': leg, 'why': why})
        self.i += 1; self.phase = 'idle'; self.last_input = state['tick'] if why == 'ok' else self.last_input
        return []
plan = PlanRunner(os.environ['WDBG_PLAN'], int(os.environ['WDBG_LEVELNUM'])) if os.environ.get('WDBG_PLAN') else None
log = open(LOGS + '/oracle_%s.jsonl' % (want or 'cur'), 'w')
def emit(rec):
    log.write(json.dumps(rec) + '\n'); state['n'] += 1
    if state['n'] % 50 == 0: log.flush()
def actor_states():
    out = {}
    for name, a in actors.items():
        try:
            out[name] = {'x': struct.unpack('<i', rd(a + 0x28, 4))[0], 'y': struct.unpack('<i', rd(a + 0x2c, 4))[0], 'anim': as_string(u32(a + 0x3c))}
        except Exception: pass
    return out
LEAD = int(os.environ.get('WDBG_LEAD', '4'))
def click_dummy():
    subprocess.Popen([T + '/xdotool-result/bin/xdotool', 'mousemove', DUMMY[0], DUMMY[1], 'sleep', '0.3',
                      'mousedown', '1', 'sleep', '0.2', 'mouseup', '1'],
                     env=dict(os.environ, DISPLAY=os.environ.get('WDBG_DISPLAY', ':97')))
def watchdog():
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > float(os.environ.get('WDBG_WATCHDOG', '20')):
            print('WATCHDOG: no tick for %s s (last tick %d)' % (os.environ.get('WDBG_WATCHDOG', '20'), state['tick']), flush=True)
            os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()

class LevelName(gdb.Breakpoint):
    """the session start fcn.00406970: the level's name String on its stack, patched to WDBG_LEVEL"""
    def __init__(self): super().__init__('*0x406970', internal=True)
    def stop(self):
        try:
            esp = reg('esp')
            for i in range(40):
                p = u32(esp + 4 * i); s = as_string(p)
                if s and s.startswith(('level_', 'tutorial_')):
                    print('level %s (stack word %d)' % (s, i), flush=True)
                    if want and not state['patched'] and want != s:
                        b, e = u32(p + 4), u32(p + 8)
                        if len(want) == len(s):
                            wr(b, want.encode('utf-16le'))
                        else:
                            if scratch['base'] is None: alloc_scratch()
                            data = want.encode('utf-16le') + b'\0\0'; buf = salloc(len(data)); wr(buf, data)
                            wr(p + 4, struct.pack('<II', buf, buf + len(data) - 2))
                        state['patched'] = True; print('patched to %s' % want, flush=True)
                    break
        except Exception as ex:
            print('level name err', repr(ex), flush=True)
        return False
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*0x43b2f5', internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time(); state['last'] = now
        if state['t0'] is None:
            state['t0'] = now; open(LOGS + '/level_started', 'w').write('%.3f' % now)
        if state['tick'] == 1 and scratch['base'] is None: alloc_scratch()
        while script and script[0]['tick'] - LEAD <= state['tick']:
            step = script.pop(0); pending.append(step); click_dummy()
            emit({'tick': state['tick'], 'ev': 'dummy', 'for': step})
        if plan is not None and state['tick'] > 2:
            for step in plan.step(state['tick']):
                pending.append(step); click_dummy()
                emit({'tick': state['tick'], 'ev': 'dummy', 'for': step})
        emit({'tick': state['tick'], 'wall': round(now - state['t0'], 3), 'ev': 'tick', 'actors': actor_states()})
        return now - state['t0'] > secs
class Loop(gdb.Breakpoint):
    """the message loop after the pop (0x43b165): the message at [esp+0x18]; a player's message with a
    step pending is replaced by the built one"""
    def __init__(self): super().__init__('*0x43b165', internal=True)
    def stop(self):
        try:
            esp = reg('esp'); msg = u32(esp + 0x18); vt = u32(msg)
            if vt in (VT_GOTO, VT_USE, VT_COMBINE):
                if scratch['sproto'] is None: scratch['sproto'] = u32(msg + 4)
                if pending:
                    step = pending.pop(0); new = build(step)
                    wr(esp + 0x18, struct.pack('<I', new))
                    emit({'tick': state['tick'], 'ev': 'injected', 'step': step})
                    print('INJECTED tick %d: %s' % (state['tick'], step), flush=True)
                else:
                    emit({'tick': state['tick'], 'ev': 'click', 'vt': '%#x' % vt, 'a': as_string(u32(msg + 4)), 'b': as_string(u32(msg + 8)) or u32(msg + 0xc)})
        except Exception as e:
            print('loop err', repr(e), flush=True)
        return False
class Mover(gdb.Breakpoint):
    """the mover's update fcn.0047cb50: its second argument is the actor (+4 name)"""
    def __init__(self): super().__init__('*0x47cb50', internal=True)
    def stop(self):
        try:
            a = u32(reg('esp') + 8); name = as_string(u32(a + 4))
            if name and name not in actors: actors[name] = a
        except Exception: pass
        return False
class Hook(gdb.Breakpoint):
    def __init__(self, addr, name, nargs=4):
        super().__init__('*%#x' % addr, internal=True); self.name, self.nargs = name, nargs
    def stop(self):
        try:
            esp = reg('esp')
            args = decode_args(esp, self.nargs)
            emit({'tick': state['tick'], 'ev': self.name, 'ret': '%#x' % u32(esp), 'args': args})
            if self.name == 'action' and isinstance(args[1], str):
                state['actions'].setdefault(args[1], []).append((state['tick'], args[2]))
                if args[1] == 'woody' and args[2] == 'decline': state['declines'].append(state['tick'])
                if args[1] == 'woody' and args[2] in ('fight', 'respawn'):
                    state['caught'].append((state['tick'], args[2])); print('CAUGHT tick %d: %s' % (state['tick'], args[2]), flush=True)
        except Exception as e:
            emit({'tick': state['tick'], 'ev': 'error', 'name': self.name, 'err': repr(e)})
        return False

LevelName(); Tick(); Loop(); Mover()
Hook(0x477f60, 'action'); Hook(0x437f70, 'icon', 2)
try:
    gdb.execute('continue')
except Exception as ex:
    print('continue ended:', repr(ex), flush=True)
log.flush()
print('done: %d ticks, %d records, %d script steps left' % (state['tick'], state['n'], len(script) + len(pending)), flush=True)
if plan is not None:
    json.dump(plan.results, open(LOGS + '/oracle_%s_legs.json' % (want or 'cur'), 'w'), indent=1)
    print('plan: %d/%d legs, %s; caught %s' % (plan.i, len(plan.legs), [r['why'] for r in plan.results], state['caught']), flush=True)
gdb.execute('kill')

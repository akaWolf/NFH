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

WDBG_PLAN=<port plan file> runs the port's plan (tests/plans/pc/...) instead, its legs mapped by pcmap.py
and its conditions read off the trace: a take / use / usewith / prime / unlock waits for Woody to stand
idle, injects, and is done when his action on the object has run and he stands again (or he declined);
park waits for his arrival in the zone's room; whenusing X for the neighbour's next action on X's object;
await X for the next trick record paid; wait / until for the clock; sneak sets the walks' sneaking.

The trace (~/nfh-bench/wine/logs/oracle_<level>.jsonl): per tick the actors' x/y/anim (GameLogic's actor
object: +0x2c, +0x30, +0x40 — captured from the path finder fcn.1000a711), and the script elements — GoTo
fcn.1000e3e0, DoAction fcn.10002cd5, icon fcn.100422a5, behaviour post fcn.1004000a, SHOUT fcn.1000f977, a trick record paid fcn.100522e6 —
with the calling step's return address. The level tick is fcn.10044234 (12 a second)."""
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
    # (winedbg's proxy garbles a memory write past 32 bytes — the chunk after the first repeated bytes
    # 16..31 —: 16 bytes a packet, read back)
    for i in range(0, len(b), 16):
        inf.write_memory(a + i, b[i:i + 16])
    if bytes(inf.read_memory(a, len(b))) != bytes(b):
        raise RuntimeError('memory write mismatch at %#x' % a)
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
lg = open(LOGS + '/winedbg.log').read()
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
USETEXT = os.environ.get('WDBG_USETEXT', 'oracle')      # the message's text field (a probe of the GUI's own value)
def msg_use(name, sneak=False):
    # (+0xc the sneaking byte the GUI sets from its flag — game.exe fcn.00408161 @ 0x40841f)
    m = salloc(0x40); wr(m, struct.pack('<IIIII', 0x453b2c, make_string(name), make_string(USETEXT), 1 if sneak else 0, 0x1000)); return m
def msg_combine(obj, item, offset=(0, 0), flag18=0):
    # item None: the GUI's own click on a `game` object without a tool (game.exe fcn.00408161 @ 0x40828a: the
    # object found with flag 0x80 -> a CombineMsg whose second object is NULL) — the tool-less dexterity unlock
    m = salloc(0x40); wr(m, struct.pack('<IIIIiiII', 0x453b20, make_string(obj), make_string(item) if item is not None else 0, make_string('oracle'), offset[0], offset[1], flag18, 0x1000)); return m
def msg_goto(room, x, sneak=False):
    m = salloc(0x40); wr(m, struct.pack('<IIIIIBBHI', 0x453b38, make_string(room), 0, int(x), 0, 1 if sneak else 0, 0, 0, 0x1000)); return m
def build(step):
    k, a = step['kind'], step['args']
    if k == 'use': return msg_use(a[0], step.get('sneak', False))
    if k == 'combine': return msg_combine(a[0], a[1], tuple(step.get('offset', (0, 0))), step.get('flag18', 1 if step.get('sneak') else 0))
    if k == 'goto': return msg_goto(a[0], a[1], step.get('sneak', False))
    raise ValueError(k)

script = json.load(open(os.environ['WDBG_SCRIPT'])) if os.environ.get('WDBG_SCRIPT') else []
script.sort(key=lambda s: s['tick'])
pending = []          # messages built, waiting for a dummy click to replace
state = {'tick': 0, 't0': None, 'last': time.time(), 'n': 0, 'actions': {}, 'credits': [], 'declines': [], 'caught': [], 'sneak': False}
actors = {}

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
    def idle(self, w, strict=False):
        # (Woody is in `actors` from his first walk on; before it he stands where the level put him; hidden
        # in a wardrobe, a bed or a pipe after a `hide` leg he is as good as standing — a click brings him out)
        if getattr(self, 'hidden', False) and w is not None and w['anim'] not in ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3'):
            return True
        if w is None or w['anim'] in self.STANDS: return True
        # an action without an actornextanim leaves him on its last frame (208's `take3` held 48 s after the
        # shovel): any pose that is no gait and no catch, unchanged for two seconds, is a stand — except for
        # a leg whose action runs long on purpose (an unlock's minigame: `strict`, the stands alone)
        if strict or w['anim'] in self.GAITS or w['anim'].startswith(('fear', 'fight', 'respawn', 'fly_away')): return False
        return state['tick'] - getattr(self, '_anim_since', state['tick']) >= 24
    CATCHERS = ('neighbor', 'mother')
    ROLES = {'Rottweiler': 'neighbor', 'Mother': 'mother', 'Olga': 'olga', 'Woody': 'woody'}
    def room_of(self, a):
        """an actor's PC room: by name where the trace carries it (Season 1), else the PCRoom whose x range and
        floor hold his position (Season 2's overlays)"""
        if a is None: return None
        if a.get('room') is not None: return a['room']
        for z, pr in self.m.rooms.items():
            if pr['x1'] - 60 <= a['x'] <= pr['x2'] + 60 and abs(a['y'] - pr['floor']) <= 150: return pr['room']
        return None
    GAITS = ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3')
    def gate_closed(self, room):
        """the port's runner walks into a room only when its gate is open — no catcher in it, none due there
        while Woody works (tests/run_tricks.py gate_open reads the routine's ETAs); here, without a model of
        the PC's routine: no catcher stands in the room and none is on a walk (a walking catcher's target is
        unknown — he may be coming; he stops within seconds)"""
        if not room: return False
        st = actor_states(); w = st.get('woody')
        # the rooms on Woody's way too (the port's door graph; the PC's path finder may differ)
        rooms = set(self.m.geo.route(self.room_of(w) if w else None, room)) | {room}
        for c in self.CATCHERS:
            if c not in self.present: continue
            a = st.get(c)
            if a is None: return True                   # (no state: he is in a door pass — a walk)
            if self.blind(c, a): continue
            if self.room_of(a) in rooms: return True
            if a['anim'] in self.GAITS:
                # his walk's target: the goto hook's last destination object for his actor pointer
                d = state.get('dest', {}).get(actors.get(c))
                dest = d[1].split('/')[0] if d and isinstance(d[1], str) and '/' in d[1] else None
                if dest is None or dest in rooms: return True
        return False
    def blind(self, c, a):
        """the catcher inside a hideout station — the PC's flag 4 (tools/pcref/pc_catch_s2.py: the enter step of an
        object carrying hideout / neighbor_hideout sets it, its leave step clears it; the catch predicate skips
        either object carrying it): his last walk's target on NFH2 (the goto hook), on NFH1 any neighbor_hideout
        object whose last action is an enter or a sleep, while he stands"""
        if a['anim'] in self.GAITS: return False
        ins = state.get('inside', {}); d = state.get('dest', {}).get(actors.get(c))
        objs = [d[1]] if d and isinstance(d[1], str) else [o for o, k in self.m.hideouts.items() if k == 'neighbor_hideout']
        fams = set(self.m.family(o) for o in objs if o in self.m.hideouts or self.m.family(o) in set(self.m.family(h) for h in self.m.hideouts))
        return any(v[0] and self.m.family(o) in fams for o, v in ins.items())       # (the guarded / plain variants are one)
    @property
    def present(self):
        """the catchers the level has (a state seen once)"""
        if not hasattr(self, '_present'): self._present = set()
        self._present |= set(c for c in self.CATCHERS if c in actor_states())
        return self._present
    def acts_on(self, obj, since=0):
        """the actions logged on the object's family (the guarded / container variants) since a tick"""
        fam = self.m.family(obj)
        return sorted((t, a) for o, l in state['actions'].items() if '/' in o and self.m.family(o) == fam
                      for t, a in l if t >= since)
    def step(self, tick):
        """returns the steps to inject this tick"""
        if self.i >= len(self.legs): return []
        leg = self.legs[self.i]; op, args = leg[0], leg[1:]
        ungated = op.endswith('!'); op = op.rstrip('!')     # `!`: the port runs the leg without its gate
        w = self.woody()
        if w is not None and w['anim'] != getattr(self, '_last_anim', None):
            self._last_anim = w['anim']; self._anim_since = tick
        if self.phase == 'idle':
            if getattr(self, '_idle_leg', None) != self.i: self.leg_start = tick; self._idle_leg = self.i
            if op == 'hide' and getattr(self, 'hidden', False) and getattr(self, 'hidden_in', None) == args[0]:
                # (the port's hide while hidden is a no-op; the PC's second use of the wardrobe brings him
                # out for a walk and in again — 106's Woody was caught on it)
                return self.done('already hidden')
            if op in ('take', 'use', 'usewith', 'prime', 'unlock', 'hide'):
                self.phase = 'wait_idle'          # (`hide`: the PC's use of the wardrobe or bed — he stays in)
            elif op == 'park':
                room, x = self.m.zone_center(args[0])
                if room is None: return self.done('no room for %s' % args[0])
                if not ungated and self.gate_closed(room):
                    if tick - self.leg_start > self.TIMEOUT: return self.done('timeout at the gate')
                    return []                      # the gate: the room free of the catchers first
                self.phase = 'parking'; self.target = args[0]
                return [{'tick': tick, 'kind': 'goto', 'args': [room, x], 'sneak': state['sneak'], 'leg': ' '.join(leg)}]
            elif op == 'walk':
                # `walk x y`: the world point's zone on its PC room (pcgeo: the port's own geometry)
                room, px = self.m.walk_point(float(args[0]), float(args[1]))
                if room is None: return self.done('no room for the walk')
                if not ungated and self.gate_closed(room):
                    if tick - self.leg_start > self.TIMEOUT: return self.done('timeout at the gate')
                    return []
                self.phase = 'walking'; self.target = (room, px); self.last_input = tick
                return [{'tick': tick, 'kind': 'goto', 'args': [room, int(round(px))], 'sneak': state['sneak'], 'leg': ' '.join(leg)}]
            elif op == 'whenanim':
                # `whenanim Role Anim` (tests/run_tricks.py leg_whenanim): the pawn's phase — a sleep or a hide
                # is his hideout's flag 4 here, a walk his gait, another name the next animation of his own
                self.phase = 'whenanim'; self.target = (self.ROLES.get(args[0], args[0].lower()), args[1])
                self._anim0 = (actor_states().get(self.target[0]) or {}).get('anim')
            elif op == 'whenin':
                # `whenin Role Zone`: the pawn in the zone's PC room (tests/run_tricks.py leg_whenin)
                self.phase = 'whenin'; self.target = (self.ROLES.get(args[0], args[0].lower()), self.m.rooms.get(args[1]))
                if self.target[1] is None: return self.done('no room for %s' % args[1])
            elif op == 'activated':
                # (the port parks until the item's GameObject is active — a game event's SetActive; the PC's
                # object is in its scene throughout or comes with the same event: three seconds here, the
                # take's own timeout covers the rest)
                self.phase = 'wait'; self.target = tick + 36
            elif op == 'whenusing':
                self.phase = 'whenusing'; self.target = self.m.station(args[0])
                if self.target is None: return self.done('no station for %s' % args[0])
            elif op == 'whenzone':
                # the neighbour in the zone's PC room: his room by name (Season 1's actors carry it), else his
                # position within the room's x range and floor
                self.phase = 'whenzone'; self.target = self.m.rooms.get(args[0])
                if self.target is None: return self.done('no room for %s' % args[0])
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
            # the gate: the target's room free of the catchers before the input goes
            tgt = self.m.use_target(args[0]) if op not in ('usewith', 'prime', 'unlock') else (self.m.combine_target(args[0], self.m.item_name(args[0], args[1]) if len(args) > 1 else None)[0])
            if tgt and not ungated and self.gate_closed(tgt.split('/')[0]): return []
            if op == 'usewith' and args[0].startswith('Ground@'):
                # a floor trick: the combination of the zone's room object with the item at the drop's x
                mx = next((float(o[2:]) for o in args[2:] if o.startswith('x=')), None)
                room, px, pcname, result = self.m.floor_target(args[0].split('@', 1)[1], mx, args[1])
                if room is None: return self.done('no floor for %s' % args[0])
                if not ungated and self.gate_closed(room): return []
                step = {'tick': tick, 'kind': 'combine', 'args': [room, pcname], 'offset': (int(round(px)), 0)}
                obj = result or room
            elif op in ('usewith', 'prime', 'unlock') and len(args) > 1:
                pcname = self.m.item_name(args[0], args[1])
                obj, game = self.m.combine_target(args[0], pcname)
                if obj is None: return self.done('no PC object for %s' % args[0])
                step = {'tick': tick, 'kind': 'combine', 'args': [obj, pcname]}
            elif op == 'unlock':
                # a dexterity unlock without a tool: the GUI's click on the minigame combination's own object
                # is a CombineMsg with no second object (msg_combine); its UseObjectMsg only walks him there
                obj, game = self.m.combine_target(args[0], None)
                if obj is None: return self.done('no PC object for %s' % args[0])
                step = {'tick': tick, 'kind': 'combine', 'args': [obj, None]}
            else:
                obj = self.m.use_target(args[0])
                if obj is None: return self.done('no PC object for %s' % args[0])
                if op == 'use' and self.m.single_combo(obj):
                    # a bare trick that is a single-object combination (101's TV): the GUI's NULL combine
                    step = {'tick': tick, 'kind': 'combine', 'args': [obj, None]}
                else:
                    step = {'tick': tick, 'kind': 'use', 'args': [obj]}
            step['leg'] = ' '.join(leg); step['sneak'] = state['sneak']; self.target = obj; self.phase = 'acting'; self.last_input = tick
            self.acted = len(self.acts_on(obj)); self.declined = len(state['declines'])
            return [step]
        if self.phase == 'acting':
            if len(state['declines']) > self.declined: return self.done('declined')
            acts = self.acts_on(self.target)
            if op == 'usewith' and args[0].startswith('Ground@'):
                acts = acts + [(t, a) for t, a in state['actions'].get('woody', []) if t > self.leg_start and a not in ('start', 'fear1', 'fear2', 'fear3', 'fight', 'respawn', 'decline')]
                acts.sort()
            if op == 'hide' and len(acts) > self.acted and tick - acts[-1][0] >= 3:
                self.hidden = True; self.hidden_in = args[0]; return self.done('ok')
            if len(acts) > self.acted and tick - acts[-1][0] >= 3 and self.idle(w, strict=(op == 'unlock')):
                if op in ('usewith', 'use'): self.tricked[args[0]] = tick
                if w is not None and w['anim'] in self.STANDS: self.hidden = False
                return self.done('ok')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
            return []
        if self.phase == 'walking':
            room, px = self.target
            if w is not None and self.idle(w) and tick - self.last_input >= 6 and abs(w['x'] - px) <= 40 \
                    and (w.get('room') is None or w['room'] == room):
                return self.done('ok')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
            return []
        if self.phase == 'whenanim':
            role, anim = self.target; a = actor_states().get(role)
            if a is not None and tick - self.leg_start > 3:
                if 'Sleep' in anim or 'Hide' in anim:
                    if self.blind(role, a): return self.done('ok')
                elif 'Walk' in anim:
                    if a['anim'] in self.GAITS: return self.done('ok')
                elif a['anim'] != self._anim0 and a['anim'] not in self.GAITS and a['anim'] not in self.STANDS:
                    return self.done('ok (approximate: his next animation)')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
            return []
        if self.phase == 'whenin':
            role, pr = self.target; a = actor_states().get(role)
            if a is not None and tick - self.leg_start > 6:
                if a.get('room') is not None:
                    if a['room'] == pr['room']: return self.done('ok')
                elif pr['x1'] - 60 <= a['x'] <= pr['x2'] + 60 and abs(a['y'] - pr['floor']) <= 150:
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
        if self.phase == 'whenzone':
            nb = actor_states().get('neighbor'); pr = self.target
            if nb is not None and tick - self.leg_start > 6:
                if nb.get('room') is not None:
                    if nb['room'] == pr['room']: return self.done('ok')
                elif pr['x1'] - 60 <= nb['x'] <= pr['x2'] + 60 and abs(nb['y'] - pr['floor']) <= 150:
                    return self.done('ok')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
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
            out[name] = {'x': struct.unpack('<i', rd(a + 0x2c, 4))[0], 'y': struct.unpack('<i', rd(a + 0x30, 4))[0], 'anim': as_string(u32(a + 0x40))}
        except Exception: pass
    return out
LEAD = int(os.environ.get('WDBG_LEAD', '4'))      # ticks between the dummy's dispatch and the scripted tick
DUMMIES = [DUMMY] + [d.split() for d in os.environ.get('WDBG_DUMMIES', '400 400;300 450;500 450;400 500;200 400;600 400').split(';')]
def click_dummy():
    # (a dummy click that hits no floor sends no message: the Tick hook re-clicks the next point of
    # DUMMIES while a step stays pending)
    state['dummy_at'] = state['tick']; pt = DUMMIES[state.get('dummy_i', 0) % len(DUMMIES)]
    subprocess.Popen([T + '/xdotool-result/bin/xdotool', 'mousemove', pt[0], pt[1], 'sleep', '0.3',
                      'mousedown', '1', 'sleep', '0.2', 'mouseup', '1'],
                     env=dict(os.environ, DISPLAY=os.environ.get('WDBG_DISPLAY', ':97')))
def _click_dummy_old():
    # (the game polls the mouse at its 12 Hz: xdotool's instant click fell between two polls every other
    # time — the button is held 0.2 s; the move settles 0.3 s before; the message lands 3-4 ticks on)
    subprocess.Popen([T + '/xdotool-result/bin/xdotool', 'mousemove', DUMMY[0], DUMMY[1], 'sleep', '0.3',
                      'mousedown', '1', 'sleep', '0.2', 'mouseup', '1'],
                     env=dict(os.environ, DISPLAY=os.environ.get('WDBG_DISPLAY', ':97')))
def watchdog():
    shot = False
    while True:
        time.sleep(1)
        if state['t0'] is not None and time.time() - state['last'] > 6 and not shot:
            # the ticks stalled: a screenshot of what the game shows (a dialog after a catch?)
            shot = True
            try:
                subprocess.Popen([T + '/xwd-result/bin/xwd', '-root', '-silent', '-display', os.environ.get('WDBG_DISPLAY', ':97'),
                                  '-out', LOGS + '/stall_%s.xwd' % (want or 'cur')])
            except Exception as e:
                print('stall shot err', repr(e), flush=True)
        if state['t0'] is not None and time.time() - state['last'] > 8:
            print('WATCHDOG: no tick for 8 s (last tick %d)' % state['tick'], flush=True)
            os.kill(os.getpid(), signal.SIGINT); return
threading.Thread(target=watchdog, daemon=True).start()

class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % gl(0x10044234), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time(); state['last'] = now
        if state['t0'] is None:
            state['t0'] = now; open(LOGS + '/level_started', 'w').write('%.3f' % now)
        if state['tick'] == 1:
            # (the level's setup flood is before the first tick; the loop hook is cheap from here)
            alloc_scratch(); state['loop'].enabled = True
            if os.environ.get('WDBG_NOCATCH'):
                # an idle lap with Woody uncatchable: the trigger predicate of mode 1 (fcn.1003f573 — both
                # objects in one room, the target placed, neither carrying flag 4: tools/pcref/pc_catch_s2.py)
                # returns false — `xor eax, eax; ret 0x10` over its first bytes
                wr(gl(0x1003f573), b'\x31\xc0\xc2\x10\x00'); print('NOCATCH: the catch predicate stubbed', flush=True)
        # a dummy click LEAD ticks ahead of each scripted message; the plan's legs as they come due
        while script and script[0]['tick'] - LEAD <= state['tick']:
            step = script.pop(0); pending.append(step); click_dummy()
            emit({'tick': state['tick'], 'ev': 'dummy', 'for': step})
        if plan is not None and state['tick'] > 2:
            for step in plan.step(state['tick']):
                pending.append(step); click_dummy()
                emit({'tick': state['tick'], 'ev': 'dummy', 'for': step})
        if pending and state['tick'] - state.get('dummy_at', 0) > 10:
            # no message took the dummy: another floor point
            state['dummy_i'] = state.get('dummy_i', 0) + 1; click_dummy()
            emit({'tick': state['tick'], 'ev': 'dummy', 'retry': state['dummy_i']})
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
            if name and name not in actors:
                actors[name] = a; emit({'tick': state['tick'], 'ev': 'actor', 'name': name, 'ptr': a})
        except Exception: pass
        return False
MINIGAME_TICKS = int(os.environ.get('WDBG_MINIGAME_TICKS', '36'))
class Perfect(gdb.Breakpoint):
    """the PC minigame played perfectly: the minigame object's update (fcn.100508a1) scores the thumb's
    distance from the wobbling field's middle each tick — 4 within 200 of its 1000-unit radius, 3 / 2 / 1
    farther out, a penalty beyond (0x1005099d-0x10050a17, [this+0x18]); the score accumulates (fcn.10001b2c,
    [this+0x28]) into the progress [this+0x1c] the action reads. WDBG_MINIGAME=perfect writes the 4 at the
    join 0x10050a1a: the game is won as fast as the rules allow, its length a property of the data"""
    def __init__(self): super().__init__('*%#x' % gl(0x10050a1a), internal=True); self.n = 0
    def stop(self):
        try:
            esi = int(gdb.parse_and_eval('$esi')); self.n += 1
            wr(esi + 0x18, struct.pack('<I', 4))
            state['last'] = time.time()          # (a minigame keeps the watchdog quiet)
            if self.n == 1 or self.n % 24 == 0:
                emit({'tick': state['tick'], 'ev': 'minigame', 'obj': '%#x' % esi, 'perfect': self.n, 'progress': u32(esi + 0x1c), 'acc': u32(esi + 0x28)})
        except Exception as e:
            emit({'tick': state['tick'], 'ev': 'error', 'name': 'perfect', 'err': repr(e)})
        return False
class Minigame(gdb.Breakpoint):
    """a PC minigame won: the game action's update asks the minigame object's progress (fcn.100507f0:
    [this+0x1c], 100 = done, 0x10004c63) every tick — the oracle writes 100 MINIGAME_TICKS calls in"""
    def __init__(self): super().__init__('*%#x' % gl(0x100507f0), internal=True); self.calls = {}
    def stop(self):
        try:
            ecx = int(gdb.parse_and_eval('$ecx'))
            n = self.calls.get(ecx, 0) + 1; self.calls[ecx] = n
            state['last'] = time.time()          # (a minigame keeps the watchdog quiet)
            if n >= MINIGAME_TICKS:
                # (the GUI pushes its own progress into the object every tick: written before each read)
                wr(ecx + 0x1c, struct.pack('<I', 100))
                if n == MINIGAME_TICKS:
                    emit({'tick': state['tick'], 'ev': 'minigame', 'obj': '%#x' % ecx, 'won_after': n})
                    print('MINIGAME won at tick %d' % state['tick'], flush=True)
            elif n == 1:
                emit({'tick': state['tick'], 'ev': 'minigame', 'obj': '%#x' % ecx, 'progress': u32(ecx + 0x1c)})
        except Exception as e:
            emit({'tick': state['tick'], 'ev': 'error', 'name': 'minigame', 'err': repr(e)})
        return False
class Setter(gdb.Breakpoint):
    """the GUI's push of its minigame progress (fcn.100507dd: [this+0x1c] = arg): the first calls' return
    addresses and values, to find the GUI's own progress variable"""
    def __init__(self): super().__init__('*%#x' % gl(0x100507dd), internal=True); self.n = 0
    def stop(self):
        try:
            self.n += 1
            if self.n <= 8 or self.n % 50 == 0:
                esp = int(gdb.parse_and_eval('$esp'))
                emit({'tick': state['tick'], 'ev': 'setprogress', 'ret': '%#x' % ungl(u32(esp)), 'value': u32(esp + 4), 'n': self.n,
                      'ebp': '%#x' % int(gdb.parse_and_eval('$ebp')), 'esi': '%#x' % int(gdb.parse_and_eval('$esi')), 'edi': '%#x' % int(gdb.parse_and_eval('$edi'))})
        except Exception as e:
            emit({'tick': state['tick'], 'ev': 'error', 'name': 'setprogress', 'err': repr(e)})
        return False
class Hook(gdb.Breakpoint):
    def __init__(self, addr, name, nargs=4):
        super().__init__('*%#x' % gl(addr), internal=True); self.name, self.nargs = name, nargs
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp'))
            args = decode_args(esp, self.nargs)
            emit({'tick': state['tick'], 'ev': self.name, 'ret': '%#x' % ungl(u32(esp)), 'args': args})
            if self.name == 'goto':
                state.setdefault('dest', {})[args[1]] = (state['tick'], args[2])      # the actor's walk target
            if self.name == 'action' and isinstance(args[1], str) and args[2] in ('enter', 'leave', 'sleep'):
                state.setdefault('inside', {})[args[1]] = (args[2] != 'leave', state['tick'])     # a hideout's flag 4
            if self.name == 'action' and isinstance(args[1], str):
                state['actions'].setdefault(args[1], []).append((state['tick'], args[2]))
                if args[1] == 'woody' and args[2] == 'decline': state['declines'].append(state['tick'])
                if args[1] == 'woody' and args[2] in ('fight', 'respawn'):
                    state['caught'].append((state['tick'], args[2])); print('CAUGHT tick %d: %s' % (state['tick'], args[2]), flush=True)
            elif self.name == 'credit':
                state['credits'].append(state['tick'])
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
Hook(0x100522e6, 'credit', 3)       # a trick record paid (fcn.1000140b -> fcn.100522e6 on the record's tick)
if os.environ.get('WDBG_MINIGAME', 'perfect') == 'perfect': Perfect()
else: Minigame()
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

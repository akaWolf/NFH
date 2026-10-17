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
def msg_use(name, sneak=False):
    m = salloc(0x40); wr(m, struct.pack('<IIIII', VT_USE, make_string(name), make_string('oracle'), 1 if sneak else 0, 0x1000)); return m   # (+0xc sneaking, as NFH2's)
def msg_combine(obj, item, offset=(0, 0), flag18=0):
    # (item None: the GUI's click on a single-object combination — 101's TV, lir/twistedantenna <- lir/tv —
    # a NULL second object, as NFH2's game.exe sends for a `game` object without a tool)
    m = salloc(0x40); wr(m, struct.pack('<IIIIiiII', VT_COMBINE, make_string(obj), make_string(item) if item is not None else 0, make_string('oracle'), offset[0], offset[1], flag18, 0x1000)); return m
def msg_goto(room, x, sneak=False):
    m = salloc(0x40); wr(m, struct.pack('<IIIIIII', VT_GOTO, make_string(room), 0, int(x), 0, 1 if sneak else 0, 0x1000)); return m
def build(step):
    k, a = step['kind'], step['args']
    if k == 'use': return msg_use(a[0], step.get('sneak', False))
    if k == 'combine': return msg_combine(a[0], a[1], tuple(step.get('offset', (0, 0))), step.get('flag18', 1 if step.get('sneak') else 0))
    if k == 'goto': return msg_goto(a[0], a[1], step.get('sneak', False))
    raise ValueError(k)

script = json.load(open(os.environ['WDBG_SCRIPT'])) if os.environ.get('WDBG_SCRIPT') else []
script.sort(key=lambda s: s['tick'])
pending = []
state = {'tick': 0, 't0': None, 'last': time.time(), 'n': 0, 'actions': {}, 'credits': [], 'declines': [], 'caught': [], 'sneak': 'auto', 'patched': False}
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
    CATCHERS = ('neighbor', 'mother', 'chili', 'dog')       # (Season 1's dogs bark Woody into his fear: 107's chili)
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
            if self.room_of(a) in rooms or a['anim'] in self.GAITS: return True   # (NFH1: no GoTo hook — a walk's target is unknown)
        return False
    def sneak_now(self, w=None, to=None):
        """the sneaking flag of an input: the plan's on / off, or under auto (the port's default, tests/
        run_tricks.py _auto_sneak_tick) Woody's current room being a pet's — the PC's flag is per input,
        for the whole walk, so the walk is re-issued at each room change (resneak)"""
        if state['sneak'] != 'auto': return bool(state['sneak'])
        w = w or self.woody(); room = self.room_of(w) if w else None
        # the pet wakes on the entry tick of a running Woody (111's dog at tick 233, the re-issue at 239 came
        # late): an input whose way crosses a pet's room sneaks from the start, the port sets its flag
        # before the door's warp; the walk is re-issued running once the pet's room is behind him
        rooms = set(self.m.geo.route(room, to)) | {room} if to else {room}
        return bool(rooms & self.m.alerter_rooms)
    def resneak(self, tick, w):
        """under auto: the pending input sent again with the flag of the room Woody has just entered"""
        step = getattr(self, 'cur_step', None)
        if state['sneak'] != 'auto' or step is None or w is None: return []
        room = self.room_of(w)
        if room == getattr(self, '_sneak_room', room): self._sneak_room = room; return []
        self._sneak_room = room
        want = self.sneak_now(w, step.get('to'))
        if want == step.get('sneak', False): return []
        again = dict(step); again['tick'] = tick; again['sneak'] = want; again['resneak'] = True
        self.cur_step = again; self.last_input = tick
        return [again]
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
                self.phase = 'parking'; self.target = args[0]; self._sneak_room = self.room_of(w) if w else None
                self.cur_step = {'tick': tick, 'kind': 'goto', 'args': [room, x], 'sneak': self.sneak_now(w, room), 'to': room, 'leg': ' '.join(leg)}
                return [self.cur_step]
            elif op == 'walk':
                # `walk x y`: the world point's zone on its PC room (pcgeo: the port's own geometry)
                room, px = self.m.walk_point(float(args[0]), float(args[1]))
                if room is None: return self.done('no room for the walk')
                if not ungated and self.gate_closed(room):
                    if tick - self.leg_start > self.TIMEOUT: return self.done('timeout at the gate')
                    return []
                self.phase = 'walking'; self.target = (room, px); self.last_input = tick; self._sneak_room = self.room_of(w) if w else None
                self.cur_step = {'tick': tick, 'kind': 'goto', 'args': [room, int(round(px))], 'sneak': self.sneak_now(w, room), 'to': room, 'leg': ' '.join(leg)}
                return [self.cur_step]
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
                state['sneak'] = 'auto' if args[0] in ('auto', 'pet') else args[0] == 'on'; return self.done('sneak %s' % args[0])
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
                # (the drop's y: the room's path line — a y of 0 was declined on the spot in 103; WDBG_FLOOR_Y overrides)
                fy = int(os.environ.get('WDBG_FLOOR_Y', getattr(self.m, 'floor_y', 0) or 0))
                # (a probe's `obj=<name>` names the message's first object instead of the room: house / the
                # result object — the room object `toi` with the drop's x and the path's y was declined on 105)
                fobj = next((o[4:] for o in args[2:] if o.startswith('obj=')), room)
                fy = int(next((o[2:] for o in args[2:] if o.startswith('y=')), fy))
                # NFH1's GUI (game.exe fcn.004077a0 @ 0x407ae6, a floor hit with an item in hand): the
                # CombineMsg carries the ITEM at +4 and the room's name at +8, the click's x/y at +0x10/+0x14
                step = {'tick': tick, 'kind': 'combine', 'args': [pcname, fobj], 'offset': (int(round(px)), fy)}
                obj = result or room
            elif op in ('usewith', 'prime', 'unlock') and len(args) > 1:
                pcname = self.m.item_name(args[0], args[1])
                obj, game = self.m.combine_target(args[0], pcname)
                if obj is None: return self.done('no PC object for %s' % args[0])
                step = {'tick': tick, 'kind': 'combine', 'args': [obj, pcname]}
            elif op == 'unlock':
                # a dexterity unlock without a tool: the use of the minigame combination's own object
                obj, game = self.m.combine_target(args[0], None)
                if obj is None: return self.done('no PC object for %s' % args[0])
                step = {'tick': tick, 'kind': 'use', 'args': [obj]}
            else:
                obj = self.m.use_target(args[0])
                if obj is None: return self.done('no PC object for %s' % args[0])
                if op == 'use' and self.m.single_combo(obj):
                    # a bare trick that is a single-object combination (101's TV): the GUI's NULL combine
                    step = {'tick': tick, 'kind': 'combine', 'args': [obj, None]}
                else:
                    step = {'tick': tick, 'kind': 'use', 'args': [obj]}
            step['to'] = (obj or '').split('/')[0] if '/' in (obj or '') else (room if op == 'usewith' and args[0].startswith('Ground@') else None)
            step['leg'] = ' '.join(leg); step['sneak'] = self.sneak_now(w, step['to']); self.target = obj; self.phase = 'acting'; self.last_input = tick
            self.cur_step = step; self._sneak_room = self.room_of(w) if w else None
            self.acted = len(self.acts_on(obj)); self.declined = len(state['declines'])
            return [step]
        if self.phase in ('acting', 'parking', 'walking') and w is not None and w['anim'] in self.GAITS:
            again = self.resneak(tick, w)
            if again: return again
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
                    pr['x1'] - 120 <= w['x'] <= pr['x2'] + 120 and abs(w['y'] - pr['floor']) <= 150 \
                    and (w.get('room') in (None, pr['room'])):
                return self.done('ok')
            if tick - self.leg_start > self.TIMEOUT: return self.done('timeout')
            return []
        if self.phase == 'whenusing':
            acts = self.acts_on(self.target, self.leg_start)
            if acts and acts[-1][1] != 'leave': return self.done('ok')
            if tick - self.leg_start > 2 * self.TIMEOUT: return self.done('timeout')   # (102's beer never used again after the laxative)
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
            out[name] = {'x': struct.unpack('<i', rd(a + 0x28, 4))[0], 'y': struct.unpack('<i', rd(a + 0x2c, 4))[0], 'anim': as_string(u32(a + 0x3c)),
                         'room': as_string(u32(u32(a + 0x1c) + 4))}          # the room object at +0x1c, its name at +4
        except Exception: pass
    return out
LEAD = int(os.environ.get('WDBG_LEAD', '4'))
DUMMIES = [DUMMY] + [d.split() for d in os.environ.get('WDBG_DUMMIES', '400 400;300 450;500 450;400 500;200 400;600 400').split(';')]
def click_dummy():
    # (a dummy click that hits no floor sends no message: the Tick hook re-clicks the next point of
    # DUMMIES while a step stays pending)
    state['dummy_at'] = state['tick']; pt = DUMMIES[state.get('dummy_i', 0) % len(DUMMIES)]
    subprocess.Popen([T + '/xdotool-result/bin/xdotool', 'mousemove', pt[0], pt[1], 'sleep', '0.3',
                      'mousedown', '1', 'sleep', '0.2', 'mouseup', '1'],
                     env=dict(os.environ, DISPLAY=os.environ.get('WDBG_DISPLAY', ':97')))
def _click_dummy_old():
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
        if state['tick'] == 1 and not state.get('nocatch_done'):
            # (on its own flag: the scratch may be allocated before the first tick, by the level-name patch —
            # the runs of 107-112 went without the stub while it hung on `scratch is None`)
            state['nocatch_done'] = True
            if os.environ.get('WDBG_NOCATCH'):
                # Woody uncatchable: the state function's rooms test (fcn.00436bb0 — Woody's and the
                # neighbour's room objects equal, the neighbour's pause byte +0x78 clear, neither carrying
                # flag 4, fcn.0043c2b0) sets its `seen` byte at 0x436d2c; five NOPs there, and the
                # WouldCatch breakpoint on them logs each tick the test passes
                wr(0x436d2c, b'\x90' * 5); WouldCatch(); print('NOCATCH: the rooms test stubbed', flush=True)
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
class WouldCatch(gdb.Breakpoint):
    """the rooms test passed (Woody in the neighbour's room, unhidden): a catch on an unpatched game"""
    def __init__(self): super().__init__('*0x436d2c', internal=True); self.last = -100
    def stop(self):
        if state['tick'] - self.last >= 12:
            emit({'tick': state['tick'], 'ev': 'wouldcatch', 'actors': actor_states()}); print('WOULDCATCH tick %d' % state['tick'], flush=True)
            state.setdefault('wouldcatch', []).append(state['tick'])
        self.last = state['tick']
        return False
class Loop(gdb.Breakpoint):
    """the message loop after the pop (0x43b165): the message at [esp+0x18]; a player's message with a
    step pending is replaced by the built one"""
    def __init__(self): super().__init__('*0x43b165', internal=True); self.slot = None; self.hits = 0
    def stop(self):
        try:
            esp = reg('esp'); self.hits += 1
            if self.hits <= 3 and state['t0'] is not None: print('loop hit %d tick %d [esp+0x14] %#x [esp+0x18] %#x' % (self.hits, state['tick'], u32(esp + 0x14), u32(esp + 0x18)), flush=True)
            # the pop's out-parameter: [esp+0x14] before the push of its address, [esp+0x18] if the callee
            # left the push — whichever holds a message of the player's classes
            for off in ((self.slot,) if self.slot is not None else (0x18, 0x14)):
                msg = u32(esp + off)
                vt = u32(msg) if 0x10000 < msg < 0x7fffffff else 0
                if vt in (VT_GOTO, VT_USE, VT_COMBINE):
                    if self.slot is None: self.slot = off; print('message slot [esp+%#x]' % off, flush=True)
                    break
            else:
                return False
            if vt in (VT_GOTO, VT_USE, VT_COMBINE):
                if scratch['sproto'] is None: scratch['sproto'] = u32(msg + 4)
                if pending:
                    step = pending.pop(0); new = build(step)
                    wr(esp + off, struct.pack('<I', new))
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
            if name and name not in actors:
                actors[name] = a
                # the room: a pointer among the actor's words whose +4 is a short String (anc, lir, kit...)
                found = {}
                for i in range(2, 40):
                    w = u32(a + 4 * i)
                    if 0x10000 < w < 0x7fffffff:
                        try:
                            s4 = as_string(u32(w + 4))
                            if s4 and 1 < len(s4) <= 4 and '/' not in s4: found['+%#x' % (4 * i)] = s4
                        except Exception: pass
                print('ACTOR %s at %#x: room-like pointees %s' % (name, a, found), flush=True)
                emit({'tick': state['tick'], 'ev': 'actor', 'name': name, 'ptr': a, 'rooms': found})
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
            if self.name == 'action' and isinstance(args[1], str) and args[2] in ('enter', 'leave', 'sleep'):
                state.setdefault('inside', {})[args[1]] = (args[2] != 'leave', state['tick'])     # a hideout's flag 4
            if self.name == 'action' and isinstance(args[1], str):
                state['actions'].setdefault(args[1], []).append((state['tick'], args[2]))
                if args[1] == 'woody' and args[2] == 'decline': state['declines'].append(state['tick'])
                if args[1] == 'woody' and (args[2] in ('fight', 'respawn') or args[2].startswith('fear')):
                    # (a Season 1 catch: Woody's fear, then the level's FAILED screen — the ticks stop)
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
    print('plan: %d/%d legs, %s; caught %s; would be caught at %s' % (plan.i, len(plan.legs), [r['why'] for r in plan.results], state['caught'], state.get('wouldcatch', [])), flush=True)
gdb.execute('kill')

"""The PC level classes as scripts (plan B): the walker over levels/pc/scripts/LevelNNN.json — the cases
tools/pcref/pc_scripts.py extracted from game.exe's level classes (each a `run` switch on the resume index;
a case is a decision tree over its variant / inventory / lookup / class-byte tests, its leaf the case the
yield resumes). The walker is the part of the step runner that is pure data: it hands out the next steps of
the current case up to the next test or the case's end, takes the test's answer, and moves to the next case.
The runner that plays the steps on the port's pawns (GoTo = the walk to the PC hotspot, Action = the clip at
the Loader's ticks, Switch = the item variant swap, Icon = the bubble, OBJ2 = the fire) comes next; until
then `python3 -m runtime.pcscript <level> <trace.jsonl>` drives the walker with an oracle trace of the
original and reports where the trace's case chain and the walker's part ways.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'levels', 'pc', 'scripts')


def _addr(a):
    return int(a, 16) if isinstance(a, str) else int(a)


class Script(object):
    """one level's classes: cases by index, steps by address, the port items of the PC objects"""

    def __init__(self, level):
        self.level = level
        self.data = json.load(open(os.path.join(SCRIPTS, 'Level%d.json' % level)))
        objs = json.load(open(os.path.join(SCRIPTS, 'objects.json'))).get(str(level), {}).get('items', {})
        self.item_of = {}                       # PC object (and its family's base) -> the port item
        for item, d in objs.items():
            for key in (d.get('object'), d.get('base')):
                if key: self.item_of.setdefault(key, item)
        self.classes = []
        for cls in self.data['classes']:
            cases = {}
            for c in cls['cases']:
                for ix in c['index']:
                    cases[ix] = c
            self.classes.append({'address': cls['class'], 'cases': cases, 'steps': {_addr(a): t for a, t in cls['steps'].items()}})

    def case(self, cls, index):
        return self.classes[cls]['cases'].get(index)

    @staticmethod
    def family(name):
        return name.split('/')[-1].split('_')[0] if isinstance(name, str) else None

    def item(self, obj):
        """the port item that stands for a PC object (its variants share the family's base)"""
        if obj in self.item_of:
            return self.item_of[obj]
        if isinstance(obj, str) and '/' in obj:
            base = obj.split('/')[0] + '/' + self.family(obj)
            return self.item_of.get(base)
        return None


class Walker(object):
    """the position in a class's script: the case, the node of its tree, the step within the node"""

    def __init__(self, script, cls=0, start=0):
        self.script = script
        self.cls = cls
        self.index = start
        self.node = None
        self.pos = 0
        self.enter(start)

    def enter(self, index):
        c = self.script.case(self.cls, index)
        self.index = index
        self.node = c['tree'] if c else None
        self.pos = 0

    def pending(self):
        """the steps left in the current node (no test crossed)"""
        return self.node['steps'][self.pos:] if self.node else []

    def take(self):
        """pop the next step of the node, or None at the node's end"""
        if self.node is None or self.pos >= len(self.node['steps']):
            return None
        s = self.node['steps'][self.pos]
        self.pos += 1
        return s

    def test(self):
        """the test the node ends on (None at a leaf)"""
        return self.node.get('test') if self.node else None

    def leaf_next(self):
        return self.node.get('next') if self.node and 'test' not in self.node else None

    def answer(self, value):
        """take the test's branch (True / False)"""
        sub = self.node.get('true' if value else 'false')
        if sub is None:
            sub = self.node.get('false' if value else 'true')      # (one branch extracted only)
        self.node = sub
        self.pos = 0

    def advance(self):
        """at a leaf: move to the next case (a numeric next; else stay — the class returned or looped)"""
        nxt = self.leaf_next()
        if isinstance(nxt, int):
            self.enter(nxt)
            return True
        return False


def check(level, trace):
    """drive the walker with the trace: at each test take the branch whose steps the trace confirms next"""
    sc = Script(level)
    events = []
    for l in open(trace):
        r = json.loads(l); ev = r.get('ev')
        if ev not in ('icon', 'action', 'switch'): continue
        if ev == 'action' and r['args'][1] == 'woody': continue
        events.append((r['tick'] / 12.0, ev, int(r['ret'], 16) - 5))
    known = set()
    for cls in sc.classes: known |= set(cls['steps'])
    events = [e for e in events if e[2] in known]
    # which class holds the first event
    cls_ix = next((i for i, cls in enumerate(sc.classes) if events and events[0][2] in cls['steps']), 0)
    w = Walker(sc, cls_ix, 0)
    i = 0; matched = 0; divergences = []
    guard = 0
    while i < len(events) and guard < 20000:
        guard += 1
        t, ev, call = events[i]
        s = w.take()
        if s is not None:
            if _addr(s['a']) == call:
                matched += 1; i += 1
            elif s['kind'] in ('ICON', 'ACTION', 'SWITCH', 'GOTOENTER', 'ENTER', 'LEAVE'):
                # a step the trace should have shown as an event but did not: a GOTOENTER's own event is the
                # enter action (a sub-call), a Switch's event may come from the job — skip silently
                pass
            continue
        tst = w.test()
        if tst is not None:
            # look ahead: which branch's first observable step matches the next event
            def first_obs(node):
                for st in node.get('steps', []):
                    if st['kind'] in ('ICON', 'ACTION', 'SWITCH'): return _addr(st['a'])
                for v in ('true', 'false'):
                    if v in node:
                        r = first_obs(node[v])
                        if r is not None: return r
                return None
            tnode, fnode = w.node.get('true'), w.node.get('false')
            tfirst = first_obs(tnode) if tnode else None
            ffirst = first_obs(fnode) if fnode else None
            if tfirst == call and ffirst != call: w.answer(True)
            elif ffirst == call and tfirst != call: w.answer(False)
            elif tfirst is None and ffirst is not None: w.answer(False)
            elif ffirst is None and tfirst is not None: w.answer(True)
            else:
                # neither branch names the next event first: the leaf's next case decides — try true
                w.answer(True)
            continue
        if not w.advance():
            divergences.append((t, 'the class stopped at case %s before event %s %#x' % (w.index, ev, call)))
            break
        # the event should be found in the new case; if the case's first observable step is elsewhere, note it
        if events and w.node is not None:
            exp = next((_addr(st['a']) for st in w.pending() if st['kind'] in ('ICON', 'ACTION', 'SWITCH')), None)
            if exp is not None and exp != call and all(_addr(st['a']) != call for st in w.pending()):
                divergences.append((round(t, 2), 'case %s expects %#x, the trace has %s %#x' % (w.index, exp, ev, call)))
                # resync: jump to the case that holds the event
                cls = sc.classes[w.cls]
                for ix, c in cls['cases'].items():
                    def holds(node):
                        return any(_addr(st['a']) == call for st in node['steps']) or any(holds(node[v]) for v in ('true', 'false') if v in node)
                    if holds(c['tree']):
                        w.enter(ix); break
    print('level %d: %d of %d trace events matched in order; %d divergence(s)' % (level, matched, len(events), len(divergences)))
    for d in divergences[:12]: print('   ', d)
    return divergences


if __name__ == '__main__':
    check(int(sys.argv[1]), sys.argv[2])

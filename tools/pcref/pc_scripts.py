"""The Season 1 level classes of game.exe as scripts: every case of a class's `run` (a switch on the resume
index, tools/pcref/trick_branches.py's Fiber) explored down both answers of each variant test, so the port's
PC script engine can play the neighbour's routine as the original does instead of the overlays' per-item keys.

    python3 tools/pcref/pc_scripts.py [levels...] [--out levels/pc/scripts] [--print]

Per level a JSON: {"level", "class" (the switch's address), "cases": [{"index", "start", "tree"}], "steps":
{addr: step}}; a tree node is {"steps": [step...], "test": {"a", "fn", "variant"}, "true": node, "false":
node} or a leaf {"steps": [...], "next": case index | "ret" | "loop" | "out" | "toolong"}. A step is the
simulator's token (kind ACTION/GOTO/GOTOENTER/ENTER/LEAVE/SWITCH/ICON/OBJ2/FIRE5/FIRE4/REPAIR/LOOKUP/IFVARIANT/
IFTRICKED/OBJ1/OBJ3/SUBSEQ/INV/MSG/STOPMSG/TESTVAL/LOOKUPVAL with its address `a`); the tests are the calls of
fcn.0047a130 IsVariant(tricked, object), fcn.00413780 IsTricked(object) and fcn.00479ff0 OBJ3(object, n),
answered along a path by the objects the path has switched in (trick_branches.Fiber.simulate's `present` /
`gone` book-keeping) — the enumeration forks only where the simulator's own answer could differ at run time.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trick_branches as TB
import fire_sites as FS

ROOT = TB.ROOT


def level_fibers(n, levels):
    """the level's class(es) and the names its fire sites trick (as dump_cases finds them)"""
    names = set(); fs = {}
    for i, a, kind, top, notes, regs in FS.sites():
        if TB.level_of(TB.prologue(i), levels) != n:
            continue
        f = TB.fiber_of(a)
        if f is None:
            continue
        fs[f.a_sw] = f
        if top and isinstance(top[0], str):
            names.add(top[0])
    return list(fs.values()), names


def explore(f, start, names, limit=64):
    """the decision tree of one case: every path through its variant tests"""
    paths = []           # [(decisions, tokens, next)]
    todo = [()]          # decision prefixes to run
    seen = set()
    while todo and len(paths) < limit:
        prefix = todo.pop(0)
        if prefix in seen:
            continue
        seen.add(prefix)
        made = []        # (a, fn, variant, value) along this run

        def decide(a, fn, variant, default, _prefix=prefix, _made=made):
            i = len(_made)
            val = _prefix[i] if i < len(_prefix) else default
            _made.append((a, fn, variant, val))
            return val
        tokens, nxt = f.simulate(start, {}, set(names), present=set(), gone=set(), decide=decide)
        tokens = [resolve(dict(t)) for t in tokens]
        paths.append((tuple(m[3] for m in made), made, tokens, nxt))
        # the alternatives: flip each decision past the prefix (the first run's defaults), one at a time
        for i in range(len(prefix), len(made)):
            alt = tuple(m[3] for m in made[:i]) + (('false' if made[i][3] == 'true' else 'true'),)
            if alt not in seen:
                todo.append(alt)
    return paths


def slotvalue(i, slot, limit=1200):
    """the string a stack slot carries at line i: the last `mov dword [esp + N], reg` above it (the class's
    cases keep a GoTo's object in a slot, loaded from a global at the case's start) and that register's global"""
    for j in range(i - 1, max(0, i - limit), -1):
        a, ins = TB.parse(TB.L[j])
        if ins is None:
            continue
        m = TB.re.match(r'^mov dword \[%s\], (e[a-z]{2})$' % TB.re.escape(slot), ins)
        if m:
            return TB.regvalue(j, m.group(1))
        m = TB.re.match(r'^mov dword \[%s\], dword \[(0x5[0-9a-f]{5})\]$' % TB.re.escape(slot), ins)
        if m:
            return TB.G.get(m.group(1))
        if ins.startswith('push 0xffffffffffffffff'):
            return None
    return None


ACTIONS = {}     # the level's object -> its action names (objects.xml), set per level by script_of


def _actions_of(lv):
    out = {}
    for text in lv.texts:
        for m in TB.re.finditer(r'<(?:object|actor)\s+name="([^"]+)"[^>]*>(.*?)</(?:object|actor)>', text, TB.re.S):
            for am in TB.re.finditer(r'<action\s+[^>]*?name="([^"]+)"', m.group(2)):
                out.setdefault(m.group(1), set()).add(am.group(1))
    return out


def resolve(tok):
    """a token's operands that came out as a stack slot or a register: a GoTo's object is the `/` global
    loaded before the call (the decoder's last argument is the actor context — 113's valve GoTo), a DoAction's
    action the global that names one of the object's actions (the decoder swapped `surprise` and `neighbor`
    at 0x4521ce), else the slot's last write"""
    i = TB.LINE.get(tok['a'])
    if i is None:
        return tok
    # the globals loaded since the previous call (the call's own argument set-up: a GoTo's object sits 17
    # listing lines above its call in 113's valve case, past strings_near's 14)
    lo = i - 1
    for j in range(i - 1, max(0, i - 80), -1):
        a, ins = TB.parse(TB.L[j])
        if ins and TB.re.match(r'call ', ins):
            lo = j; break
    else:
        lo = max(0, i - 80)
    near = TB.strings_near(i, i - lo)
    if tok['kind'] in ('GOTO', 'GOTOENTER', 'ENTER', 'LEAVE', 'GOTO2') and not (isinstance(tok.get('obj'), str) and '/' in tok['obj']):
        objs = [x for x in near if '/' in x]
        if objs: tok['obj'] = objs[-1]
    if tok['kind'] == 'ACTION':
        obj, act = tok.get('obj'), tok.get('act')
        known = ACTIONS.get(obj, set())
        if not (isinstance(act, str) and act in known):
            cands = [x for x in near if x in known]
            if cands: tok['act'] = cands[-1]
            elif act == obj or not TB._resolved(act):
                cands = [x for x in near if '/' not in x and x != obj]
                if cands: tok['act'] = cands[-1]
    def fix(v, want_obj):
        if isinstance(v, str) and v.startswith('dword ['):
            r = slotvalue(i, v[7:-1])
            if r: return r
        if isinstance(v, str) and v in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi', 'ebp'):
            r = TB.regvalue(i, v)
            if r: return r
        return v
    if tok['kind'] in ('GOTO', 'GOTOENTER', 'ENTER', 'LEAVE', 'GOTO2'):
        tok['obj'] = fix(tok.get('obj'), True)
    elif tok['kind'] == 'ACTION':
        tok['obj'] = fix(tok.get('obj'), True); tok['act'] = fix(tok.get('act'), False)
        raw = tok.get('raw') or []
        if tok['act'] == tok['obj'] and len(raw) > 2:
            # the actor's name came out twice: the action name sits in the raw slot
            alt = fix(raw[2], False)
            if alt and alt != tok['obj']: tok['act'] = alt
    elif tok['kind'] == 'ICON':
        tok['args'] = [fix(v, False) for v in tok.get('args', [])]
    elif 'args' in tok:
        tok['args'] = [fix(v, True) for v in tok['args']]
    return tok


def _strip(tok):
    t = dict(tok)
    t.pop('fire', None); t.pop('raw', None)
    return t


def tree_of(paths):
    """a trie over the decisions: the shared token prefix up to each test, then the two subtrees"""
    def build(ps, depth):
        # ps: paths sharing their first `depth` decisions; split the tokens at the depth-th TESTVAL token
        head = ps[0]
        toks = head[2]
        # the tokens before the (depth+1)-th test
        count = 0; cut = None
        for i, t in enumerate(toks):
            if t['kind'] == 'TESTVAL':
                if count == depth:
                    cut = i; break
                count += 1
        if cut is None or all(len(p[1]) <= depth for p in ps):
            # a leaf: no further test on this path (the paths agree past here)
            return {'steps': [_strip(t) for t in toks[cut if cut is not None else len(toks):]] if False else [_strip(t) for t in toks], 'next': head[3]} if depth == 0 else \
                   {'steps': [_strip(t) for t in toks[_prev_cut(toks, depth):]], 'next': head[3]}
        test = toks[cut]
        node = {'steps': [_strip(t) for t in toks[_prev_cut(toks, depth):cut]],
                'test': {'a': test['a'], 'fn': test.get('fn'), 'variant': test.get('variant')}}
        for val in ('true', 'false'):
            sub = [p for p in ps if len(p[1]) > depth and p[1][depth][3] == val]
            if sub:
                node[val] = build(sub, depth + 1)
        return node

    def _prev_cut(toks, depth):
        # the index just past the depth-th TESTVAL token (0 for depth 0)
        if depth == 0:
            return 0
        count = 0
        for i, t in enumerate(toks):
            if t['kind'] == 'TESTVAL':
                count += 1
                if count == depth:
                    return i + 1
        return len(toks)
    return build(paths, 0)


def script_of(n, levels):
    global ACTIONS
    ACTIONS = _actions_of(levels[n])
    fibers, names = level_fibers(n, levels)
    out = {'level': n, 'folder': TB.LEVEL_DIR[n], 'tricked': sorted(names), 'classes': []}
    for f in fibers:
        cls = {'class': '%#x' % f.a_sw, 'cases': [], 'steps': {}}
        for st in sorted(set(f.starts), key=lambda x: f.starts.index(x)):
            paths = explore(f, st, names)
            tree = tree_of(paths)
            cls['cases'].append({'index': f.case_of[st], 'start': '%#x' % st, 'paths': len(paths), 'tree': tree})
            for _d, _m, toks, _n in paths:
                for t in toks:
                    cls['steps'].setdefault('%#x' % t['a'], _strip(t))
        out['classes'].append(cls)
    return out


def show(script):
    for cls in script['classes']:
        print('level %d class %s: %d cases, %d steps' % (script['level'], cls['class'], len(cls['cases']), len(cls['steps'])))
        for c in cls['cases']:
            def walk(node, ind):
                for s in node['steps']:
                    d = ('%s.%s' % (s.get('obj'), s.get('act'))) if s['kind'] == 'ACTION' else str(s.get('obj') or s.get('value') or s.get('args') or '')
                    print('%s%s %s %s' % (ind, s['a'] if isinstance(s['a'], str) else '%x' % s['a'], s['kind'], d[:60]))
                if 'test' in node:
                    print('%sTEST %s %s %s' % (ind, '%x' % node['test']['a'], node['test']['fn'], node['test']['variant']))
                    for v in ('true', 'false'):
                        if v in node:
                            print('%s %s:' % (ind, v)); walk(node[v], ind + '    ')
                else:
                    print('%s-> %s' % (ind, node.get('next')))
            print(' case %s @%s (%d paths)' % (c['index'], c['start'], c['paths']))
            walk(c['tree'], '   ')


def main(argv):
    want = [int(x) for x in argv if x.isdigit()] or sorted(TB.LEVEL_DIR)
    out_dir = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(ROOT, 'levels', 'pc', 'scripts')
    levels = {n: TB.Level(n) for n in TB.LEVEL_DIR}
    os.makedirs(out_dir, exist_ok=True)
    for n in want:
        sc = script_of(n, levels)
        if '--print' in argv:
            show(sc)
        p = os.path.join(out_dir, 'Level%d.json' % n)
        json.dump(sc, open(p, 'w'), indent=1, default=str)
        print('%s: %d class(es), %s cases, %s steps' % (p, len(sc['classes']), [len(c['cases']) for c in sc['classes']], [len(c['steps']) for c in sc['classes']]))


if __name__ == '__main__':
    main(sys.argv[1:])

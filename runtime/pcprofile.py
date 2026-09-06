"""The PC-experience profile (docs/PC_FIDELITY.md): the default since
2026-09-09; NFH_PROFILE=mobile (or --profile=mobile) selects the
mobile-parity runtime, which stays untouched. This module is the one
switch the profile hangs off — a data overlay applied after the
mobile level loads (levels/pc/<Level>.overlay.json) and the rule switches
the world reads through is_pc(). Every overlay entry carries a "source"
(the PC guide / video the deviation comes from), the profile's counterpart
of the runtime's `cs:` citations."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_pc():
    """read live, not at import: the harness sets the env after its imports"""
    return os.environ.get('NFH_PROFILE', 'pc') != 'mobile'


def overlay_path(level_path):
    name = os.path.basename(level_path).replace('.json', '.overlay.json')
    return os.path.join(ROOT, 'levels', 'pc', name)


def apply_overlay(level):
    """patch level.objs in place. An entry matches components by type
    (`component`), the GameObject's name (`object`) and optionally the item's
    zone (`zone`); `set` updates fields, `append` extends list fields, `anim`
    + `anim_set` retunes one animation of an ItemAnimationController by
    Name. Returns the number of components touched."""
    p = overlay_path(level.path)
    if not os.path.exists(p):
        return 0
    ov = json.load(open(p, encoding='utf-8'))
    n = 0
    for op in ov.get('patches', []):
        hit = 0
        for pid, o in level.objs.items():
            if o.get('type') != op.get('component'):
                continue
            d = o.get('data') or {}
            if 'owner' in op:
                # an ActionManager is addressed by its Owner pawn
                if (d.get('Owner') or {}).get('name') != op['owner']:
                    continue
            else:
                goname = (d.get('m_GameObject') or {}).get('name')
                if goname is None:
                    go = level._go_of(o)
                    goname = ((level._o(go) or {}).get('data') or {}).get('name')
                if goname != op.get('object'):
                    continue
            if op.get('zone') and (d.get('Zone') or {}).get('name') != op['zone']:
                continue
            if 'set' in op:
                d.update(op['set']); n += 1; hit += 1
            if 'append' in op:
                for k, v in op['append'].items():
                    d.setdefault(k, []).extend(v)
                n += 1; hit += 1
            if 'anim' in op:
                for a in d.get('Animations') or []:
                    if a.get('Name') == op['anim']:
                        a.update(op.get('anim_set') or {}); n += 1; hit += 1
            if 'actions_by_index' in op:
                # rebuild an ActionManager's list from the mobile list's
                # indices (duplicates allowed): the PC order of a lap where
                # the same item has several distinct actions (Level104's
                # two ApplePie entries — the fridge and the eat)
                acts = d.get('Actions') or []
                new = [acts[i] for i in op['actions_by_index'] if 0 <= i < len(acts)]
                if new:
                    d['Actions'] = new; n += 1; hit += 1
            if 'actions' in op:
                # rebuild an ActionManager's list from item names, the
                # entries reused (duplicates allowed): the PC order of a lap
                acts = d.get('Actions') or []
                by_name = {}
                for a in acts:
                    nm = (a.get('Item') or {}).get('name')
                    by_name.setdefault(nm, a)
                new = []
                for nm in op['actions']:
                    if nm in by_name:
                        new.append(by_name[nm])
                if new:
                    d['Actions'] = new; n += 1; hit += 1
        if hit == 0:
            import sys
            # a patch that touched nothing is a wrong object/component name
            # (the Season 2 neighbour's GameObject is "Rottweiler2", not
            # "Rottweiler"): say so, per patch, instead of applying silently
            print('pcprofile: overlay %s: patch %s matched nothing' % (
                os.path.basename(p), json.dumps({k: op[k] for k in ('object', 'component', 'owner', 'zone') if k in op})), file=sys.stderr)
    if n == 0:
        import sys
        print('pcprofile: overlay %s matched nothing' % os.path.basename(p), file=sys.stderr)
    return n

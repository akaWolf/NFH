#!/usr/bin/env python3
"""The Season 2 door passes of the PC original into the levels/pc overlays.

    python3 tools/pcref/pc_walks_s2.py            # print the room map and the passes
    python3 tools/pcref/pc_walks_s2.py --write    # PCPass on the Transitions, PCApproach on the stations

GameLogic.dll walks an actor through a door pair in one step (vtable
0x100ab1b8, fcn.1000340b / 0x10003a19): a movement to the near door's
`<actor>_in` hotspot, then — when the near door has an `enter` action for the
actor — its `enter`, the placement at the far door's `<actor>_out` and the far
door's `leave` (fcn.10003647, fcn.10003236), else a movement straight from
`<actor>_in` to `<actor>_out` (fcn.100037f8 -> fcn.100090bd, its floor line the
start's y). A movement steps one axis a tick (fcn.10009215) at the actor's
gait records — the neighbour's mg 8 px along, 3 up or down, Woody's 17 / 6 —
through the waypoints of fcn.10009177: off the floor line and off the target's
x it first goes up or down to the floor, then along it, then straight to the
target. The walk up to `<actor>_in` leaves the room's floor there, and the
next walk in the far room comes down to its floor from `<actor>_out`, so a
pass is, in px of the PC scene:

  in   the near door's `<actor>_in` against the near room's floor line,
  dx, dy   the straight movement from `<actor>_in` to the far `<actor>_out`,
  enter, leave   instead of dx, dy: the enter and leave actions' ticks (their
           clips) — the back doors of 211-214's fifth rooms, the mobile's Doors,
  out  the far room's floor line against `<actor>_out`,

each axis run its own ceil(px / record) ticks (pcprofile.s2_pass_ticks). The
mobile level has the same rooms as Zone01-Zone05; the map room -> zone is the
geometric one (the rooms' floor centres against the zones', each set scaled to
its own span) and is checked against the door graph: every <neighbor> record
of the PC must be a mobile Transition between the mapped zones and back.
The mobile door that stands for a record is the Transition in the near zone
whose LinkTo lies in the far zone.
"""
import itertools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
import lap_model_s2 as S  # noqa: E402

# the PC actor -> the mobile pawn role
ROLES = (('neighbor', 'Rottweiler'), ('woody', 'Woody'), ('mother', 'Mother'), ('olga', 'Olga'))


# The actors' stations: the mobile routine item -> the PC object its visit walks to, per
# role — the object of the level script's GoTo / DoAction for the station
# (lap_model_s2.walk's targets: 202's theocean, 205's beachright/mat, 206's fifi, 207's
# kid, 213's limberwall, 214's door_closed …), else the object whose actor action the
# station plays; stations without a PC counterpart are left out (205's rocket has no
# hotspot, 208's and 209's Mother at Fifi and at her start, 210's call, 211's and
# 214's Olga at her stands, the kid). The approach is the object's `<actor>` hotspot
# against its room's floor line: the walk goes up or down to it from the floor and the
# next walk comes back down (fcn.10009177).
STATIONS = {
    201: {'CaptainHat': {'Rottweiler': 'topleft/captncap'},
          'Buffet': {'Rottweiler': 'topleft/buffet', 'Olga': 'topleft/buffet'},
          'WaterPuddle': {'Rottweiler': 'topright/waterpuddle'},
          'DeckRail': {'Rottweiler': 'topright/reling'}},
    202: {'BeerMat': {'Rottweiler': 'beachright/mat_hn_guarded'},
          'Rake': {'Rottweiler': 'pond/rake_ground'},
          'Swimming': {'Rottweiler': 'beachright/theocean'},
          'BridgeRail': {'Rottweiler': 'pond/bridge'},
          'OlgaMat': {'Olga': 'beachleft/mat_olga_guarded'},
          'Submarine': {'Olga': 'beachleft/sub'}},
    203: {'Microphone': {'Rottweiler': 'wallright/stage'},
          'ToiletPaper': {'Rottweiler': 'groundleft/toilet'},
          'ToiletFlush': {'Rottweiler': 'groundleft/toilet'},
          'Watermelon': {'Rottweiler': 'wallleft/melons'},
          'Bicycle': {'Rottweiler': 'groundleft/bike'}},
    204: {'PullKart': {'Rottweiler': 'groundleft/rickshaw', 'Olga': 'groundleft/rickshaw'},
          'Karate': {'Rottweiler': 'groundleft/headbanging'},
          'GongDrumstick': {'Rottweiler': 'wallleft/gong'},
          'HotDog': {'Rottweiler': 'wallright/hotdogshop'},
          'JadeNecklace': {'Rottweiler': 'groundright/jadedummy'}},
    205: {'OlgaMatBeach': {'Rottweiler': 'beachright/mat', 'Olga': 'beachright/mat_guarded'},
          'TabbleTennis': {'Rottweiler': 'beachright/pingpong_guarded', 'Olga': 'beachright/pingpong_guarded'},
          'WaterSkiis': {'Rottweiler': 'beachleft/waterski_guarded'},
          'Chef': {'Rottweiler': 'shop/chef'},
          'SandSculpture': {'Rottweiler': 'beachleft/sandlion'}},
    206: {'DogFifi': {'Rottweiler': 'topleft/fifi'},
          'DeckChair': {'Rottweiler': 'topleft/deckchair', 'Mother': 'topleft/deckchair'},
          'DeckChairThrow': {'Mother': 'topleft/deckchair'},
          'DeckChairCall': {'Mother': 'topleft/deckchair'},
          'DeckChairOrder': {'Mother': 'topleft/deckchair'},
          'Pillows': {'Rottweiler': 'topright/pillows'},
          'LaunchPad': {'Rottweiler': 'bottomleft/ramp'},
          'Harpoon': {'Rottweiler': 'bottomleft/harpoon'},
          'FifiWeightsDrop': {'Rottweiler': 'bottomright/dumbbell'},
          'Weights': {'Rottweiler': 'bottomright/dumbbell'},
          'FifiWeightsGrab': {'Rottweiler': 'bottomright/dumbbell'},
          'DynamiteBox': {'Rottweiler': 'topright/dynamitebag'}},
    207: {'PoolBoard': {'Rottweiler': 'pool/divingboard'},
          'Bartender': {'Rottweiler': 'bar/keeper'},
          'Elephant': {'Rottweiler': 'bar/elefant'},
          'Shell': {'Rottweiler': 'beachright/mat_guarded', 'Olga': 'beachright/mat_guarded'},
          'ShellLaydown': {'Olga': 'beachright/mat_guarded'},
          'SandCastle': {'Rottweiler': 'kid'},
          'BeachTowel': {'Rottweiler': 'beachleft/mat'},
          'DeckChair': {'Mother': 'pool/deckchair'},
          'PoolLadder': {'Mother': 'pool/pool'}},
    208: {'IndianPlatform': {'Rottweiler': 'amusement/platform'},
          'ShoeMachine': {'Rottweiler': 'tadj_mahal/shoe_cleaner'},
          'AngryElephant': {'Rottweiler': 'elephant/elephant'},
          'ArmsBowl': {'Rottweiler': 'altar/statue'},
          'DressingRoom': {'Mother': 'bazar/dressing_room'}},
    209: {'FireFakir': {'Rottweiler': 'fire_fakir/groove'},
          'HotShoe': {'Rottweiler': 'tadj_mahal/shoe_mat'},
          'TadjMahal': {'Rottweiler': 'tadj_mahal/curtain'},
          'Coal': {'Rottweiler': 'coal_area/coal'},
          'IceCream': {'Rottweiler': 'bazar/icecream_machine'},
          'Cow': {'Rottweiler': 'holy_cow/cow'},
          'DressingRoom': {'Mother': 'bazar/dressing_room'}},
    210: {'DeckChair': {'Rottweiler': 'beachleft/deckchair'},
          'DogBasket': {'Rottweiler': 'pool/fifi_sleep'},
          'DogBasketPut': {'Rottweiler': 'pool/fifi_sleep'},
          'TurbanShop': {'Rottweiler': 'beachright/turbanshop'},
          'Elephant': {'Rottweiler': 'bar/elefant'},
          'OlgaMatBeach': {'Olga': 'beachleft/mat_olga_guarded'},
          'OlgaShower': {'Olga': 'beachleft/shower_guarded'},
          'DeckChairMother': {'Mother': 'pool/deckchair'},
          'CallRTMother': {'Mother': 'pool/deckchair'}},
    211: {'Sweets': {'Rottweiler': 'topleft/dish'},
          'FishingRod': {'Rottweiler': 'topleft/rod'},
          'LifeBoat': {'Rottweiler': 'bottomleft/boat'},
          'LifeJacket': {'Rottweiler': 'bottomleft/lifevest'},
          'DivingGear': {'Rottweiler': 'bottomright/diving'},
          'ToiletWomen': {'Olga': 'topleft/wcright'},
          'OlgaSeaView': {'Olga': 'topleft/reling'},
          'DeckChairMother': {'Mother': 'topright/deckchair'}},
    212: {'PreAztecThrone': {'Rottweiler': 'topright/hands'},
          'AztecThrone': {'Rottweiler': 'topright/hands'},
          'Whip': {'Rottweiler': 'midright/whip'},
          'CigarBox': {'Rottweiler': 'midleft/cigars'},
          'SleepBench': {'Rottweiler': 'midleft/bank'},
          'MechanicalBull': {'Rottweiler': 'bottomleft/bullride'},
          'PreParrotLedge': {'Rottweiler': 'bottomright/cliff'},
          'MumWaitZone4': {'Mother': 'midleft/red_bull'},
          'MumWaitZone3': {'Mother': 'midright/statue_hideout'}},
    213: {'LiveBull': {'Rottweiler': 'midleft/limberwall'},
          'PlantCarnivore': {'Rottweiler': 'topright/carnivore'},
          'Tortilla': {'Rottweiler': 'bottomright/tortilla'},
          'BoatPicnic': {'Rottweiler': 'bottomright/picnic', 'Olga': 'bottomright/picnic'},
          'OlgaBackTowel': {'Olga': 'bottomright/picnic'},
          'Pinata': {'Rottweiler': 'bottomleft/pinata'},
          'MechanicalBullControls': {'Rottweiler': 'bottomleft/bullride_controls'},
          'MechanicalBullControlsWait': {'Rottweiler': 'bottomleft/bullride_controls'},
          'CementBath': {'Rottweiler': 'midleft/washingtub'},
          'MotherWaitZone5': {'Mother': 'topright/flowers'},
          'MotherWaitZone2': {'Mother': 'bottomright/water'},
          'MechanicalBullWait': {'Olga': 'bottomleft/bullride_olga'},
          'MechanicalBull': {'Olga': 'bottomleft/bullride_olga'}},
    214: {'Shower': {'Rottweiler': 'bottomleft/shipshower', 'Olga': 'bottomleft/shipshower_guarded'},
          'Bouquet': {'Rottweiler': 'topleft/bouquet'},
          'CaptainDoor': {'Rottweiler': 'topright/door_closed'},
          'Pistol': {'Rottweiler': 'bottomleft/pistol'},
          'Hatch': {'Rottweiler': 'bottomright/hatch_closed'},
          'DeckChairMother': {'Mother': 'topright/deckchair'},
          'MotherWait': {'Mother': 'bottomright/reling'}},
}
ACTOR = {role: actor for actor, role in ROLES}


def approaches(n):
    """[(item, zone, component, {role: {'obj', 'x', 'px', 'routes'}})]: per
    station the PC object's `<actor>` hotspot x, its height against the
    room's floor and the PC's routes to the role's other stations in other
    rooms — the mobile zones of the path finder's rooms (Geometry.route: the
    Dijkstra of fcn.1000a421 from this hotspot to the other's), where the
    mobile's Helpers.GetShortestPath (1 a hop, its ties to Mono's qsort)
    takes 39 of the 338 legs through the other room of a ring"""
    g = S.Geometry(n)
    doors, zones = mobile_doors(n)
    zmap = room_map(n, g, doors, zones)
    raw = json.load(open('%s/levels/s2/Level%d.json' % (ROOT, n)))
    out = []
    for pid, o in sorted(raw['objects'].items(), key=lambda kv: int(kv[0])):
        d = o.get('data') or {}
        name = (d.get('m_GameObject') or {}).get('name')
        if name not in STATIONS.get(n, {}) or 'Zone' not in d or o['type'] in ('Transition', 'Door'):
            continue
        per = {}
        for role, obj in STATIONS[n][name].items():
            actor = ACTOR[role]
            p = g.point(obj, actor, exact=True)
            r = g.room_of(obj)
            if p is None or r not in g.rooms:
                raise KeyError('%d: %s has no %s hotspot in a room' % (n, obj, actor))
            routes = {}
            for other, per2 in STATIONS[n].items():
                ob = per2.get(role)
                if ob is None or other == name or g.room_of(ob) == r:
                    continue
                pb = g.point(ob, actor, exact=True)
                rt = g.route(r, p, g.room_of(ob), pb, actor)
                if rt is not None:
                    routes[other] = [zmap[r]] + [zmap[g.room_of(dout)] for _din, dout in rt]
            per[role] = {'obj': obj, 'x': p[0], 'px': p[1] - g.floor(r), 'routes': routes}
        out.append((name, (d.get('Zone') or {}).get('name'), o['type'], per))
    return out


def mobile_doors(n):
    """[(pid, name, zone name, far zone name, component)] of the level's
    Transitions and Doors (the back doors of 211-214's fifth rooms), and the
    zones {name: (centre x, floor y)}"""
    raw = json.load(open('%s/levels/s2/Level%d.json' % (ROOT, n)))
    objs = raw['objects']
    zone_of = {}
    doors = []
    for pid, o in objs.items():
        d = o.get('data') or {}
        if o['type'] in ('Transition', 'Door'):
            zone_of[int(pid)] = (d.get('Zone') or {}).get('name')
    for pid, o in objs.items():
        d = o.get('data') or {}
        if o['type'] in ('Transition', 'Door'):
            link = (d.get('LinkTo') or {}).get('path')
            doors.append((int(pid), (d.get('m_GameObject') or {}).get('name'),
                          zone_of[int(pid)], zone_of.get(link), o['type']))
    import scene                                    # the zones' extents, as the port builds them
    lv = scene.Level('%s/levels/s2/Level%d.json' % (ROOT, n))
    zones = {z.name: ((z.left + z.right) / 2.0, z.ty) for z in lv.zones}
    return doors, zones


def room_map(n, g, doors, zones):
    """{PC room: mobile zone} — the geometric assignment that the door graph
    confirms; the PC rooms without a mobile zone (201's bridge, off the
    level's left edge) are left out"""
    rooms = {r: ((v['x1'] + v['x2']) / 2.0, -float(v['y'])) for r, v in g.rooms.items()}

    def norm(pts):
        xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
        sx = (max(xs) - min(xs)) or 1.0; sy = (max(ys) - min(ys)) or 1.0
        return {k: ((p[0] - min(xs)) / sx, (p[1] - min(ys)) / sy) for k, p in pts.items()}
    zn = norm(zones)
    links = {(z, fz) for _p, _n, z, fz, _c in doors}
    best = None
    names = sorted(zones)
    for sub in itertools.combinations(sorted(rooms), len(names)):
        rn = norm({r: rooms[r] for r in sub})
        for perm in itertools.permutations(names):
            m = dict(zip(sub, perm))
            ok = all((m[r], m[nb['name']]) in links
                     for r in sub for nb in g.rooms[r]['nb'] if nb['name'] in m)
            ok = ok and all(any(m.get(r) == z and nb['name'] in m and m[nb['name']] == fz
                                for r in sub for nb in g.rooms[r]['nb']) for z, fz in links)
            if not ok:
                continue
            cost = sum((rn[r][0] - zn[m[r]][0]) ** 2 + (rn[r][1] - zn[m[r]][1]) ** 2 for r in sub)
            if best is None or cost < best[0]:
                best = (cost, m)
    if best is None:
        raise ValueError('%d: no room map fits the door graph' % n)
    return best[1]


def passes(n):
    """[(mobile door name, zone, far zone, component, near PC door, far PC
    door, {role: pass})] — a pass {'in', 'dx', 'dy', 'out'} or {'in',
    'enter', 'leave', 'out'}"""
    g = S.Geometry(n); d = S.Data(n)
    doors, zones = mobile_doors(n)
    m = room_map(n, g, doors, zones)
    zr = {z: r for r, z in m.items()}
    out = []
    for _pid, name, z, fz, comp in sorted(doors, key=lambda t: (t[2], t[1])):
        ra, rb = zr[z], zr[fz]
        rec = next(r for r in g.rooms[ra]['nb'] if r['name'] == rb)     # fcn.1004ca13
        din, dout = rec['doorin'], rec['doorout']
        per = {}
        for actor, role in ROLES:
            a = g.point(din, actor + '_in', exact=True)
            b = g.point(dout, actor + '_out', exact=True)
            if a is None or b is None:
                continue
            p = {'in': a[1] - g.floor(ra), 'out': g.floor(rb) - b[1]}
            if actor in g.door_acts.get(din, ()):
                t1 = d.action_ticks(din, 'enter', actor)
                t2 = d.action_ticks(dout, 'leave', actor)
                if t1 is None or t2 is None:
                    continue
                p['enter'] = t1; p['leave'] = t2
            else:
                p['dx'] = b[0] - a[0]; p['dy'] = b[1] - a[1]
            per[role] = p
        out.append((name, z, fz, comp, din, dout, per))
    return m, out


def main(argv):
    write = '--write' in argv
    sys.path.insert(0, os.path.join(ROOT, 'runtime'))
    import pcprofile
    for n in [int(a) for a in argv[1:] if a.isdigit()] or range(201, 215):
        m, rows = passes(n)
        print('== %d  %s' % (n, ', '.join('%s=%s' % (r, z) for r, z in sorted(m.items(), key=lambda kv: kv[1]))))
        for name, z, fz, comp, din, dout, per in rows:
            print('  %-24s %s->%s  %-26s %-26s %s' % (
                name, z, fz, din, dout, '  '.join('%s %d' % (role[:4], pcprofile.s2_pass_ticks(role, 'walk', p))
                                                  for role, p in per.items())))
        if not write:
            continue
        p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
        ov = json.load(open(p))
        patches = [e for e in ov.get('patches', []) if not (e.get('component') in ('Transition', 'Door')
                                                            and 'PCPass' in (e.get('set') or {}))]
        for name, z, fz, comp, din, dout, per in rows:
            patches.append({'object': name, 'component': comp, 'zone': z,
                            'set': {'PCPass': per}})
        patches = [e for e in patches if not ('PCApproach' in (e.get('set') or {}))]
        for name, z, comp, per in approaches(n):
            patches.append({'object': name, 'component': comp, 'zone': z,
                            'set': {'PCApproach': per}})
        ov['patches'] = patches
        note = (" The door passes (tools/pcref/pc_walks_s2.py): PCPass on each Transition = per pawn the PC"
                " pass of the door pair it stands for — the near door's <actor>_in against the room's floor,"
                " the straight movement to the far door's <actor>_out (or the enter + leave ticks), the far"
                " floor against <actor>_out, in px of the PC scene; PCApproach on the actors' stations = per"
                " role the PC object's <actor> hotspot x and its height against the room's floor.")
        src = ov.get('source', '')
        i = src.find(' The door passes (tools/pcref/pc_walks_s2.py)')
        if i >= 0:
            j = src.find(' The ', i + 1)
            src = src[:i] + (src[j:] if j >= 0 else '')
        ov['source'] = src + note
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
        open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

"""The s2_plans area (docs/audit/verified/s2_plans.md): the six PORT findings
of the Season-2 plan pass — the L208 InventoryToAdd rat refill, the Season-2
start (FinishedEntrance serialized TRUE: no walk-in, the Entrance greeting's
lock), the L210 Mother210 bar re-arm (MotherWakeSleepBehavior.ProgressBar
Delay), the L211 FishingRod / TransitionDownwards raycast order (a data
fact, kept as a regression of the near-face ordering), the L214 forced
sleep's CurrentAnimationSequence stamp + the action-stop carry-over + the
captain cabin's DoorBack pair, and the L209 serialized starting inventory.

Each check drives the real viewer loop in-process (record.Recorder), as
tests/checks/items.py does; the flows that need laps set the catchers to
IgnoreWoody and tick.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

from record import Recorder, DT     # noqa: E402


def _rec(level, outdir, name):
    os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
    return Recorder(os.path.join(ROOT, level), os.path.join(outdir, name),
                    script=None, seconds=1e9, fps=0)


def _advance(rec, t, seconds, stop=None, each=None):
    """tick `seconds` of game time from t; stop() ends the run early,
    each() samples every frame"""
    end = t + seconds
    while t < end:
        rec.tick(t)
        t += DT
        if each is not None:
            each(t)
        if stop is not None and stop():
            break
    return t


def _item(rec, name):
    return next(i for i in rec.v.level.items.values() if i.name == name)


def _ignore_catchers(w):
    for role in ('Rottweiler', 'Mother'):
        p = w.pawns.get(role)
        if p is not None:
            p.ignore_woody = True


def run(record, check, outdir):
    ok = True

    # -- F1: Item.AddInventoryToObject (Item.cs:1791-1810) — the L208 snake
    #    and elephant rounds refill the emptied Mouse (InventoryToAdd = the
    #    Mouse itself) with a fresh IT2_Rat (cs:1559, 1582) ---------------
    rec = _rec('levels/s2/Level208.json', outdir, 'rat_refill')
    w = rec.v.world
    mouse = _item(rec, 'Mouse')
    snake = _item(rec, 'Snake')
    el = _item(rec, 'AngryElephant')
    ok &= check('s2_plans: Mouse.InventoryToAdd resolves to the Mouse',
                mouse.inventory_to_add == mouse.pid, mouse.inventory_to_add)
    w._woody_search_done(mouse)                       # the take empties it
    emptied = not mouse.inventory_items
    w.inventory.used = w.inventory.items[0]           # hold the rat
    w._can_woody_use(snake)                           # the snake round
    ok &= check('s2_plans: snake round refills the Mouse with a rat',
                emptied and mouse.inventory_items
                and mouse.inventory_items[0]['type'] == 'IT2_Rat'
                and w.inventory.used['type'] == 'IT2_Snake' and snake.primed,
                (emptied, mouse.inventory_items, w.inventory.used))
    w._woody_search_done(mouse)                       # the second take
    rat = next(e for e in w.inventory.items if e['type'] == 'IT2_Rat')
    w.inventory.used = rat
    w._can_woody_use(el)                              # the elephant round
    ok &= check('s2_plans: elephant round refills the Mouse again',
                el.primed and mouse.inventory_items
                and mouse.inventory_items[0]['type'] == 'IT2_Rat'
                and not any(e['type'] == 'IT2_Rat' for e in w.inventory.items),
                (el.primed, mouse.inventory_items,
                 [e['type'] for e in w.inventory.items]))

    # -- F6: InventoryManager.InventoryItems (InventoryManager.cs:5) — L209
    #    ships the pen knife, every other scene an empty list --------------
    rec = _rec('levels/s2/Level209.json', outdir, 'knife')
    w = rec.v.world
    ok &= check('s2_plans: L209 starts with the serialized pen knife',
                [e['type'] for e in w.inventory.items] == ['IT2_Knife']
                and rec.v.level.first_inventory_item,
                w.inventory.items)
    # the knife chain's head: the Flowers pick (Item.cs:1421-1426) works
    # off it — the held knife becomes the flowers and a fresh knife lands
    fl = next(i for i in rec.v.level.items.values()
              if i.name == 'Flowers' and i.kind == 'SearchItem')
    w.inventory.used = w.inventory.items[0]
    w._can_woody_use(fl)
    ok &= check('s2_plans: the knife picks the flowers, a knife lands back',
                sorted(e['type'] for e in w.inventory.items)
                == ['IT2_Flowers', 'IT2_Knife'],
                [e['type'] for e in w.inventory.items])
    ok &= check('s2_plans: L208 starts empty-handed',
                _rec('levels/s2/Level208.json', outdir, 'nokinfe')
                .v.world.inventory.items == [])

    # -- F2: the Season-2 start — Woody serializes FinishedEntrance TRUE
    #    (Pawn.cs:119): no entrance walk (Woody.cs:223-231), StartGame's
    #    Entrance greeting holds the input for its 1.1 s (IntroAnimation.cs:
    #    300-304, Woody.cs:372-375); L210's neighbour walks to the deck chair
    #    in the entrance zone and must not catch him ------------------------
    rec = _rec('levels/s2/Level210.json', outdir, 'start210')
    w = rec.v.world
    wd = w.woody
    sx, sy = wd.sprite.x, wd.sprite.y
    z0 = wd.zone.name if wd.zone else None
    seen = {'entrance': False, 'unlock_t': None}

    def sample(t):
        if wd.anim.anim.name == 'Entrance':
            seen['entrance'] = True
        if seen['unlock_t'] is None and not wd.input_locked:
            seen['unlock_t'] = t
    t = _advance(rec, 0.0, 6.0, each=sample)
    ok &= check('s2_plans: S2 start plays Entrance, no walk-in, no catch',
                wd.finished_entrance and seen['entrance']
                and abs(wd.sprite.x - sx) < 1e-6 and abs(wd.sprite.y - sy) < 1e-6
                and (wd.zone.name if wd.zone else None) == z0 == 'Zone02'
                and not w.game.got_caught,
                (wd.finished_entrance, seen, wd.sprite.x, wd.sprite.y,
                 wd.zone.name if wd.zone else None, w.game.got_caught))
    ok &= check('s2_plans: the Entrance end unlocks the input (~1 s)',
                seen['unlock_t'] is not None and 0.9 <= seen['unlock_t'] <= 1.3,
                seen['unlock_t'])
    # Season 1 keeps its walk-in (Level101 serializes FALSE)
    rec = _rec('levels/s1/Level101.json', outdir, 'start101')
    wd = rec.v.world.woody
    ok &= check('s2_plans: S1 Woody still starts unfinished and locked',
                not wd.finished_entrance and wd.input_locked
                and rec.v.world._entrance_timer is not None)

    # -- F3: MotherWakeSleepBehavior.ProgressBarDelay (cs:33/40, 46-52) —
    #    the L210 Mother210 bar re-arms 2 s after MotherLookLoop, so her
    #    IsSleeping window opens every lap (not once) ---------------------
    rec = _rec('levels/s2/Level210.json', outdir, 'mother210')
    w = rec.v.world
    _ignore_catchers(w)
    mother = w.pawns['Mother']
    windows = []
    state = {'on': False}

    def sample210(t):
        if mother.is_sleeping and not state['on']:
            state['on'] = True
            windows.append([t, None])
        elif not mother.is_sleeping and state['on']:
            state['on'] = False
            windows[-1][1] = t
    t = _advance(rec, 0.0, 100.0, each=sample210)
    ok &= check('s2_plans: L210 Mother sleeps (IsSleeping) on the 2nd lap',
                len(windows) >= 2 and windows[1][0] > 50.0,
                windows)

    # -- F5: MotherSleepBehaviour.ForceSleep / ForceSleepAfterTrick stamp
    #    CurrentAnimationSequence (Item.cs:936-940, 977-981) — L214's
    #    DeckChairMother bar reads the MotherSecondUse window; the forced
    #    sequence's end still stops her action (AnimationControllerBase.cs:
    #    242-246), so her routine walks on to MotherWait ----------------------
    rec = _rec('levels/s2/Level214.json', outdir, 'force214')
    w = rec.v.world
    _ignore_catchers(w)
    mother = w.pawns['Mother']
    dcm = _item(rec, 'DeckChairMother')
    rm = next(r for r in w.routines if r.role == 'Mother')
    slept = {'t': None}
    moved = {'t': None}

    def sample214(t):
        if slept['t'] is None and mother.is_sleeping:
            slept['t'] = t
        if moved['t'] is None and rm.item is not None \
                and rm.item.name == 'MotherWait':
            moved['t'] = t
    t = _advance(rec, 0.0, 130.0, each=sample214,
                 stop=lambda: moved['t'] is not None)
    ok &= check('s2_plans: L214 pistol play puts the Mother to sleep (bar)',
                slept['t'] is not None and 50.0 < slept['t'] < 75.0
                and dcm.current_sequence in ('MotherSecondUse', 'MotherUse'),
                (slept['t'], dcm.current_sequence))
    ok &= check('s2_plans: the forced sleep ends her DeckChairMother action',
                moved['t'] is not None and moved['t'] > (slept['t'] or 0),
                (moved['t'], rm.item.name if rm.item else None))
    # the stamps themselves, direct
    beh = next(b for b in w.behavior_objs
               if type(b).__name__ == 'MotherSleepBehaviour')
    dcm.current_sequence = None
    beh._force_sleep_after_trick()
    ok &= check('s2_plans: ForceSleepAfterTrick stamps MotherExtraUse',
                dcm.current_sequence == 'MotherExtraUse', dcm.current_sequence)

    # -- F5b: the captain cabin — the DoorBack pair keeps its zone edge and
    #    opens with Item.CaptainDoorBehavior (Item.cs:2606-2623) ----------
    rec = _rec('levels/s2/Level214.json', outdir, 'cabin')
    w = rec.v.world
    lv = rec.v.level
    z03 = next(z.pid for z in lv.zones if z.name == 'Zone03')
    z05 = next(z.pid for z in lv.zones if z.name == 'Zone05')
    before = lv.find_path(z03, z05)
    cd = _item(rec, 'CaptainDoor')
    cd.tricked = True
    w._captain_door_behavior(cd)
    after = lv.find_path(z03, z05)
    doors = [d for d in lv.doors if d.name == 'DoorBack']
    ok &= check('s2_plans: cabin route refused until the CaptainDoor trick',
                before is None and after is not None and len(after) == 1
                and all(not d.disabled for d in doors),
                (before, after, [d.disabled for d in doors]))

    # -- F4 (data fact): in the scene file the L211 FishingRod box lies
    #    inside the Zone04 TransitionDownwards box, whose near face the click
    #    ray would meet first (Physics.Raycast nearest hit, Pawn.cs:403) — but
    #    Level.Start moves Zone04 to ZonesY[4], 1.07 lower (Level.cs:186), and
    #    the transition rides along with its zone: the rod stands clear of it
    #    and a click on the rod is the rod's
    rec = _rec('levels/s2/Level211.json', outdir, 'rod')
    rod = _item(rec, 'FishingRod')
    stairs = next(d for d in rec.v.level.doors
                  if d.name == 'TransitionDownwards'
                  and rec.v.level.zone_by_pid(d.zone).name == 'Zone04')
    it, door = rec.v._hit_at(rod.collider[0], rod.collider[1])
    ok &= check('s2_plans: FishingRod click resolves to the rod, above the moved stairs',
                it is not None and it.name == 'FishingRod' and door is None
                and stairs.collider[1] + stairs.collider[3] * 0.5 < rod.collider[1],
                (it.name if it else None, door.name if door else None,
                 round(stairs.collider[1] + stairs.collider[3] * 0.5, 3),
                 round(rod.collider[1], 3)))
    return ok

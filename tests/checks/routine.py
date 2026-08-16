"""routine — the ActionManager / urgent / alarm / angry checks of the final
audit (docs/audit/verified/routine.md). Each guards one fixed divergence and
fails on the pre-fix code.

The scenarios build a headless World straight from the level (no SDL, no
viewer — World + spawn_pawn + start_routines is what Viewer.load does) and
poke the exact state the original's method reads; a few tick the world so
the animation sequences drain as in play.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

from scene import Level                       # noqa: E402
from world import World                       # noqa: E402

DT = 1.0 / 60.0


def build(level):
    """a World the way Viewer.load builds it, minus the HUD/sounds; Woody
    hides so the neighbour's detection never interrupts a scenario"""
    lv = Level(os.path.join(ROOT, level))
    w = World(lv)
    for role in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
        w.spawn_pawn(role)
    w.woody = w.pawns.get('Woody')
    w.start_routines()
    if w.woody is not None:
        w.woody.hiding = True
    return w


def item(w, name):
    return next(i for i in w.level.items.values() if i.name == name)


def routine(w, role='Rottweiler'):
    return next(r for r in w.routines if r.role == role)


def alerter(w):
    return next((i for i in w.level.items.values() if i.kind == 'Alerter'),
                None)


def tick(w, seconds):
    for _ in range(int(seconds / DT)):
        w.tick(DT)


def run(record, check, outdir):
    ok = True

    # -- D1: Item.Fix clears Rottweiler.TrickedAux (Item.cs:2065) ----------
    w = build('levels/s2/Level206.json')
    rott = w.pawns['Rottweiler']
    pad, harpoon = item(w, 'LaunchPad'), item(w, 'Harpoon')
    for it in (pad, harpoon):
        it.tricked = True
        it.already_tricked = True
    w.play_angry(rott, pad)
    set_ = rott.tricked_aux
    w._fix(harpoon)
    ok &= check('routine: TrickedAux set by the scored pair', set_)
    ok &= check('routine: TrickedAux cleared by Item.Fix', not rott.tricked_aux)

    # -- D8/D9: the Season 2 meter keeps decaying, no compound whistle -----
    ok &= check('routine: S2 keeps CanDecreaseAngryMeter',
                rott.can_decrease_angry)
    w = build('levels/s2/Level213.json')
    rott = w.pawns['Rottweiler']
    plant = item(w, 'PlantCarnivore')
    plant.tricked = plant.compound = plant.compound_tricked = True
    before = w.game.compound_tricks
    w.play_angry(rott, plant)
    ok &= check('routine: S2 compound skips OnCompoundTrickDone',
                w.game.compound_tricks == before, w.game.compound_tricks)

    # -- D2: a tricked Drawing goes angry (Item as TrickItem, cs:419) -------
    w = build('levels/s1/Level107.json')
    rt = routine(w)
    drawing = item(w, 'Drawing')
    drawing.tricked = True
    calls = []
    w.play_angry = lambda pawn, it, on_done=None: calls.append(it.name)
    rt.index = 0
    rt.state = rt.USING
    rt._finish()
    ok &= check('routine: tricked Drawing goes angry', calls == ['Drawing'],
                calls)

    # -- D5: LoopFromSelectedIndex=false wraps to 0 (ActionManager.cs:575-582)
    w = build('levels/s2/Level206.json')
    mrt = routine(w, 'Mother')
    mrt.index = len(mrt.actions) - 1
    mrt._advance()
    ok &= check('routine: L206 Mother wraps to 0', mrt.index == 0, mrt.index)

    # -- D4: IsAlarmPostponed's six arms ---------------------------------
    w = build('levels/s1/Level105.json')
    rt = routine(w)
    i = next(k for k, a in enumerate(rt.actions)
             if a['postpone_alarm_during_use_only'] and not a['postpone_alarm'])
    rt.index = i
    rt.state = rt.USING
    ok &= check('routine: PostponeAlarmDuringUseOnly arm', rt.is_alarm_postponed())
    w = build('levels/s1/Level114.json')
    rt = routine(w)
    rt.index = 0                                # Polish, PostponeAlarm
    rt.state = rt.MOVING
    ok &= check('routine: the walk toward a PostponeAlarm use',
                rt.is_alarm_postponed())
    w = build('levels/s1/Level101.json')
    rt = routine(w)
    item(w, 'Sofa').tricked = True
    rt.index = 0
    rt.state = rt.USING
    ok &= check('routine: Item.IsTricked() arm', rt.is_alarm_postponed())
    w = build('levels/s1/Level110.json')
    rt = routine(w)
    rt.run_to_fixing_item(item(w, 'FireExtinguisher'), item(w, 'BBQ'))
    ok &= check('routine: L110 Grab.PostponeAlarm arm', rt.is_alarm_postponed())

    # -- D3: the parked alerter run fires at the use stop -----------------
    w = build('levels/s1/Level114.json')
    rt = routine(w)
    pet = alerter(w)
    rt.index = 0
    rt.state = rt.USING
    rt.pending_surprise = pet
    rt._finish()
    ok &= check('routine: use stop releases the parked run',
                pet is not None and rt.urgent_item is pet)

    # -- D7: a parked phone alarm releases as the AlarmAction (full use) ---
    w = build('levels/s1/Level105.json')
    rt = routine(w)
    phone = item(w, 'Phone')
    rt.pending_alarm = phone
    # every L105 use postpones during use (PostponeAlarmDuringUseOnly), so
    # the release comes on the walk toward an action without PostponeAlarm
    rt.index = next(k for k, a in enumerate(rt.actions)
                    if not a['postpone_alarm'])
    rt.state = rt.MOVING
    rt._check_pending_alarm()
    ok &= check('routine: parked phone alarm keeps alarm_use',
                rt.urgent_item is phone and rt._alarm_use)

    # -- D6: the templates' Urgent flags pick the run ---------------------
    w = build('levels/s1/Level103.json')
    rt = routine(w)
    rt.move_to_toilet(True)
    ok &= check('routine: the toilet rush runs', rt.pawn.in_urgent)
    w = build('levels/s1/Level111.json')
    rt = routine(w)
    rt.run_to_fixing_item(item(w, 'Vacuum'), item(w, 'DirtyCarpet'))
    ok &= check('routine: L111 fetch walks (Grab.Urgent=false)',
                not rt.pawn.in_urgent)
    w = build('levels/s2/Level206.json')
    mrt = routine(w, 'Mother')
    mrt.run_to_hit_pawn(w.pawns['Rottweiler'])
    ok &= check('routine: L206 Mother walks to the hit', not mrt.pawn.in_urgent)

    # -- the interrupted fetch resumes (StartUrgentAction's OriginalAction)
    w = build('levels/s1/Level111.json')
    rt = routine(w)
    pet = alerter(w)
    rt.run_to_fixing_item(item(w, 'Vacuum'), item(w, 'DirtyCarpet'))
    rt.start_urgent(pet)                       # an alerter run lands on it
    interrupted = rt.urgent_item is pet and bool(rt._urgent_stack)
    rt._urgent_finished()                      # the run ends
    ok &= check('routine: interrupted Grab replays after the run',
                interrupted and rt.urgent_item is item(w, 'Vacuum')
                and rt._urgent_action.get('kind') == 'grab')

    # -- D10: a Duration timeout is a bare Finished (no StopAction(bool)) --
    w = build('levels/s1/Level110.json')
    rt = routine(w)
    calls = []
    w.play_angry = lambda pawn, it, on_done=None: calls.append(it.name)
    beer = item(w, 'Beer')
    beer.tricked = True
    rt.delay_start = 0.0
    rt._pending = None                         # past StartFirstAction
    rt.index = 1
    rt.state = rt.USING
    rt.timer = 0.5
    rt.tick(0.6)
    ok &= check('routine: Duration timeout skips the angry',
                calls == [] and rt._pending == 'advance', (calls, rt._pending))

    # -- D11: the animated angry never rushes to the toilet ---------------
    w = build('levels/s1/Level102.json')
    rt = routine(w)
    rott = w.pawns['Rottweiler']
    beer, sofa = item(w, 'Beer'), item(w, 'Sofa')
    beer.tricked = beer.got_tricked = True
    rt.frozen = True                           # keep the routine out of it
    w.play_angry(rott, sofa)
    tick(w, 20)
    ok &= check('routine: animated angry does not rush',
                not rt._toilet_run and not sofa.tricked)

    # -- D15: a bark mid-climb is parked (PortalMove, Rottweiler.cs:272) --
    w = build('levels/s1/Level114.json')
    rt = routine(w)
    pet = alerter(w)
    rt.pawn.state = rt.pawn.DOOR_CLIMB
    rt.hear_alerter(pet, True)
    ok &= check('routine: bark mid-climb parks',
                rt.urgent_item is None and rt.pending_surprise is pet)

    # -- D16: Olga.OnItemAnimationSequenceEnded (TrickItem.cs:972, Olga.cs:
    #    154-158) + the OnGUI hidden gate (AnimationControllerBase.cs:177):
    #    on Level205 hidden Olga's own HitPawn stands still and her mat use
    #    ends with the mat's UseNormalSequence, which the parked neighbour's
    #    ItemToStopInfiniteAnimation releases — the second half of the mutex
    #    handshake; before the fix both routines parked for good after lap 1
    w = build('levels/s2/Level205.json')
    w._catch = lambda *a, **k: None          # Woody's presence is not the point
    rt, ort = routine(w), routine(w, 'Olga')
    tick(w, 3.0)                              # she is on the mat, hidden
    frozen = ort.state == ort.USING and ort.pawn.sprite.hidden \
        and ort.pawn.anim.anim.name == 'HitPawn'
    f0 = (ort.pawn.anim.frame, ort.pawn.anim.acc)
    tick(w, 2.0)
    frozen = frozen and (ort.pawn.anim.frame, ort.pawn.anim.acc) == f0
    ok &= check('routine: hidden Olga does not animate', frozen)
    laps = {'Rottweiler': 0, 'Olga': 0}
    prev = {}
    for _ in range(int(395 / DT)):
        w.tick(DT)
        for r in (rt, ort):
            if prev.get(r.role) not in (None, 0) and r.index == 0:
                laps[r.role] += 1
            prev[r.role] = r.index
    ok &= check('routine: L205 handshake cycles (>=3 laps/400s)',
                laps['Rottweiler'] >= 3 and laps['Olga'] >= 3, laps)

    # -- the Dog/Chili SameZone re-check on every Update (ActionManager.cs:
    #    442-448, RoutineActionMove.cs:105-128): an alerter run arriving from
    #    another zone starts the surprise where it lands, walks to the pet,
    #    yells 'Angry' and (Rottweiler.cs:485-510) runs to the raw-tricked
    #    DirtyCarpet — the vacuum fetch. Level111 from the neighbour's start
    #    zone (Zone06, a walk-up door into the dog's Zone02)
    w = build('levels/s1/Level111.json')
    w._catch = lambda *a, **k: None
    rt = routine(w)
    dog, carpet, vac = item(w, 'Dog'), item(w, 'DirtyCarpet'), item(w, 'Vacuum')
    carpet.tricked = True
    rt._pending = None
    rt.delay_start = 0.0
    rt.start_urgent(dog)
    latched = None
    yelled = fetched = False
    for _ in range(int(60 / DT)):
        w.tick(DT)
        if latched is None and rt._same_zone:
            latched = (rt.pawn.zone is not None and rt.pawn.zone.pid == dog.zone,
                       round(abs(rt.pawn.sprite.x - dog.move_x('Rottweiler')), 2))
        if rt.pawn.anim.anim.name == 'Angry':
            yelled = True
        if rt._fix_tool is vac:
            fetched = True
            break
    ok &= check('routine: SameZone latches on landing, away from the dog',
                latched is not None and latched[0] and latched[1] > 0.3, latched)
    ok &= check('routine: the yell starts the carpet run and the vacuum fetch',
                yelled and fetched, (yelled, fetched))
    # the null RottLastDoor: a Level113 neighbour who has not passed a door
    # is stalled by cs:121's exception until the next urgent retargets him
    w = build('levels/s1/Level113.json')
    w._catch = lambda *a, **k: None
    rt = routine(w)
    dog = item(w, 'Dog')
    rt._pending = None
    rt.delay_start = 0.0
    rt.start_urgent(dog)
    tick(w, 20)
    dead = rt._manager_dead and rt.urgent_item is dog and not rt._same_zone
    rt.start_urgent(item(w, 'Sink'))          # any other target revives it
    ok &= check('routine: L113 null RottLastDoor stalls the manager',
                dead and not rt._manager_dead)

    # -- UpdateWalking on every walk (Pawn.cs:981, Rottweiler.cs:833-849):
    #    the toilet rush passes the tricked toilet, the near surprise
    #    interrupts it (chained as OriginalAction, resumed after), and the
    #    use then angers at the dependency (GetTrickedItem, RoutineActionUse.
    #    cs:548) — Level102 pays the toilet and the ToiletPaper on one visit
    w = build('levels/s1/Level102.json')
    w._catch = lambda *a, **k: None
    rt = routine(w)
    toilet, paper = item(w, 'Toilet'), item(w, 'ToiletPaper')
    toilet.tricked = True
    paper.tricked = paper.got_tricked = True
    rt._pending = None
    rt.delay_start = 0.0
    before = w.game.completed
    rt.move_to_toilet(True)
    startled = False
    for _ in range(int(60 / DT)):
        w.tick(DT)
        if rt.pawn.anim.anim.name in ('FindRight', 'FindLeft'):
            startled = True
        if w.game.completed - before >= 2:
            break
    ok &= check('routine: L102 loo visit pays the toilet and the paper',
                startled and w.game.completed - before == 2,
                (startled, w.game.completed - before))

    # -- the toilet template's ContinueToNextAfterFinished (Level102) ------
    w = build('levels/s1/Level102.json')
    rt = routine(w)
    rt.move_to_toilet(True)
    rt._urgent_finished()
    ok &= check('routine: L102 toilet end advances', rt._pending == 'advance',
                rt._pending)
    return ok

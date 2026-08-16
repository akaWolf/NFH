"""The items area (docs/audit/verified/items.md): the Item family's flag
lifecycle and Woody's use side — WasPriming, the subclass CanWoodyUse
overrides, the SearchItem take path, IsUsing, the elephant zone watch,
ActivateItemAfterUsingObject, the idle tails, KidActions, the crab strips,
GetTrickScore / ExtraCoinLinkedTrick, the zone strips, the small twins.

Each check drives the real viewer loop in-process (record.Recorder, the
same 60 Hz tick tests/run_tricks.py rides) so the item state — which
state.jsonl does not carry — can be asserted directly; the flows that
need a walk jump the routine index instead of waiting for the lap.
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


def _advance(rec, t, seconds, stop=None):
    """tick `seconds` of game time from t; stop() ends the run early"""
    end = t + seconds
    while t < end:
        rec.tick(t)
        t += DT
        if stop is not None and stop():
            break
    return t


def _item(rec, name):
    return next(i for i in rec.v.level.items.values() if i.name == name)


def _player(rec, it):
    return rec.v.world.players.get(id(it.sprite)) if it.sprite else None


def _routine_index(rec, name):
    r = rec.v.world.routines[0]
    names = [(rec.v.level.items[a['item']].name
              if a.get('item') in rec.v.level.items else None)
             for a in r.actions]
    return names.index(name)


def run(record, check, outdir):
    ok = True

    # -- D1: WasPriming — the prime leg of a tricked toggles-prime item is
    #    not a tricked use (TrickItem.cs:260, RoutineActionUse.cs:546):
    #    no angry, the flag raised for the leg, and the use leg pays -----
    rec = _rec('levels/s1/Level111.json', outdir, 'wasprime')
    w = rec.v.world
    wm = _item(rec, 'WashingMachine')
    r = w.routines[0]
    w.pawns['Rottweiler'].ignore_woody = True
    wm.tricked = True
    r.index = _routine_index(rec, 'WashingMachine')      # the prime leg
    angry = []
    orig = w.play_angry

    def spy(pawn, item, on_done=None):
        angry.append((r.index, item.name))
        return orig(pawn, item, on_done=on_done)
    w.play_angry = spy
    seen_flag = []
    t = _advance(rec, 0.0, 90.0,
                 stop=lambda: (seen_flag.append(wm.was_priming) or False)
                 if r.index == 1 else r.index >= 3)
    ok &= check('items: prime leg raises WasPriming', any(seen_flag))
    ok &= check('items: no angry on the prime leg',
                not any(i == 1 for i, _ in angry), angry)
    ok &= check('items: the use leg still pays angry',
                any(i == 2 for i, _ in angry), angry)

    # -- D1: the primed pose survives the prime visit (TrickItem.cs:691):
    #    L111's Airer is primed at action 8 and used at 10, the FishTank
    #    between — the AirerCloth pose has to hold while he is away ------
    rec = _rec('levels/s1/Level111.json', outdir, 'primepose')
    w = rec.v.world
    airer = _item(rec, 'Airer')
    r = w.routines[0]
    w.pawns['Rottweiler'].ignore_woody = True
    r.index = 8
    t = _advance(rec, 0.0, 120.0, stop=lambda: r.index >= 9)
    p = _player(rec, airer)
    ok &= check('items: primed pose survives the prime visit',
                bool(airer.primed and p is not None
                     and p.anim.name == airer.primed_normal),
                (airer.primed, p.anim.name if p else None))

    # -- D2: the collider ships disabled on the SlipperyGround strips (and
    #    220 more) — never a click target; the GroundItem / InspectItem
    #    overrides refuse with the description and no trick -------------
    rec = _rec('levels/s1/Level113.json', outdir, 'ground')
    w = rec.v.world
    slip = _item(rec, 'SlipperyGround')
    ok &= check('items: disabled colliders are unclickable',
                slip.clickable is False)
    w.woody.anim.play_looping('Stand_Down')
    res = w._can_woody_use(slip)
    ok &= check('items: GroundItem click refuses with its description',
                res is False and not slip.tricked and not slip.used
                and w.hud is not None and w.hud.show_description
                and w.hud.desc_string == w.hud.loc(slip.description_string),
                (res, slip.tricked, w.hud.desc_string if w.hud else None))
    rec = _rec('levels/s1/Level110.json', outdir, 'inspect')
    w = rec.v.world
    plant = _item(rec, 'CarnivorPlant')
    changer = rec.v.level.items.get(plant.item_that_changes_tooltip)
    res = w._can_woody_use(plant)
    first = w.hud.desc_string
    changer.got_tricked = True
    res2 = w._can_woody_use(plant)
    ok &= check('items: InspectItem click refuses, primed text once tricked',
                res is False and res2 is False and not plant.tricked
                and first == w.hud.loc(plant.description_string)
                and w.hud.desc_string == w.hud.loc(plant.description_primed),
                (res, first, w.hud.desc_string))
    # F8: the zone strip keeps its own Looping type (PlayAnimationDirectly)
    bbq = _item(rec, 'BBQ')
    w.zone_reaction(bbq.zone, 'enter')
    p = _player(rec, bbq)
    ok &= check('items: BBQFullSmoke loops on zone enter',
                p is not None and p.anim.name == 'BBQFullSmoke'
                and p.mode == 'looping',
                (p.anim.name, p.mode) if p else None)

    # -- D4: the take path runs Item.UseItem / SearchItem.InternalUse ------
    rec = _rec('levels/s1/Level105.json', outdir, 'take_used')
    w = rec.v.world
    mob = _item(rec, 'Mobile')
    w._woody_search_done(mob)
    spent = w._can_woody_use(mob)
    ok &= check('items: search take sets Used (UseOnce gate)',
                mob.used and spent is False, (mob.used, spent))
    rec = _rec('levels/s1/Level102.json', outdir, 'take_hide')
    w = rec.v.world
    tp = _item(rec, 'ToiletPaper')
    w._woody_search_done(tp)
    q = rec.v.level.quads_by_go.get(tp.go) or {}
    ok &= check('items: HideAfterUse on the take',
                tp.used and q.get('renderer_enabled') is False,
                (tp.used, q.get('renderer_enabled')))
    rec = _rec('levels/s2/Level202.json', outdir, 'take_collider')
    w = rec.v.world
    sb = _item(rec, 'Sandbucket')
    w._woody_search_done(sb)
    ok &= check('items: DisableColliderAfterUse on the take',
                sb.clickable is False)
    # F3: the crab strips go through SearchItem.PlayItemAnimation
    crab = _item(rec, 'CrayFish')
    plays = []
    w.search_play = lambda it, name: plays.append((it.name, name))
    other = next(z.pid for z in rec.v.level.zones if z.pid != crab.zone)
    w.crab_animations(w.woody, crab.zone, other)
    ok &= check('items: crab zone strip rides search_play',
                ('CrayFish', crab.leave_zone) in plays, plays)
    # F13: the untricked Rake refuses its compound with the HideString bubble
    # and the compound drops DontGetAngry (TrickItem.cs:514-518, 531)
    rake = _item(rec, 'Rake')
    w.inventory.used = {'type': rake.compound_required, 'use_count': 0,
                        'name': '', 'desc': '', 'wrong_zone': '',
                        'long': False}
    w._can_woody_use(rake)
    bubble = w.hud.desc_string if w.hud.show_description else None
    rake.tricked = True
    w.inventory.used = {'type': rake.compound_required, 'use_count': 0,
                        'name': '', 'desc': '', 'wrong_zone': '',
                        'long': False}
    w.inventory.items.append(w.inventory.used)
    w._can_woody_use(rake)
    ok &= check('items: Rake compound bubble, then DontGetAngry drops',
                bubble == w.hud.loc(rake.hide_string_key) and rake.compound_tricked
                and not rake.dont_get_angry and rake.use_once,
                (bubble, rake.compound_tricked, rake.dont_get_angry))
    rec = _rec('levels/s2/Level207.json', outdir, 'keepfull')
    w = rec.v.world
    moped = _item(rec, 'Moped2')
    crab = _item(rec, 'CrayFish')
    w._woody_search_done(moped)
    w._woody_search_done(crab)
    ok &= check('items: KeepFull head — count 0 empties, count 2 decrements',
                bool(moped.inventory_items == [] and not moped.keep_full
                     and crab.take_item_count == 1 and crab.keep_full
                     and crab.inventory_items),
                (moped.inventory_items, crab.take_item_count))
    # D9: the ElephantBucket idle rewrite on ActivateItemTrick
    src = _item(rec, 'Elephant')
    bucket = _item(rec, 'ElephantBucket')
    w._woody_trick_done(src, None)
    ok &= check('items: ElephantBucket IdleNormal rewrite',
                bucket.tricked and bucket.idle == 'N2TrickItemIdleNormal',
                (bucket.tricked, bucket.idle))
    # F5: ExtraCoinLinkedTrick pays the pair a second time
    castle = _item(rec, 'SandCastle')
    towel = rec.v.level.items[castle.linked_item_trick]
    castle.tricked = towel.tricked = True
    before = w.game.completed
    w._on_trick_done(castle)
    ok &= check('items: ExtraCoinLinkedTrick counts three',
                w.game.completed - before == 3, w.game.completed - before)
    rec = _rec('levels/s2/Level206.json', outdir, 'rabbit')
    w = rec.v.world
    rb = _item(rec, 'Rabbit')
    w._woody_search_done(rb)
    ok &= check('items: Rabbit take deactivates it', rb.clickable is False)
    # D4.6: SearchingItem=False openers never close; a drawer closes,
    # 1 s after a take
    rec = _rec('levels/s1/Level107.json', outdir, 'pinboard')
    w = rec.v.world
    pb = _item(rec, 'PinsBoard')
    w.open_search_furniture(pb)
    t = _advance(rec, 0.0, 3.0)
    q = rec.v.level.quads_by_go.get(pb.open_object) or {}
    ok &= check('items: SearchingItem=False opener stays open',
                q.get('active') is True and pb not in w._open_furniture)
    rec = _rec('levels/s1/Level101.json', outdir, 'drawer')
    w = rec.v.world
    dr = _item(rec, 'Drawer')
    # past the entrance: Woody's controller is Hidden for the door pass
    # (Pawn.cs:1617-1641) and a hidden controller does not Refresh
    # (AnimationControllerBase.cs:177) — his search would stand still
    t = _advance(rec, 0.0, 3.5)
    w.open_search_furniture(dr)
    t0 = dr.close_time
    t = _advance(rec, t, 1.7)
    q = rec.v.level.quads_by_go.get(dr.open_object) or {}
    closed = q.get('active') is False
    w._woody_search_done(dr)
    w.open_search_furniture(dr)
    ok &= check('items: drawer closes, 1 s once taken',
                t0 == 1.5 and closed and dr.acquired_inventory_count == 1
                and dr.close_time == 1.0, (t0, closed, dr.close_time))
    # the empty re-click still runs OnFinishAnimationCompelted
    w._woody_search_step(dr)
    t = _advance(rec, t, 2.5)
    ok &= check('items: empty search still runs UseItem',
                dr.acquired_inventory_count == 0
                and w.woody.anim.anim.name != 'WhatsUp',
                (dr.acquired_inventory_count, w.woody.anim.anim.name))

    # -- D5: DoNothingWhileBeeingUsed reads Item.IsUsing ------------------
    rec = _rec('levels/s1/Level114.json', outdir, 'isusing')
    w = rec.v.world
    g = _item(rec, 'Gramaphone')
    g.is_using = True
    res = w._can_woody_use(g)
    ok &= check('items: IsUsing refuses the nail-less click with NoNo',
                res is False and w.woody.anim.anim.name == 'NoNo',
                (res, w.woody.anim.anim.name))
    # F4: the compound Shotgun pays CompoundTrickScore
    sg = _item(rec, 'Shotgun')
    sg.compound_tricked = sg.tricked = True
    w._on_trick_done(sg)
    ok &= check('items: compound trick pays CompoundTrickScore',
                w.game.log[-1:] == [sg.compound_trick_score_v], w.game.log)
    # the OnUseAnimationCompleted tail: a compound-tricked shotgun shows
    # CompoundDoubleTrickedAnim (TrickItem.cs:357-366)
    sg.tricked = False
    w._woody_trick_done(sg, None)
    p = _player(rec, sg)
    ok &= check('items: compound trick tail plays the double anim',
                p is not None and p.anim.name == sg.compound_double_anim,
                p.anim.name if p else None)

    # -- D6: Pawn.ElephantAnimations (L208) --------------------------------
    rec = _rec('levels/s2/Level208.json', outdir, 'elephant')
    w = rec.v.world
    el = _item(rec, 'AngryElephant')
    line = rec.v.level.items[el.object_to_prime]
    el.primed = True
    line.locked = False
    other = next(z.pid for z in rec.v.level.zones if z.pid != el.zone)
    w.elephant_animations(w.woody, other)
    p = _player(rec, el)
    ok &= check('items: elephant zone watch locks the line once',
                line.locked and el.elephant_behavior_aux
                and p is not None and p.anim.name == 'N2TrickItemPrimedNormal',
                (line.locked, el.elephant_behavior_aux,
                 p.anim.name if p else None))
    line.locked = False
    w.elephant_animations(w.woody, other)
    ok &= check('items: elephant zone watch is one-shot', not line.locked)

    # -- D7: ActivateItemAfterUsingObject (L214) --------------------------
    rec = _rec('levels/s2/Level214.json', outdir, 'grog')
    w = rec.v.world
    mug = _item(rec, 'CaptainMug')
    wheel = rec.v.level.items[mug.activate_item_after_using]
    cap = rec.v.level.items[mug.linked_item_trick]
    w._woody_trick_done(mug, None)
    t = _advance(rec, 0.0, 10.5)
    early = cap.clickable
    t = _advance(rec, t, 1.0)
    ok &= check('items: grog activates the wheel after 11 s',
                early and not cap.clickable and wheel.clickable,
                (early, cap.clickable, wheel.clickable))

    # -- D8: the idle arms ---------------------------------------------------
    rec = _rec('levels/s1/Level103.json', outdir, 'fuckedup')
    w = rec.v.world
    cake = _item(rec, 'BirthdayCake')
    cake.fucked_up = True
    w._return_to_idle(cake)
    p = _player(rec, cake)
    ok &= check('items: ReturnToIdle plays IdleFuckedUp',
                p is not None and p.anim.name == cake.idle_fucked_up,
                p.anim.name if p else None)
    rec = _rec('levels/s1/Level104.json', outdir, 'neutral')
    w = rec.v.world
    deo = _item(rec, 'Deodrant')
    w._woody_trick_done(deo, None)
    p = _player(rec, deo)
    ok &= check('items: a tricked Neutral item shows its tricked idle',
                p is not None and p.anim.name == deo.idle_tricked,
                p.anim.name if p else None)
    rec = _rec('levels/s2/Level209.json', outdir, 'loopidle')
    w = rec.v.world
    ff = _item(rec, 'FireFakir')
    w._return_to_idle(ff)
    p = _player(rec, ff)
    ok &= check('items: ReturnToIdle keeps a UseAnimationType idle looping',
                p is not None and p.mode == 'looping', p.mode if p else None)
    rec = _rec('levels/s1/Level113.json', outdir, 'fusebox')
    w = rec.v.world
    fb = _item(rec, 'FuseBox')
    w.set_primed(fb, True)
    ok &= check('items: primed FuseBox hides its strip (PlayItemAnimation NONE)',
                fb.sprite is not None and fb.sprite.hidden)

    # -- F1: TrickItem.KidActions animates Item.Kid, the OlgaKid item -----
    rec = _rec('levels/s2/Level205.json', outdir, 'kid')
    w = rec.v.world
    ss = _item(rec, 'SandSculpture')
    okid = rec.v.level.items[ss.kid_item]
    w.routines[0]._trick_kid_actions(ss)
    p = _player(rec, okid)
    ok &= check('items: SandSculpture animates the OlgaKid item',
                p is not None and p.anim.name == 'N2TrickItemIdleTricked',
                p.anim.name if p else None)

    # -- TrickItem.WaterPuddleBehavior: the L210 Valve's Extra1 pose hands
    #    the click over to its puddle once (TrickItem.cs:1240-1251) --------
    rec = _rec('levels/s2/Level210.json', outdir, 'valve')
    w = rec.v.world
    valve = _item(rec, 'Valve')
    puddle = rec.v.level.items[valve.object_to_prime]
    before = puddle.clickable
    w._item_anim_completed(valve, 'N2TrickItemExtra1')
    ok &= check('items: Valve Extra1 end hands the click to the puddle',
                bool(not before and puddle.clickable and not valve.clickable
                     and puddle.primed_animation == 'N2TrickItemIdleNormal'
                     and valve.only_once_water_puddle),
                (before, puddle.clickable, valve.clickable))

    # -- F13: the WaterPuddle sign flip at load (Item.Start -> SetPrimed) --
    rec = _rec('levels/s2/Level201.json', outdir, 'puddle')
    wp = _item(rec, 'WaterPuddle')
    ok &= check('items: WaterPuddle DeltaLocation flipped at load',
                abs(wp.dx + 0.6) < 1e-3, wp.dx)
    return ok

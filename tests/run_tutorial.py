"""The tutorial suite: drive the five tutorial scenes through runtime/app.py
and assert the LevelScript/camera contracts — the signal kinds
(location / door / zone / item use / look-at), the unlock chains, the
neighbour freezes, the camera state machines, the ForceWin tail.

    python3 tests/run_tutorial.py
"""
import os, sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

from prefs import MemoryPrefs
from menu import GameIntroAnimation
from app import App

DT = 1.0 / 60.0
_ok = True


def check(name, cond, detail=''):
    global _ok
    print('%-52s %s %s' % (name, 'ok' if cond else 'FAIL',
                           '' if cond else detail))
    _ok &= bool(cond)
    return cond


def start(scene):
    GameIntroAnimation.finished = False
    app = App(headless=True, prefs=MemoryPrefs())
    app.load_level(scene)
    app.tick(DT, events=(False, True, False, False))    # skip the cards
    return app


def step(app, n=1):
    for _ in range(n):
        app.tick(DT, events=(False, False, False, False))


def wait(app, cond, secs=30.0):
    for _ in range(int(secs / DT)):
        step(app)
        if cond():
            return True
    return False


def use_with(app, item, inv_type):
    w = app.viewer.world
    e = next(i for i in w.inventory.items if i['type'] == inv_type)
    w.inventory.used = e
    return w.woody_click(item.x, item.y, item, None)


def click_door(app, pid):
    L = app.viewer.level
    wd = app.viewer.woody
    d = L.door_by_pid(pid)
    near = d if d.zone == (wd.zone.pid if wd.zone else None) else \
        next(dd for dd in L.doors if dd.link_to == d.pid)
    app.viewer.world.woody_click(near.x, near.y, None, near)


def teleport(app, x, y, zone_pid):
    wd = app.viewer.woody
    wd.steps = []
    wd._step = None
    wd.state = wd.IDLE
    wd.sprite.x, wd.sprite.y = x, y
    z = app.viewer.level.zone_by_pid(zone_pid)
    if z is not None:
        wd.zone = z


def settle(app, secs=20.0):
    """Woody standing, out of any door pass"""
    wd = app.viewer.woody
    return wait(app, lambda: wd.state == wd.IDLE and not wd.is_warping, secs)


def main():
    # -- the Intro scenes' LevelScripts (the mobile's: the PC profile runs
    # the PC's own tutorials, checked below) -------------------------------
    profile = os.environ.get('NFH_PROFILE')
    os.environ['NFH_PROFILE'] = 'mobile'
    # -- Intro101: the full walkthrough (location + door signals) --------
    app = start('Intro101')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    check('101: the tutorial activates after the cards',
          t is not None and t.active and t.action_index == 0)
    check('101: the world clock started', wait(app, lambda: w.time > 0.1, 2))
    w.woody_click(3.7, 0.3, None, None)
    check('101: the location signal (x threshold)',
          wait(app, lambda: t.action_index >= 1))
    d = L.door_by_pid(128)
    check('101: the action unlocked the doors', not d.locked)
    click_door(app, 128)
    check('101: the door signal (the far half)',
          wait(app, lambda: t.action_index >= 2))
    w.woody_click(-2.1, 0.4, None, None)
    check('101: the second location', wait(app, lambda: t.action_index >= 3))
    click_door(app, 144)
    step(app, int(8 / DT))
    w.woody_click(0.9, -2.3, None, None)
    check('101: the third location', wait(app, lambda: t.action_index >= 4))
    click_door(app, 155)
    check('101: the last door wins the game (ForceWinGame)',
          wait(app, lambda: w.game.ending, 20) and w.game.won
          and w.game.final_viewer_rating == 100)

    # -- Intro102: look-at, item use, unfreeze, the 102 camera ------------
    app = start('Intro102')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    cam = app.tutorial_camera
    items = {it.name: it for it in L.items.values()}
    plant, drawer = items['PlantStink'], items['Drawer']
    mum, ground = items['MumPicture'], items['Ground']
    check('102: the camera script binds',
          type(cam).__name__ == 'TutorialCamera102')
    check('102: the neighbour ships frozen', cam.rott_routine.frozen)
    w.woody_click(plant.x, plant.y, plant, None)
    check('102: the look-at signal (CompleteOnLookAt)',
          wait(app, lambda: t.action_index >= 1))
    check('102: it unlocked the drawer', not drawer.locked)
    w.woody_click(drawer.x, drawer.y, drawer, None)
    check('102: the searched-item signal',
          wait(app, lambda: t.action_index >= 2))
    use_with(app, mum, 'IT_Marker')
    check('102: the trick-use signal',
          wait(app, lambda: t.action_index >= 3) and mum.tricked)
    click_door(app, 217)
    check('102: the door signal unfreezes the neighbour',
          wait(app, lambda: t.action_index >= 4)
          and not cam.rott_routine.frozen)
    check('102: the camera rides the fix (MumSmeared -> Hold)',
          wait(app, lambda: cam.state == 'Hold', 60)
          and not mum.is_tricked(L.items))
    teleport(app, ground.x - 0.4, ground.y, 51)
    use_with(app, ground, 'IT_Marbles')
    check('102: the marbles signal', wait(app, lambda: t.action_index >= 5)
          and ground.tricked)
    check('102: the alternate description latched (on trick)',
          t._alt.get(id(t.actions[4])) is True
          or t.get_description(t.actions[5]) != '')
    teleport(app, 0.5, -1.4, 47)
    w.woody_click(0.0, -1.4, None, None)
    check('102: the final location wins',
          wait(app, lambda: t.action_index >= 6, 20) and w.game.won)

    # -- Intro103: the dog walk, the MoveOnly unlocks, the 103 camera -----
    app = start('Intro103')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    cam = app.tutorial_camera
    r = cam.rott_routine
    rott = w.pawns['Rottweiler']
    items = {it.name: it for it in L.items.values()}
    drawer, ground = items['Drawer'], items['Ground']
    wardrobe = items['Wardrobe']
    check('103: the camera script binds',
          type(cam).__name__ == 'TutorialCamera103')
    check('103: the dog wakes the frozen neighbour '
          'and the walk unlocks the drawer',
          wait(app, lambda: not drawer.locked, 45))
    check('103: the walk ends frozen again (FreezeAfterCompletion)',
          r.frozen)
    check('103: the camera consumed FreezeNeighbour (snap to Woody)',
          not r.freeze_neighbour and cam.only_one_time)
    w.woody_click(drawer.x, drawer.y, drawer, None)
    check('103: the drawer search signals',
          wait(app, lambda: t.action_index >= 1))
    use_with(app, ground, 'IT_Marbles')
    check('103: the marbles trick signals',
          wait(app, lambda: t.action_index >= 2) and ground.tricked)
    click_door(app, 219)
    check('103: the door signal', wait(app, lambda: t.action_index >= 3))
    w.woody_click(wardrobe.x, wardrobe.y, wardrobe, None)
    check('103: the hide-item use signals',
          wait(app, lambda: t.action_index >= 4) and wd.hiding)
    check('103: the camera unfreezes him into the marbles '
          '(Hold -> MarbleTrick)',
          wait(app, lambda: cam.state == 'MarbleTrick', 45)
          and not r.frozen)
    check('103: the slip pays the level',
          wait(app, lambda: w.game.won, 90))
    if profile is None:
        del os.environ['NFH_PROFILE']
    else:
        os.environ['NFH_PROFILE'] = profile

    # -- the Intro scenes under the PC profile: game.exe's tutorial classes
    os.environ['NFH_PROFILE'] = 'pc'
    app = start('Intro101')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    check('pc 101: Level_Tutorial1 binds, no camera script',
          type(t).__name__ == 'TutorialPC101' and app.tutorial_camera is None)
    check('pc 101: the director speaks on tick 15 (12 ticks counted)',
          wait(app, lambda: t.msg == 'tut_target1', 3) and t.tick_n == 15
          and t.text.startswith("Welcome to the 'Neighbours from Hell' show."))
    signs = t.pc['signs']
    z, x = t._point(signs['kit/sign'])
    w.woody_click(x - 0.5, wd.sprite.y, None, None)
    check('pc 101: the kit sign\'s nearobj stops Woody at it',
          wait(app, lambda: t.msg == 'tut_door', 10) and settle(app)
          and abs(t._pc_at(wd)[1] - signs['kit/sign'][0]) < 15)
    check('pc 101: lir/kit opened', not L.door_by_pid(128).locked)
    click_door(app, 128)
    check('pc 101: the room trigger as the pass starts: tut_target2',
          wait(app, lambda: t.msg == 'tut_target2', 15) and wd.zone.name == 'Zone02')
    settle(app)
    z, x = t._point(signs['lir/sign'])
    w.woody_click(x, wd.sprite.y, None, None)
    check('pc 101: the lir sign opens lir/anc: tut_target3',
          wait(app, lambda: t.msg == 'tut_target3', 15)
          and not L.door_by_pid(144).locked and 'anc/sign' in t.signs)
    settle(app)
    click_door(app, 144)
    check('pc 101: into anc (no stop on that trigger)',
          wait(app, lambda: t.state == 9 and t.prev == 7, 20))
    settle(app)
    z, x = t._point(signs['anc/sign'])
    w.woody_click(x, wd.sprite.y, None, None)
    check('pc 101: the anc sign opens the front door: tut_exit',
          wait(app, lambda: t.msg == 'tut_exit', 20) and not L.door_by_pid(130).locked)
    settle(app)
    click_door(app, 130)
    check('pc 101: the porch scores the trick (100) and ends the level',
          wait(app, lambda: w.game.ending, 20) and w.game.won
          and w.game.final_viewer_rating == 100)

    app = start('Intro102')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    items = {it.name: it for it in L.items.values()}
    rott = w.pawns['Rottweiler']
    r = t.rott_routine
    check('pc 102: the tutorial_2 classes bind, the neighbour at kit 500/420',
          type(t).__name__ == 'TutorialPC102' and app.tutorial_camera is None
          and rott.zone.name == 'Zone03' and r.frozen)
    check('pc 102: tick 15: the plant\'s marker, tut_lookat_plant',
          wait(app, lambda: t.msg == 'tut_lookat_plant', 3)
          and 'PlantStink' in t.markers)
    plant = items['PlantStink']
    w.woody_click(plant.x, plant.y, plant, None)
    check('pc 102: Woody at the flower: the chest shown, tut_take_objects',
          wait(app, lambda: t.msg == 'tut_take_objects', 15)
          and not items['Drawer'].locked and 'Drawer' in t.markers)
    settle(app)
    drawer = items['Drawer']
    w.woody_click(drawer.x, drawer.y, drawer, None)
    check('pc 102: `take`: the doors to lir, the picture\'s marker',
          wait(app, lambda: t.msg == 'tut_use_marker', 15)
          and not L.door_by_pid(217).locked and 'MumPicture' in t.markers)
    settle(app)
    use_with(app, items['MumPicture'], 'IT_Marker')
    check('pc 102: `marker`: tut_hallway1',
          wait(app, lambda: t.msg == 'tut_hallway1', 30))
    settle(app)
    click_door(app, 217)
    check('pc 102: Woody in anc: `start`, the camera on him, tut_watch2',
          wait(app, lambda: t.msg == 'tut_watch2', 30) and t.follow
          and wait(app, lambda: not r.frozen, 1))
    check('pc 102: the doubletake, then tut_laugh1 before the fire',
          wait(app, lambda: t.msg == 'tut_laugh1', 40) and not w.pay_log)
    check('pc 102: the picture cleaned: anc/kit opened, the camera back',
          wait(app, lambda: t.state == 13 and t.prev == 9, 30)
          and not t.follow and not L.door_by_pid(220).locked
          and w.pay_log and w.pay_log[0][1:3] == ('MumPicture', 50))
    check('pc 102: parked at sign 1 (its neighbor hotspot)',
          wait(app, lambda: t.nb_state == 3 and r.frozen, 30)
          and wait(app, lambda: t._goto_to is None, 1)
          and t._pc_at(rott)[1:] == tuple(t.pc['points']['lir_sign1'][:2]),
          str(t._pc_at(rott)))
    t0 = w.time
    check('pc 102: 96 updates there, then off to sign 2',
          wait(app, lambda: t.nb_state == 5, 15)
          and 7.9 < w.time - t0 < 8.3)
    if profile is None:
        del os.environ['NFH_PROFILE']
    else:
        os.environ['NFH_PROFILE'] = profile

    os.environ['NFH_PROFILE'] = 'pc'
    app = start('Intro103')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    items = {it.name: it for it in L.items.values()}
    rott = w.pawns['Rottweiler']
    r = t.rott_routine
    check('pc 103: the tutorial_3 classes bind, the neighbour in lir',
          type(t).__name__ == 'TutorialPC103' and rott.zone.name == 'Zone02')
    check('pc 103: tick 15: the introduction and the dog\'s whistle',
          wait(app, lambda: t.msg == 'introduction', 3)
          and wait(app, lambda: t._dog_fsm().awake, 1))
    check('pc 103: the alarm runs him, the camera on him',
          wait(app, lambda: t.in_alarm, 5) and t.follow)
    check('pc 103: after it sign 1 and `target`: the chest, tut_take_marbles',
          wait(app, lambda: t.msg == 'tut_take_marbles', 40)
          and not t.follow and not items['Drawer'].locked)
    settle(app)
    drawer = items['Drawer']
    w.woody_click(drawer.x, drawer.y, drawer, None)
    check('pc 103: `take`: anc/kit opened, tut_put_marbles',
          wait(app, lambda: t.msg == 'tut_put_marbles', 15)
          and not L.door_by_pid(219).locked)
    settle(app)
    click_door(app, 219)
    wait(app, lambda: wd.zone.name == 'Zone03', 20)
    settle(app)
    wd.sneaking = True
    use_with(app, items['Ground'], 'IT_Marbles')
    check('pc 103: the marbles near Woody: tut_hiding',
          wait(app, lambda: t.msg == 'tut_hiding', 20))
    settle(app)
    click_door(app, 148)
    check('pc 103: Woody in anc: tut_hiding2',
          wait(app, lambda: t.msg == 'tut_hiding2', 20))
    settle(app)
    wardrobe = items['Wardrobe']
    w.woody_click(wardrobe.x, wardrobe.y, wardrobe, None)
    check('pc 103: `hide`: lir/kit closed, `start`, tut_watch',
          wait(app, lambda: t.msg == 'tut_watch', 20)
          and L.door_by_pid(208).locked and t.follow)
    check('pc 103: round lir/kit through anc',
          wait(app, lambda: rott.zone.name == 'Zone01', 30))
    check('pc 103: the slip pays the level, Ha, ha! after the fire',
          wait(app, lambda: w.game.won, 60)
          and wait(app, lambda: t.msg == 'tut_laugh', 1))
    if profile is None:
        del os.environ['NFH_PROFILE']
    else:
        os.environ['NFH_PROFILE'] = profile

    # -- Level201: the NFH2 camera's opening (the mobile's tutorial: the
    # PC profile runs the PC's own, checked below) ------------------------
    os.environ['NFH_PROFILE'] = 'mobile'
    app = start('Level201')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    cam = app.tutorial_camera
    items = {it.name: it for it in L.items.values()}
    chest = items['SoapChest']
    check('201: the camera script binds',
          type(cam).__name__ == 'TutorialCameraNFH2')
    step(app)                             # the Start state's first tick
    check('201: the stairs start locked (the Start state)',
          cam.door('LeftSideStair').locked and cam.door('RightSideStair').locked)
    w.woody_click(chest.x, chest.y, chest, None)
    check('201: the chest signals and locks back',
          wait(app, lambda: t.action_index >= 1) and chest.locked
          and any(i['type'] == 'IT2_Soap' for i in w.inventory.items))
    w.woody_click(5.0, -2.0, None, None)
    check('201: the walk signal unfreezes the neighbour',
          wait(app, lambda: t.action_index >= 2)
          and not cam.rott_routine.frozen)
    check('201: the camera walks him (Start -> Moving, Woody frozen)',
          wait(app, lambda: cam.state == 'Moving', 30) and wd.frozen)
    check('201: the fifth step completes the message (Moving -> Hold)',
          wait(app, lambda: cam.state == 'Hold', 90)
          and t.action_index >= 3 and not wd.frozen)
    if profile is None:
        del os.environ['NFH_PROFILE']
    else:
        os.environ['NFH_PROFILE'] = profile

    # -- Level201 under the PC profile: the PC's director and neighbour ----
    os.environ['NFH_PROFILE'] = 'pc'
    app = start('Level201')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    items = {it.name: it for it in L.items.values()}
    rott = w.pawns.get('Rottweiler')
    check('pc 201: the PC tutorial binds, no camera script',
          type(t).__name__ == 'TutorialPC201' and app.tutorial_camera is None)
    step(app)
    check('pc 201: the welcome box holds the level',
          t.modal and t.step == '8087')
    t.dismiss()
    check('pc 201: Woody starts in bottomleft, the chest shut',
          wd.zone.name == 'Zone01' and items['SoapChest'].locked)
    wps = t.pc['waypoints']
    z, x, _y = t._pc_point(wps['waypoint1'])
    w.woody_click(x, wd.sprite.y, None, None)
    check('pc 201: waypoint1 -> waypoint2',
          wait(app, lambda: t.step == '7df6', 30) and 'waypoint2' in t.signs)
    z, x, _y = t._pc_point(wps['waypoint2'])
    w.woody_click(x, wd.sprite.y, None, None)
    check('pc 201: waypoint2 opens the chest',
          wait(app, lambda: not items['SoapChest'].locked, 30))
    chest = items['SoapChest']
    w.woody_click(chest.x, chest.y, chest, None)
    check('pc 201: the soap shows waypoint3',
          wait(app, lambda: 'waypoint3' in t.signs, 30))
    z, x, _y = t._pc_point(wps['waypoint3'])
    w.woody_click(x, wd.sprite.y, None, None)
    check('pc 201: waypoint3 starts his demo lap',
          wait(app, lambda: t.nb_phase == 'demo', 30)
          and not t.rott_routine.frozen)
    check('pc 201: his left slip shows the puddle (soappuddle)',
          wait(app, lambda: 'soappuddle' in t.shown, 120)
          and not items['WaterPuddle'].locked)
    check('pc 201: he waits at the captain\'s hat',
          wait(app, lambda: t.nb_phase == 'cap', 60)
          and abs(rott.sprite.x - items['CaptainHat'].x) < 0.3)
    if profile is None:
        del os.environ['NFH_PROFILE']
    else:
        os.environ['NFH_PROFILE'] = profile

    # -- Level206: the NFH2206 camera's opening (the mobile's lesson: the PC
    # profile runs the PC's own, checked below) ----------------------------
    os.environ['NFH_PROFILE'] = 'mobile'
    app = start('Level206')
    w, wd, t = app.viewer.world, app.viewer.woody, app.tutorial
    cam = app.tutorial_camera
    check('206: the camera script binds',
          type(cam).__name__ == 'TutorialCameraNFH2206')
    check('206: the in-game actions were inserted at 4',
          len(cam.rott_routine.actions) > 4)
    check('206: Start freezes Woody and walks the neighbour',
          wait(app, lambda: cam.state == 'Moving', 10))
    check('206: the fourth step frees Woody and messages (-> Hold)',
          wait(app, lambda: cam.state == 'Hold', 90)
          and t.action_index >= 1 and not wd.frozen)
    if profile is None:
        del os.environ['NFH_PROFILE']
    else:
        os.environ['NFH_PROFILE'] = profile

    # -- Level206 under the PC profile: the director, the Mother and him ----
    os.environ['NFH_PROFILE'] = 'pc'
    app = start('Level206')
    w, wd, t, L = (app.viewer.world, app.viewer.woody, app.tutorial,
                   app.viewer.level)
    items = {it.name: it for it in L.items.values()}
    rott = w.pawns.get('Rottweiler')
    check('pc 206: the PC lesson binds, no camera script',
          type(t).__name__ == 'TutorialPC206' and app.tutorial_camera is None)
    check('pc 206: step1, he laughs at Fifi, Woody free',
          wait(app, lambda: 'step1' in t.shown, 5)
          and rott.anim.anim.name == 'LaughLeftInfinite' and not wd.frozen)
    check('pc 206: her call runs him to her chair',
          wait(app, lambda: t.nb.step == 'f082', 20) and t.mom.step == 'c1d9')
    check('pc 206: her order sends him for the pillows',
          wait(app, lambda: t.nb.step == 'ef9e', 20))
    check('pc 206: the pillow given, her tutorial: step2, the toy box',
          wait(app, lambda: 'step2' in t.shown, 60)
          and 'ToyBox' in t.markers and t.nb.step == 'ed50')
    box = items['ToyBox']
    w.woody_click(box.x, box.y, box, None)
    check('pc 206: the fart bag taken: step2a, the pillows',
          wait(app, lambda: 'step2a' in t.shown and 'Pillows' in t.markers, 60))
    use_with(app, items['Pillows'], 'IT2_Fartbag')
    check('pc 206: the fart bag on the pillows: step3, the pipe',
          wait(app, lambda: 'step3' in t.shown and 'Pipe' in t.markers, 60))
    pipe = items['Pipe']
    w.woody_click(pipe.x, pipe.y, pipe, None)
    check('pc 206: Woody hidden: step4, her second call',
          wait(app, lambda: 'step4' in t.shown, 60)
          and wait(app, lambda: t.nb.step == 'ecb5', 30))
    check('pc 206: the fart pays the chair\'s trick',
          wait(app, lambda: w.game.completed >= 1, 60)
          and items['DeckChair'].already_tricked)
    check('pc 206: her fight, his shout, the lap from Fifi\'s take',
          wait(app, lambda: t.done, 30)
          and t.rott_routine.index == 4 and not t.rott_routine.frozen)
    check('pc 206: step5 until Woody leaves the pipe',
          'step5' in t.shown or wait(app, lambda: 'step5' in t.shown, 10))
    if profile is None:
        del os.environ['NFH_PROFILE']
    else:
        os.environ['NFH_PROFILE'] = profile

    print()
    print('ALL OK' if _ok else 'FAILURES')
    return 0 if _ok else 1


if __name__ == '__main__':
    sys.exit(main())

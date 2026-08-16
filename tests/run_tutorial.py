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


def main():
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

    # -- Level201: the NFH2 camera's opening -------------------------------
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

    # -- Level206: the NFH2206 camera's opening ----------------------------
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

    print()
    print('ALL OK' if _ok else 'FAILURES')
    return 0 if _ok else 1


if __name__ == '__main__':
    sys.exit(main())

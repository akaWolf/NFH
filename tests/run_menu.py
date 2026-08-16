"""The menu/flow suite: drive runtime/app.py's scene machine headless and
assert the original's contracts — the splash, the window graph, the level
tiles and their prefs, the settings widgets, the title cards, the in-game
menu, the exit confirmations, the score screen's exits, the language
reload, the fullscreen pref.

    python3 tests/run_menu.py
"""
import os, sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

from prefs import MemoryPrefs
from menu import GameIntroAnimation, ControlRadioButton
from app import App

DT = 1.0 / 60.0
_ok = True


def check(name, cond, detail=''):
    global _ok
    print('%-46s %s %s' % (name, 'ok' if cond else 'FAIL',
                           '' if cond else detail))
    _ok &= bool(cond)
    return cond


def step(app, n=1, dt=DT):
    for _ in range(n):
        app.tick(dt, events=(False, False, False, False))


def click_at(app, x, y):
    app._mouse = (x, y)
    app._mouse_down = True
    app.tick(DT, events=(True, False, False, False))
    app._mouse_down = False
    app.tick(DT, events=(False, True, False, False))


def click(app, w):
    r = w.rect
    click_at(app, r[0] + r[2] / 2.0, r[1] + r[3] / 2.0)


def esc(app):
    app.tick(DT, events=(False, False, False, True))


def widget(scene, name, cls=None, active=True):
    for w in scene.widgets:
        if scene.scene.go_name(w.go) == name \
                and (cls is None or isinstance(w, cls)) \
                and (not active or w.active):
            return w
    return None


def windows(menu):
    return sorted(menu.scene.go_name(go)
                  for go, e in menu.scene.find('ControlWindow')
                  if menu.scene.active_in_hierarchy(go))


def fresh_app(prefs=None):
    GameIntroAnimation.finished = False   # the per-process splash latch
    return App(headless=True, prefs=prefs or MemoryPrefs())


def into_selection(app, season=1):
    """Splash -> MenuStart -> GameSelection -> MenuLevels(2)"""
    if app.menu.intro is not None and app.menu.intro.enabled:
        app.tick(DT, events=(False, True, False, False))
    click(app, widget(app.menu, 'MenuButtonStart'))
    btn = 'OnHouseButtonStart' if season == 1 else 'MenuButtonStart2'
    click(app, widget(app.menu, btn))
    step(app)                             # the tile initializer's OnEnable


def start_tile(app, level):
    tiles = [w for w in app.menu.widgets
             if isinstance(w, ControlRadioButton) and w.active]
    tile = next(w for w in tiles if w.level_to_start == level)
    click(app, tile)
    click(app, widget(app.menu, 'MenuButtonStart'))


def igm_widget(app, name):
    return widget(app.igm, name)


def main():
    # -- the splash and the window graph ---------------------------------
    app = fresh_app()
    m = app.menu
    check('splash: GameIntroAnimation runs first',
          m.intro is not None and m.intro.enabled and m.intro.state == 'Company')
    step(app, int(2.2 / DT))
    check('splash: Company2 after CompanyTime', m.intro.state == 'Company2')
    app.tick(DT, events=(False, True, False, False))
    check('splash: a click enters the game', not m.intro.enabled)
    check('entry: MenuStart + Title up', windows(m) == ['MenuStart', 'Title'])
    click(app, widget(m, 'MenuButtonStart'))
    check('entry: START opens GameSelection',
          windows(m) == ['GameSelection', 'Title'])
    click(app, widget(m, 'MenuBackButton'))
    check('entry: BACK returns to MenuStart',
          windows(m) == ['MenuStart', 'Title'])
    click(app, widget(m, 'MenuButtonCredits'))
    check('entry: credits window opens', windows(m) == ['MenuCredits'])
    step(app, 5)
    check('credits: entries loaded and paused',
          m.credits is not None and m.credits.data_loaded
          and not m.credits.start_moving)
    step(app, int(1.6 / DT))
    check('credits: scroll starts after 1.5 s', m.credits.start_moving)
    click_at(app, 400, 300)               # CloseWithAnyKey
    check('credits: any click closes to MenuStart',
          windows(m) == ['MenuStart', 'Title'])

    # -- Esc on the first window: the quit confirmation -------------------
    esc(app)
    check('quit: Esc raises the confirmation',
          m.exit_message.should_show and m.confirm_opened is False)
    yr = m.exit_message.no_rect
    click_at(app, yr[0] + yr[2] / 2, yr[1] + yr[3] / 2)
    check('quit: NO hides it', not m.exit_message.should_show and not app.quit)
    esc(app)
    yr = m.exit_message.yes_rect
    click_at(app, yr[0] + yr[2] / 2, yr[1] + yr[3] / 2)
    check('quit: YES quits the application', app.quit)

    # -- the level selection, the tiles, the prefs -------------------------
    app = fresh_app()
    m = app.menu
    into_selection(app, 1)
    check('levels: MenuLevels opens', windows(m) == ['MenuLevels'])
    tiles = [w for w in m.widgets
             if isinstance(w, ControlRadioButton) and w.active]
    check('levels: 17 season-1 tiles', len(tiles) == 17)
    sel = [w for w in tiles if w.texture_index == 2]
    check('levels: the initializer selects tile 0 (Intro101)',
          len(sel) == 1 and sel[0].level_to_start == 'Intro101',
          [m.scene.go_name(w.go) for w in sel])
    rend = next(r for r in m.renderers.values()
                if m.scene.active_in_hierarchy(r.go))
    check('levels: the page shows L0 (Intro101) data',
          rend.selected_level == 0 and rend.title != '', rend.selected_level)
    tile = next(w for w in tiles if w.level_to_start == 'Level101')
    click(app, tile)
    check('levels: a tile selects and points the start button',
          widget(m, 'MenuButtonStart').level_to_start == 'Level101'
          and app.prefs.get_int('LastLoadedLevel', -1) == 3)
    check('levels: the page follows the tile', rend.selected_level == 3)
    check('levels: nothing is locked (the port unlocks the packs)',
          not any(w.level_locked for w in tiles))

    # -- the level start: the cards, the world clock ----------------------
    click(app, widget(m, 'MenuButtonStart'))
    check('level: the scene machine switches', app.state == 'level'
          and app.level_scene_name == 'Level101')
    check('cards: IntroAnimation runs', app.cards is not None
          and app.cards.running and app.cards.STATES[app.cards.state] == 'Company')
    check('cards: the world clock holds', app.viewer.world.time == 0.0)
    check('cards: the episode string is L3T',
          app.cards.episode == app.igm.loc('L3T') and app.cards.episode != '')
    step(app, 30)
    check('cards: still holding after 0.5 s', app.viewer.world.time == 0.0)
    app.tick(DT, events=(False, True, False, False))    # skip
    check('cards: a click starts the game', not app.cards.running)
    step(app, 30)
    check('level: the world clock runs', app.viewer.world.time > 0.4)

    # -- the in-game menu --------------------------------------------------
    esc(app)
    check('igm: Esc opens the menu', app.igm.enabled
          and app.igm.time_scale == 0.0)
    t0 = app.viewer.world.time
    step(app, 10)
    check('igm: the world freezes', app.viewer.world.time == t0)
    check('igm: the level page renders',
          any(r.enabled and r.selected_level == 3
              for r in app.igm.renderers.values()))
    click(app, igm_widget(app, 'MenuButtonOptions'))
    check('igm: Options window swaps in',
          app.igm.scene.active_in_hierarchy(
              igm_widget(app, 'MenuButtonBack').go))
    sld = igm_widget(app, 'MenuSliderMusic')
    r = sld.screen_rect
    click_at(app, r[0] + r[2] * 0.25, r[1] + r[3] / 2)
    check('igm: the music slider writes the pref',
          0.2 <= app.prefs.get_float('MusicLevel', -1) <= 0.3,
          app.prefs.get_float('MusicLevel', -1))
    tgl = igm_widget(app, 'MenuToggleMusic')
    click(app, tgl)
    check('igm: the music toggle flips to 0',
          app.prefs.get_int('MusicEnabled', -1) == 0
          and tgl.texture_index_delta == 0)
    click(app, tgl)
    check('igm: and back to 1', app.prefs.get_int('MusicEnabled', -1) == 1
          and tgl.texture_index_delta == 3)
    fs = next((w for w in app.igm.widgets
               if getattr(w, 'setting_key', '') == 'Fullscreen'), None)
    check('igm: the fullscreen toggle rides the options', fs is not None)
    if fs is not None:
        click(app, fs)
        check('fullscreen: the pref and the window flag follow',
              app.prefs.get_int('Fullscreen', -1) == 1 and app.fullscreen)
        click(app, fs)
        check('fullscreen: and back off',
              app.prefs.get_int('Fullscreen', -1) == 0 and not app.fullscreen)
    click(app, igm_widget(app, 'MenuButtonBack'))
    click(app, igm_widget(app, 'MenuButtonContinue')
          or igm_widget(app, 'MenuButtonContinue2'))
    check('igm: Continue resumes', not app.igm.enabled
          and app.igm.time_scale == 1.0)
    step(app, 5)
    check('igm: the world runs again', app.viewer.world.time > t0)

    # -- the restart confirmation ------------------------------------------
    esc(app)
    click(app, igm_widget(app, 'MenuButtonRestart'))
    check('restart: the confirmation shows',
          app.igm.is_exit_confirmation_shown())
    nr = app.igm.exit_message.no_rect
    click_at(app, nr[0] + nr[2] / 2, nr[1] + nr[3] / 2)
    check('restart: NO stays in the level', app.state == 'level'
          and app.igm.enabled)
    click(app, igm_widget(app, 'MenuButtonRestart'))
    yr = app.igm.exit_message.yes_rect
    wid = id(app.viewer.world)
    click_at(app, yr[0] + yr[2] / 2, yr[1] + yr[3] / 2)
    check('restart: YES reloads the level', app.state == 'level'
          and app.level_scene_name == 'Level101'
          and id(app.viewer.world) != wid)

    # -- SelectEpisode -> the level selection -------------------------------
    app.tick(DT, events=(False, True, False, False))    # skip the cards
    esc(app)
    click(app, igm_widget(app, 'MenuButtonSelectEpisode'))
    yr = app.igm.exit_message.yes_rect
    click_at(app, yr[0] + yr[2] / 2, yr[1] + yr[3] / 2)
    check('select episode: back on Entry', app.state == 'menu')
    step(app, 2)
    check('select episode: the level selection is open',
          windows(app.menu) == ['MenuLevels'], windows(app.menu))

    # -- the score screen's exits ------------------------------------------
    start_tile(app, 'Level101')
    app.tick(DT, events=(False, True, False, False))    # skip the cards
    w = app.viewer.world
    w.game.force_win()
    step(app, 5)
    check('score: the forced win ends the game', w.game.ending)
    check('score: the progress is saved',
          app.prefs.get_int('LevelCompleted3', -1) == 1
          and app.prefs.get_int('RatingAchieved3', -1) == 100
          and app.prefs.get_int('LevelPerfect3', -1) == 1)
    for _ in range(int(4.0 / DT)):        # the finish pose -> GameEnded
        step(app)
        if w.game.ended:
            break
    check('score: the screen is up', w.game.ended)
    hud = app.viewer.hud
    rr = hud.rect('RestartButtonRect')
    click_at(app, rr[0] + rr[2] / 2, rr[1] + rr[3] / 2)
    check('score: Restart reloads', app.state == 'level'
          and app.viewer.world is not w)
    app.tick(DT, events=(False, True, False, False))
    w = app.viewer.world
    w.game.force_win()
    for _ in range(int(4.0 / DT)):
        step(app)
        if w.game.ended:
            break
    orr = app.viewer.hud.rect('OkButtonRect')
    click_at(app, orr[0] + orr[2] / 2, orr[1] + orr[3] / 2)
    step(app, 2)
    check('score: OK returns to the level selection', app.state == 'menu'
          and windows(app.menu) == ['MenuLevels'], windows(app.menu))
    tiles = [w2 for w2 in app.menu.widgets
             if isinstance(w2, ControlRadioButton) and w2.active]
    tile = next(w2 for w2 in tiles if w2.level_to_start == 'Level101')
    check('score: the tile shows the passed state and 100%',
          tile.is_level_passed and tile.text == '100%'
          and tile.textures[0].endswith('_perfect'), tile.textures[0])
    check('score: the initializer re-selects the last level',
          tile.texture_index == 2)

    # -- season 2 ------------------------------------------------------------
    app = fresh_app()
    into_selection(app, 2)
    check('s2: MenuLevels2 opens', windows(app.menu) == ['MenuLevels2'])
    tiles = [w for w in app.menu.widgets
             if isinstance(w, ControlRadioButton) and w.active]
    check('s2: 14 tiles, no percentages',
          len(tiles) == 14 and all(t.dont_show_percentages for t in tiles))
    start_tile(app, 'Level201')
    check('s2: Level201 loads', app.state == 'level'
          and app.level_season == 's2'
          and app.prefs.get_int('LastLoadedLevel2', -1) == 0)
    check('s2: the cards use the season-2 strings',
          app.cards is not None and app.cards.episode == app.igm.loc('L18T'))
    app.tick(DT, events=(False, True, False, False))
    step(app, 5)
    check('s2: the world runs', app.viewer.world.time > 0.0)
    check('s2: MenuLoader stamps 2', app.menu_loader == 2)

    # -- the exit door's confirmation (S1: ExitDoor + FinishedEntrance,
    # Pawn.cs:1378-1383; S2 levels ship no ExitDoor) --------------------------
    app = fresh_app()
    into_selection(app, 1)
    start_tile(app, 'Level101')
    app.tick(DT, events=(False, True, False, False))    # skip the cards
    wd = app.viewer.woody
    for _ in range(int(12.0 / DT)):       # the entrance walk-in
        step(app)
        if wd.finished_entrance and not wd.input_locked \
                and not wd.anim.blocking:
            break
    check('exit door: the entrance finishes', wd.finished_entrance)
    exit_doors = [d for d in app.viewer.level.doors if d.exit_door]
    check('exit door: the scene has one', bool(exit_doors))
    d = exit_doors[0]
    wd.sprite.x, wd.sprite.y = d.x, d.y
    z = app.viewer.level.zone_by_pid(d.zone)
    if z is not None:
        wd.zone = z
    app.viewer.world.woody_click(d.x, d.y, None, d)
    for _ in range(240):
        step(app)
        if app.igm.is_exit_confirmation_shown():
            break
    check('exit door: the dialog shows',
          app.igm.is_exit_confirmation_shown())
    check('exit door: the pawn parks',
          wd.waiting_for_exit_confirmation and wd.movement_paused)
    check('exit door: the world keeps running (no pause)',
          app.igm.time_scale == 0.0)
    nr = app.igm.exit_message.no_rect
    click_at(app, nr[0] + nr[2] / 2, nr[1] + nr[3] / 2)
    check('exit door: NO aborts the exit',
          not wd.waiting_for_exit_confirmation
          and not wd.exit_confirmation_shown
          and app.state == 'level' and not app.viewer.world.game.ending)
    app.viewer.world.woody_click(d.x, d.y, None, d)
    for _ in range(240):
        step(app)
        if app.igm.is_exit_confirmation_shown():
            break
    check('exit door: the second ask still comes '
          '(the latch cleared on abort)',
          app.igm.is_exit_confirmation_shown())
    yr = app.igm.exit_message.yes_rect
    click_at(app, yr[0] + yr[2] / 2, yr[1] + yr[3] / 2)
    for _ in range(int(6.0 / DT)):
        step(app)
        if app.viewer.world.game.ending:
            break
    check('exit door: YES walks through and ends the level',
          app.viewer.world.game.ending)

    # -- the authored-off desktop buttons stay hidden (the port's
    # Entry-scene restore_authored switch) ---------------------------------
    app = fresh_app()
    m = app.menu
    if m.intro is not None and m.intro.enabled:
        app.tick(DT, events=(False, True, False, False))
    click(app, widget(m, 'MenuButtonOptions'))
    step(app)
    check('options: the authored-off Back/Lang stay hidden',
          widget(m, 'MenuButtonBack') is None
          and widget(m, 'MenuButtonLang') is None
          and widget(m, 'MenuButtonOk') is not None
          and widget(m, 'MenuButtonReset') is not None)
    click(app, widget(m, 'MenuButtonOk'))

    # -- the language reload (the mobile path: the flag combo box) ---------
    combo = m.combo
    check('lang: the combo box binds', combo is not None)
    sx, sy, num = combo._layout()
    cw, ch = combo._flag_size(combo.selected[combo.current])
    app._mouse = (num * 0.9 * sx + cw * sx / 2, ch * sy / 2)
    app.tick(DT, events=(False, True, False, False))
    app.draw_menu(DT)
    check('lang: the head flag drops the list', combo.dropped)
    for _ in range(30):                   # the 20-frame slide-in
        app.tick(DT, events=(False, False, False, False))
        app.draw_menu(DT)
        if combo.counter >= 10.0:
            break
    idx = combo.types.index('NEW_LANG_RU')
    fw, fh = combo._flag_size(combo.unselected[idx])
    y = (fh * (idx + 1) + idx + 0.5) * (combo.counter / 10.0)
    app._mouse = (num * 0.9 * sx + fw * sx / 2, y * sy + fh * sy / 2)
    app.tick(DT, events=(False, True, False, False))
    app.draw_menu(DT)
    check('lang: the RU flag reloads Entry with the pref written',
          m.reload_requested and app.prefs.get_int('Language', -1) == 8)
    step(app, 2)
    m = app.menu
    check('lang: the reloaded Entry speaks the language',
          m.settings.language == 8 and m.loc('L3T') != ''
          and m.combo is not None and m.combo.current ==
          m.combo.types.index('NEW_LANG_RU'))

    print()
    print('ALL OK' if _ok else 'FAILURES')
    return 0 if _ok else 1


if __name__ == '__main__':
    sys.exit(main())

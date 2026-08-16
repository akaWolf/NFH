"""The tutorial layer — LevelScript / LevelScriptAction (the arrows, signs
and director message boxes of the three Intro scenes and the two Season-2
tutorial levels) and the four TutorialScriptCamera* scene scripts, driven
by the exported `hud` sections.

The LevelScript GameObject ships inactive; IntroAnimation.StartGame
activates it when GameInfo.ShowTutorialTextAfterIntro is set
(IntroAnimation.cs:305-307). Each action arms one completion signal
(LevelScriptAction.Initialize): an Item's use — or its look-at
(CompleteOnLookAt) — a Door pass, a Zone entry, or Woody reaching an
x-location within Threshold (Woody.Update, Woody.cs:288-291). The world
calls the hooks from the same places the original raises them.
"""
from gui import adjust_rect, font_size

from menu import GUI_DEPTH


class DirectorFaces:
    """DirectorAnimation.DrawFaces (DirectorAnimation.cs:29-59): the
    ping-pong face strip that stops on face 1 after
    NumberOfDirectorAnimationLoops loops; Complete re-arms it
    (StartDirectorAnimation, LevelScript.cs:155)"""

    def __init__(self, d, W, H):
        self.faces = [(t or {}).get('texture')
                      for t in (d.get('DirectorFaces') or [])]
        self.rect = adjust_rect(d.get('DirectorRect'), W, H)
        self.interval = float(d.get('DirectorFaceInterval') or 0.25)
        self.loops = int(d.get('NumberOfDirectorAnimationLoops') or 2)
        self.index = 0
        self.increment = 1
        self.start_time = 0.0
        self.clock = 0.0                  # Time.realtimeSinceStartup
        self.loop_cont = 1                # LoopContAux
        self.animating = True             # StartDirectorAnimation

    def restart(self):
        self.index = 1
        self.increment = 1
        self.start_time = self.clock

    def tick(self, dt):
        self.clock += dt

    def draw(self, g):
        if self.animating and self.clock - self.start_time > self.interval:
            self.start_time = self.clock
            self.index += self.increment
            if self.index == len(self.faces) - 1 or self.index == 0:
                self.increment = -self.increment
                if self.increment > 0 and self.loop_cont == self.loops:
                    self.animating = False
                    self.loop_cont = 1
                elif self.increment > 0:
                    self.loop_cont += 1
        if not self.faces:
            return
        i = 1 if not self.animating else self.index
        i = max(0, min(len(self.faces) - 1, i))
        g.tex(self.faces[i], self.rect)


class HudAnim:
    """HUDAnimation (HUDAnimation.cs): frame indices with per-frame times;
    the same reading hud.HudAnim gives the HUD strips"""

    def __init__(self, d):
        d = d or {}
        self.indices = list(d.get('Indices') or [])
        self.times = list(d.get('Times') or [])
        self.looping = bool(d.get('Looping'))
        self.idx = 0
        self.t = 0.0
        self.finished = True

    def restart(self):
        if not self.indices:
            return
        self.idx = 0
        self.t = self.times[0]
        self.finished = False

    @property
    def frame(self):
        if not self.indices:
            return 0
        return self.indices[min(self.idx, len(self.indices) - 1)]

    def update(self, dt):
        if self.finished or not self.indices:
            return
        self.t -= dt
        if self.t > 0.0:
            return
        self.idx += 1
        if self.idx >= len(self.indices):
            if self.looping:
                self.idx = 0
            else:
                self.idx = len(self.indices) - 1
                self.finished = True
                return
        self.t += self.times[self.idx]


class Tutorial:
    """LevelScript over the exported data; `world.level_script` points here
    while the scene runs, and the world's signal sites call the on_*
    hooks. `viewer` provides the camera for the world-anchored arrows."""

    def __init__(self, d, W, H, loc, viewer, director=None):
        self.d = d
        self.W, self.H = W, H
        self.loc = loc
        self.viewer = viewer
        self.world = viewer.world
        self.level = viewer.level
        self.active = False               # the GameObject ships inactive
        self.arrow = [(t or {}).get('texture') for t in (d.get('Arrow') or [])]
        self.arrow_right = [(t or {}).get('texture')
                            for t in (d.get('ArrowRight') or [])]
        self.sign = [(t or {}).get('texture') for t in (d.get('Sign') or [])]
        self.arrow_anim = HudAnim(d.get('ArrowAnim'))
        self.arrow_right_anim = HudAnim(d.get('ArrowRightAnim'))
        self.sign_anim = HudAnim(d.get('SignAnim'))
        self.message_background = (d.get('MessageBackground') or {}).get('texture')
        self.message_background_small = (d.get('MessageBackgroundSmall') or {}).get('texture')
        self.message_rect = adjust_rect(d.get('MessageRect'), W, H)
        self.description_rect = adjust_rect(d.get('DescriptionRect'), W, H)
        self.description_rect_small = adjust_rect(d.get('DescriptionRectSmall'), W, H)
        self.message_style = d.get('MessageStyle') or {}
        # Start (cs:63): MessageStyle.fontSize = CalculateFontSize(1)
        self.font = int(font_size(W, H) - 1)
        self.depth = GUI_DEPTH.get(d.get('depth') or 'BackHUD', 12)
        self.actions = d.get('Actions') or []
        self.action_index = 0
        self.director = director          # the LevelScript GO's own faces
        self._alt = {}                    # UseAlternateDescription per action
        self.on_complete = None           # OnCompleteCurrentAction event
        self.camera_script = None

    # -- lifecycle ---------------------------------------------------------
    def activate(self):
        """SetActive(true): Start runs — the first action arms, the
        director restarts (LevelScript.cs:60-73); OnEnable raises
        GameInfo.IsTutorialEnabled"""
        if self.active:
            return
        self.active = True
        self.action_index = 0
        if self.actions:
            self._initialize(self.current)
        if self.director is not None:
            self.director.restart()

    def deactivate(self):
        self.active = False

    @property
    def current(self):
        if not self.active or self.action_index >= len(self.actions):
            return None
        return self.actions[self.action_index]

    # -- LevelScriptAction.Initialize (cs:76-116) --------------------------
    def _initialize(self, a):
        a['Completed'] = False
        self._alt[id(a)] = False
        if a.get('DrawArrow'):
            self.arrow_anim.restart()
        if a.get('DrawArrowRight'):
            self.arrow_right_anim.restart()
        if a.get('DrawSign'):
            self.sign_anim.restart()

    @staticmethod
    def _pid(ref):
        return ref.get('path') if isinstance(ref, dict) else None

    def _signal_kind(self, a):
        """Initialize's arm order: Item, then Door, then Zone, then the
        location (LevelScriptAction.cs:80-105)"""
        if self._pid(a.get('Item')) is not None:
            return 'item'
        if self._pid(a.get('Door')) is not None:
            return 'door'
        if self._pid(a.get('Zone')) is not None:
            return 'zone'
        return 'location'

    # -- the signal hooks the world calls ----------------------------------
    def on_item_used(self, item):
        """Item's Used=true tail (Item.cs:1894-1897)"""
        a = self.current
        if a is not None and self._signal_kind(a) == 'item' \
                and not a.get('CompleteOnLookAt') \
                and self._pid(a.get('Item')) == item.pid:
            self.complete_current_action()

    def on_item_lookat(self, item):
        """CheckDescriptionTooltip's SignalOnLookAt arm (Item.cs:1817-1819)"""
        a = self.current
        if a is not None and self._signal_kind(a) == 'item' \
                and a.get('CompleteOnLookAt') \
                and self._pid(a.get('Item')) == item.pid:
            self.complete_current_action()

    def on_woody_door_entered(self, door):
        """Woody.OnDoorEnterAnimationFinished (Woody.cs:477-480)"""
        a = self.current
        if a is not None and self._signal_kind(a) == 'door' \
                and self._pid(a.get('Door')) == door.pid:
            self.complete_current_action()

    def on_woody_zone_entered(self, zone_pid):
        """Pawn.ChangeZone's SignalScriptZone arm (Pawn.cs:1592-1595)"""
        a = self.current
        if a is not None and self._signal_kind(a) == 'zone' \
                and self._pid(a.get('Zone')) == zone_pid:
            self.complete_current_action()

    def on_trick_done(self):
        """Rottweiler's tricked-use tail (Rottweiler.cs:789-792)"""
        a = self.current
        if a is not None and a.get('UseAlternateDescriptionOnTrick'):
            self._alt[id(a)] = True

    def on_rottweiler_action(self):
        """RoutineActionUse.OnUseEnded (RoutineActionUse.cs:405-407)"""
        a = self.current
        if a is not None and a.get('UseAlternateDescriptionOnRottweilerAction'):
            self._alt[id(a)] = True

    def tick(self, dt):
        """Woody.Update's location signal (Woody.cs:288-291): the x
        distance alone against Threshold"""
        if not self.active:
            return
        if self.director is not None:
            self.director.tick(dt)
        a = self.current
        w = self.world.woody
        if a is not None and self._signal_kind(a) == 'location' \
                and w is not None:
            loc = a.get('Location') or {}
            if abs(w.sprite.x - (loc.get('x') or 0.0)) \
                    < (a.get('Threshold') or 0.03):
                self.complete_current_action()

    # -- LevelScript.CompleteCurrentAction (cs:148-166) --------------------
    def complete_current_action(self):
        a = self.current
        if a is None:
            return
        if self.on_complete is not None:
            self.on_complete()            # the OnCompleteCurrentAction event
        self._complete(a)
        if self.director is not None:
            self.director.animating = True
        self.action_index += 1
        if self.action_index < len(self.actions):
            self._initialize(self.current)
        else:
            self.world.game.force_win()   # WinGame -> ForceWinGame

    def _stop_woody(self):
        """LevelScript.StopWoody (cs:183-188): StopMovement +
        ContinueMovement leave the move inert, SwitchToStandAnimation"""
        w = self.world.woody
        if w is None:
            return
        w.steps = []
        w._step = None
        w.state = w.IDLE
        w.movement_paused = False
        w._stand()

    def _complete(self, a):
        """LevelScriptAction.Complete (cs:118-166)"""
        a['Completed'] = True
        kind = self._signal_kind(a)
        if kind in ('door', 'location'):
            self._stop_woody()
        for ref in a.get('DoorsToUnlock') or []:
            d = self.level.door_by_pid(self._pid(ref))
            if d is not None:
                self.world.unlock_door(d)
        for ref in a.get('ItemsToUnlock') or []:
            it = self.level.items.get(self._pid(ref))
            if it is not None:
                it.locked = False         # + SetMouseOverNotLocked: the
                                          # cursor icon resolves per frame
        for ref in a.get('ItemsToLock') or []:
            it = self.level.items.get(self._pid(ref))
            if it is not None:
                it.locked = True
        for ref in a.get('DoorsToLock') or []:
            d = self.level.door_by_pid(self._pid(ref))
            if d is not None:
                d.locked = True
        if a.get('UnfreezeNeighbor'):
            r = self._rott_routine()
            if r is not None:
                r.unfreeze(start_next=True,
                           advance=bool(a.get('ForceAdvanceAction')),
                           idx_after=int(a.get('ActionIndexAfterForceAdvanceAction') or 0))
        self._alt[id(a)] = False

    def _rott_routine(self):
        rott = self.world.pawns.get('Rottweiler')
        return next((r for r in self.world.routines if r.pawn is rott), None)

    def get_description(self, a):
        """GetDescription (cs:168-176): the mobile strings"""
        key = a.get('AlternateDescriptionMobile') \
            if self._alt.get(id(a)) else a.get('DescriptionMobile')
        return self.loc(key or '').replace('\\n', '\n')

    # -- LevelScript.OnGUI (cs:85-146) -------------------------------------
    def draw(self, g, dt, menu_open=False):
        a = self.current
        if a is None or menu_open:
            return
        off = a.get('AnimOffset') or {}
        loc = a.get('Location') or {}
        it = self.level.items.get(self._pid(a.get('Item'))) \
            if self._pid(a.get('Item')) is not None else None
        ax = (it.x if it is not None else (loc.get('x') or 0.0)) \
            + (off.get('x') or 0.0)
        ay = (it.y if it is not None else (loc.get('y') or 0.0)) \
            + (off.get('y') or 0.0)
        sx, sy = self.viewer.cam.world_to_screen(ax, ay, self.W, self.H)
        if a.get('DrawArrow') and self.arrow:
            s = self.H * 64 // 768
            self.arrow_anim.update(dt)
            g.tex(self.arrow[self.arrow_anim.frame], (sx, sy, s, s))
        if a.get('DrawArrowRight') and self.arrow_right:
            s = self.H * 64 // 768
            self.arrow_right_anim.update(dt)
            g.tex(self.arrow_right[self.arrow_right_anim.frame],
                  (sx, sy, s, s))
        if a.get('DrawSign') and self.sign:
            w = self.W * 128 // 1024
            h = self.H * 64 // 768
            self.sign_anim.update(dt)
            g.tex(self.sign[self.sign_anim.frame], (sx, sy, w, h))
        if not a.get('SmallDescription'):
            g.tex(self.message_background, self.message_rect)
            g.label(self.description_rect, self.get_description(a),
                    self.message_style, self.font)
        else:
            g.tex(self.message_background_small, self.message_rect)
            g.label(self.description_rect_small, self.get_description(a),
                    self.message_style, self.font)
        if self.director is not None:
            self.director.draw(g)


# ---------------------------------------------------------------------------
# the scene camera scripts

class CameraScriptBase:
    """the shared plumbing: the pawns, the snap helpers, the overlay"""

    def __init__(self, d, W, H, viewer, tutorial):
        self.d = d
        self.W, self.H = W, H
        self.viewer = viewer
        self.world = viewer.world
        self.level = viewer.level
        self.tutorial = tutorial
        self.overlay = (d.get('CameraOverlay') or {}).get('texture') \
            if isinstance(d.get('CameraOverlay'), dict) else None
        self.overlay_rect = adjust_rect(d.get('CameraOverlayRect'), W, H)
        self.state = 'Start'
        self.active = True

    @staticmethod
    def _pid(ref):
        return ref.get('path') if isinstance(ref, dict) else None

    def item(self, key):
        return self.level.items.get(self._pid(self.d.get(key)))

    def door(self, key):
        return self.level.door_by_pid(self._pid(self.d.get(key)))

    @property
    def rott(self):
        return self.world.pawns.get('Rottweiler')

    @property
    def rott_routine(self):
        rott = self.rott
        return next((r for r in self.world.routines if r.pawn is rott), None)

    @property
    def mother_routine(self):
        m = self.world.pawns.get('Mother')
        return next((r for r in self.world.routines if r.pawn is m), None)

    def rott_moving(self):
        """Rottweiler.Velocity.magnitude > 0"""
        r = self.rott
        return r is not None and r.state == r.WALK

    def snap_rott(self):
        """GameCamera.SnapToRottweilerImmediate"""
        r = self.rott
        if r is not None:
            self.viewer.cam.x = r.sprite.x
            self.viewer.cam.y = r.sprite.y
            self.viewer._clamp_camera()

    def snap_woody(self):
        """GameCamera.SnapToWoodyImmediate"""
        self.world.snap_camera()

    def _ended(self):
        g = self.world.game
        return g.ending or g.ended

    def draw(self, g):
        pass


class TutorialCamera102(CameraScriptBase):
    """TutorialScriptCamera.cs (Intro102): the camera rides the neighbour
    through the MumSmeared and Marble tricks, with the film overlay"""

    def tick(self, dt):
        if self.state != 'End' and self._ended():
            self.state = 'End'
        mum, marble = self.item('MumSmeared'), self.item('Marble')
        if self.state == 'Start':
            if self.rott_moving():
                self.state = 'MumSmearedTrick'
        elif self.state == 'MumSmearedTrick':
            if mum is not None and not mum.is_tricked(self.level.items):
                self.state = 'Hold'
        elif self.state == 'Hold':
            r = self.rott
            if r is not None and r.is_warping and marble is not None \
                    and marble.is_tricked(self.level.items):
                self.state = 'MarbleTrick'
        # LateUpdate (cs:66-84)
        if self.state == 'MumSmearedTrick':
            r = self.rott
            if mum is not None and mum.is_tricked(self.level.items) \
                    and r is not None and not r.is_warping:
                self.snap_rott()
        elif self.state == 'MarbleTrick':
            if marble is not None and marble.is_tricked(self.level.items):
                self.snap_rott()

    def draw(self, g):
        """OnGUI (cs:88-118)"""
        mum, marble = self.item('MumSmeared'), self.item('Marble')
        if self.state == 'MumSmearedTrick':
            if mum is not None and mum.is_tricked(self.level.items):
                g.tex(self.overlay, self.overlay_rect)
        elif self.state == 'MarbleTrick':
            if marble is not None and marble.is_tricked(self.level.items):
                g.tex(self.overlay, self.overlay_rect)


class TutorialCamera103(CameraScriptBase):
    """TutorialScriptCameraIntro3.cs: the dog action under FreezeNeighbour,
    the marble trick after action 3"""

    def __init__(self, d, W, H, viewer, tutorial):
        CameraScriptBase.__init__(self, d, W, H, viewer, tutorial)
        self.only_one_time = False

    def tick(self, dt):
        r = self.rott_routine
        if r is not None and r.freeze_neighbour and not self.only_one_time:
            # the dog action froze the manager: park the camera on Woody
            # (cs:39-44)
            self.snap_woody()
            r.freeze_neighbour = False
            self.only_one_time = True
        if self.state != 'End' and self._ended():
            self.state = 'End'
        marble = self.item('Marble')
        rott = self.rott
        if self.state == 'Start':
            if self.rott_moving():
                self.state = 'Dog'
        elif self.state == 'Dog':
            if r is not None and r.stop_dog_action:
                self.state = 'Hold'
        elif self.state == 'Hold':
            acts = (self.tutorial.actions if self.tutorial else [])
            done3 = len(acts) > 3 and acts[3].get('Completed')
            if marble is not None and marble.is_tricked(self.level.items) \
                    and done3 and rott is not None \
                    and rott.anim.anim is not None \
                    and rott.anim.anim.name == 'Stand_Left':
                if r is not None:
                    r.freeze_neighbour = False
                    r.unfreeze(start_next=True, advance=True)
                self.state = 'MarbleTrick'
        # LateUpdate (cs:81-99)
        if self.state == 'Dog':
            if r is not None and not r.stop_dog_action and rott is not None \
                    and not rott.is_warping:
                self.snap_rott()
        elif self.state == 'MarbleTrick':
            if marble is not None and marble.is_tricked(self.level.items) \
                    and rott is not None and not rott.is_warping:
                self.snap_rott()

    def draw(self, g):
        """OnGUI (cs:101-129)"""
        r = self.rott_routine
        marble = self.item('Marble')
        if self.state == 'Dog':
            if r is not None and not r.stop_dog_action:
                g.tex(self.overlay, self.overlay_rect)
        elif self.state == 'MarbleTrick':
            if marble is not None and marble.is_tricked(self.level.items):
                g.tex(self.overlay, self.overlay_rect)


def _blank_move_action(move_zone, freeze=True, move_x=1.0):
    """TutorialScriptCameraNFH2.AddAction's `new RoutineActionUse()` with
    the fields it sets (cs:210-236): a MoveOnly step into the previous
    item's zone that freezes the manager on completion"""
    return {'item': None, 'duration': 0.0, 'max_distance': 0.0,
            'hide_object': False, 'hide_owner': False, 'move_only': True,
            'move_x': move_x, 'move_zone': move_zone, 'mutex': False,
            'postpone_alarm': False, 'postpone_alarm_during_use_only': False,
            'mutex_anim': None, 'urgent': False,
            'freeze_after_completion': freeze,
            'doors_to_unlock': [], 'items_to_unlock': [],
            'items_to_unlock_tricked': [], 'alert_next': False,
            'is_toilet': False, 'cake': False, 'give_fifi': False,
            'remove_fifi': False, 'give_skates': False,
            'remove_skates': False, 'remove_action_after_use': False}


class TutorialCameraNFH2(CameraScriptBase):
    """TutorialScriptCameraNFH2.cs (Level201): the staged neighbour walk
    with synthetic MoveOnly actions, the stair/transition locks, and the
    35 s shutdown after the last message"""

    def __init__(self, d, W, H, viewer, tutorial):
        CameraScriptBase.__init__(self, d, W, H, viewer, tutorial)
        self.one_time_invoke = False
        self._end_timer = None
        # Start (cs:57-62)
        up, down = self.door('UpTransition'), self.door('DownTransition')
        if up is not None:
            up.locked = False
        if down is not None:
            down.locked = True
        if tutorial is not None:
            tutorial.on_complete = self._unlock_transitions

    def _set_locks(self, left=None, right=None, up=None, down=None):
        for key, val in (('LeftSideStair', left), ('RightSideStair', right),
                         ('UpTransition', up), ('DownTransition', down)):
            if val is None:
                continue
            door = self.door(key)
            if door is not None:
                door.locked = val

    def _unlock_transitions(self):
        """OnCompleteCurrentAction (cs:302-317)"""
        if self.state in ('Hold2', 'TableTrick', 'LinkedTrick'):
            up = self.door('UpTransition')
            if up is not None:
                up.locked = False

    def add_action(self, index):
        """AddAction (cs:210-236)"""
        r = self.rott_routine
        if r is None:
            return
        prev = r.actions[index - 1]
        prev_item = self.level.items.get(prev['item']) if prev['item'] else None
        zone = prev_item.zone if prev_item is not None else None
        r.actions.insert(index, _blank_move_action(zone))

    def remove_action(self, index):
        """RemoveAction (cs:238-249): drop the step, restart at 0"""
        r = self.rott_routine
        if r is None or index >= len(r.actions):
            return
        del r.actions[index]
        r.index = 0

    def tick(self, dt):
        if self._end_timer is not None:
            self._end_timer -= dt
            if self._end_timer <= 0.0:
                self._end_timer = None
                # EndMessageDelay (cs:287-291)
                if self.tutorial is not None:
                    self.tutorial.deactivate()
                self.active = False
        if not self.active:
            return
        if self.state != 'End' and self._ended():
            self.state = 'End'
        wp = self.item('WaterPuddle')
        buffet = self.item('Buffet')
        rail = self.item('DeckRail')
        woody = self.world.woody
        r = self.rott_routine
        ls = self.tutorial
        if self.state == 'Start':
            self._set_locks(left=True, right=True)
            if self.rott_moving():
                if wp is not None:
                    wp.final_normal = (-0.6, wp.final_normal[1])
                if woody is not None:
                    woody.frozen = True             # Woody.Freeze
                self.state = 'Moving'
        elif self.state == 'Moving':
            if r is not None and r.index == 5:
                if woody is not None:
                    woody.frozen = False
                self.snap_woody()
                if ls is not None:
                    ls.complete_current_action()
                self.state = 'Hold'
        elif self.state == 'Hold':
            self._set_locks(left=True, right=False, up=True)
            if wp is not None and wp.tricked:
                self.remove_action(5)
                wp.rott_prime_exit_delta = (0.0, wp.rott_prime_exit_delta[1])
                if r is not None:
                    r.index = 1
                self.state = 'Hold2'
        elif self.state == 'Hold2':
            if wp is not None and wp.tricked and self.rott_moving() \
                    and ls is not None and ls.action_index == 5:
                self.state = 'Moving2'
        elif self.state == 'Moving2':
            self._set_locks(left=True, right=True)
            if self.rott_moving() and r is not None and r.index == 2:
                if woody is not None:
                    woody.frozen = True
                self.add_action(5)
                self.state = 'Hold3'
        elif self.state == 'Hold3':
            if self.rott_moving() and r is not None and r.index == 3:
                if wp is not None:
                    wp.primed = False               # the raw field write
                self.state = 'Hold4'
        elif self.state == 'Hold4':
            if r is not None and r.index == 5:
                r.index = -1
                if woody is not None:
                    woody.frozen = False
                self.snap_woody()
                if ls is not None:
                    ls.complete_current_action()
                self.state = 'TableTrick'
        elif self.state == 'TableTrick':
            self._set_locks(left=False, right=True, up=True, down=False)
            if buffet is not None and buffet.tricked and self.rott_moving() \
                    and ls is not None and ls.action_index == 10:
                self.remove_action(5)
                if woody is not None:
                    woody.frozen = True
                self.add_action(2)
                self.state = 'TableTrick2'
        elif self.state == 'TableTrick2':
            self._set_locks(left=False, right=False, up=False)
            if r is not None and r.index == 2:
                if woody is not None:
                    woody.frozen = False
                if wp is not None:
                    wp.use_once = False
                    wp.primed = True
                self.snap_woody()
                if ls is not None:
                    ls.complete_current_action()
                self.state = 'LinkedTrick'
        elif self.state == 'LinkedTrick':
            self._set_locks(left=True, right=False, up=True)
            if wp is not None and wp.tricked and rail is not None \
                    and rail.tricked and self.rott_moving() \
                    and ls is not None and ls.action_index == 15:
                if woody is not None:
                    woody.frozen = True
                if wp is not None:
                    wp.use_once = True
                self.remove_action(2)
                if r is not None:
                    r.index = -1
                self.state = 'LinkedTrick2'
        elif self.state == 'LinkedTrick2':
            self._set_locks(up=False)
            if r is not None and r.index == 0:
                self.state = 'End1'
        elif self.state == 'End1':
            self._set_locks(left=False, right=False, up=False, down=False)
            if woody is not None:
                woody.frozen = False
            if wp is not None:
                wp.primed = True
                wp.dx, wp.dy = -wp.dx, -wp.dy
                wp.final_normal = (-wp.final_normal[0], wp.final_normal[1])
            if ls is not None:
                ls.complete_current_action()
            self.state = 'End'
        elif self.state == 'End':
            if not self.one_time_invoke:
                self._end_timer = 35.0              # Invoke("EndMessageDelay")
                self.one_time_invoke = True
        # LateUpdate (cs:250-270)
        if self.state in ('Moving', 'Hold3', 'Hold4', 'TableTrick2',
                          'LinkedTrick2'):
            self.snap_rott()


class TutorialCameraNFH2206(CameraScriptBase):
    """TutorialScriptCameraNFH2206.cs (Level206): the pillow-throw lesson
    with the Mother's action surgery"""

    def __init__(self, d, W, H, viewer, tutorial):
        CameraScriptBase.__init__(self, d, W, H, viewer, tutorial)
        self.one_time = False
        self._mother_call_timer = None
        r = self.rott_routine
        if r is not None:
            r.add_in_game_actions(4)                # Start (cs:59)
        if tutorial is not None:
            tutorial.on_complete = self._unlock_transitions

    def _set_locks(self, left=None, right=None, up=None, down=None):
        for key, val in (('LeftSideStair', left), ('RightSideStair', right),
                         ('UpTransition', up), ('DownTransition', down)):
            if val is None:
                continue
            door = self.door(key)
            if door is not None:
                door.locked = val

    def _unlock_transitions(self):
        """OnCompleteCurrentAction (cs:225-235)"""
        if self.state == 'Hold':
            self._set_locks(up=False, down=False)

    def tick(self, dt):
        if self._mother_call_timer is not None:
            self._mother_call_timer -= dt
            if self._mother_call_timer <= 0.0:
                self._mother_call_timer = None
                # WaitForMotherCall (cs:172-177)
                r = self.rott_routine
                if r is not None:
                    r.unfreeze(start_next=True, advance=True, idx_after=1)
                self.state = 'Hold2'
        if not self.active:
            return
        if self.state != 'End' and self._ended():
            self.state = 'End'
        woody = self.world.woody
        r = self.rott_routine
        m = self.mother_routine
        ls = self.tutorial
        deck = self.item('DeckChair')
        throw = self.item('DeckChairThrow')
        if self.state == 'Start':
            if woody is not None:
                woody.frozen = True
            self.state = 'Moving'
        elif self.state == 'Moving':
            if r is not None and r.index == 4:
                if woody is not None:
                    woody.frozen = False
                self.snap_woody()
                if ls is not None:
                    ls.complete_current_action()
                self.state = 'Hold'
        elif self.state == 'Hold':
            self._set_locks(up=True, down=True)
            if ls is not None and ls.action_index == 4:
                if woody is not None:
                    woody.frozen = True
                if throw is not None:
                    throw.use_anim['Mother'] = ['MotherGetUpPillow',
                                                'MotherHoldPillow',
                                                'MotherThrowPillow']
                if m is not None:
                    m.index = 0
                    m._pending = 'start'            # StartAction(Actions[0])
                self.state = 'Moving2'
        elif self.state == 'Moving2':
            self._set_locks(up=False, down=False)
            if m is not None and m.index == 0:
                self.state = 'Moving3'
        elif self.state == 'Moving3':
            if m is not None and m.index == 1 \
                    and self._mother_call_timer is None:
                self._mother_call_timer = 2.0       # Invoke WaitForMotherCall
        elif self.state == 'Hold2':
            if r is not None and r.index == 2 and len(r.actions) > 2 \
                    and r.actions[2]['item'] is not None and not self.one_time:
                it2 = self.level.items.get(r.actions[2]['item'])
                if it2 is not None and it2.name == 'Pillows' and it2.tricked:
                    r.remove_action_by_index(4)
                    self.one_time = True
                    it2.tricked = False
                    if len(r.actions) > 3:
                        # ContinueToNextAfterFinished on a routine action
                        # only matters on the urgent completion arm
                        # (ActionManager.cs:530-538); the port keeps the
                        # write for the record, no reader consumes it here
                        r.actions[3]['continue_to_next'] = False
                    self.rott.deck_chair_aux = True
                    ma = self.mother_routine
                    if ma is not None and ma.actions:
                        it0 = self.level.items.get(ma.actions[0]['item']) \
                            if ma.actions[0]['item'] else None
                        if it0 is not None:
                            it0.use_anim['Mother'] = \
                                ['MotherStandDownSingle'] * 8
                        if len(ma.actions) > 3:
                            it3 = self.level.items.get(ma.actions[3]['item']) \
                                if ma.actions[3]['item'] else None
                            if it3 is not None:
                                it3.use_anim['Mother'] = ['MotherSitPillow',
                                                          'MotherLook']
            if r is not None and r.index == 4:
                self.state = 'End1'
        elif self.state == 'End1':
            self._set_locks(left=False, right=False, up=False, down=False)
            if m is not None:
                m.index = 3
                m._pending = 'start'
                m.loop_from_selected = True
            # ForceMotherSleep (cs:220-223)
            mp = self.world.pawns.get('Mother')
            if mp is not None and deck is not None:
                seq = [a for a in (deck.mother_second_use or [])
                       if mp.anim.has(a)]
                if seq:
                    mp.anim.play_sequence(seq)
            if woody is not None:
                woody.frozen = False
            if ls is not None:
                ls.deactivate()
            self.state = 'End'
        # LateUpdate (cs:179-198)
        if self.state in ('Moving', 'Moving2', 'Moving3', 'Hold2'):
            self.snap_rott()
        elif self.state == 'End1':
            self.snap_woody()


CAMERA_CLASSES = {'TutorialScriptCamera': TutorialCamera102,
                  'TutorialScriptCameraIntro3': TutorialCamera103,
                  'TutorialScriptCameraNFH2': TutorialCameraNFH2,
                  'TutorialScriptCameraNFH2206': TutorialCameraNFH2206}


def build(scene_data, W, H, loc, viewer):
    """the scene's tutorial layer, or None: the LevelScript with its own
    DirectorAnimation (the one on the LevelScript GameObject), plus the
    matching camera script"""
    ls = scene_data.find('LevelScript')
    if not ls:
        return None, None
    go, d = ls[0]
    director = None
    for dgo, dd in scene_data.find('DirectorAnimation'):
        if dgo == go:
            director = DirectorFaces(dd, W, H)
            break
    tut = Tutorial(d, W, H, loc, viewer, director=director)
    cam = None
    for typ, cls in CAMERA_CLASSES.items():
        found = scene_data.find(typ)
        if found:
            cam = cls(found[0][1], W, H, viewer, tut)
            tut.camera_script = cam
            break
    return tut, cam

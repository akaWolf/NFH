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
        """Pawn.ChangeZone's SignalScriptZone arm (Pawn.cs:1592-1595):
        `Zone == SignalScriptZone` compares Zone components; the action's
        reference is the component's path and the pawn's zone carries the
        GameObject's, so the reference resolves through the level's
        component map first (Level201's actions 4 / 9 / 14 never completed
        on the raw ids)"""
        a = self.current
        if a is None or self._signal_kind(a) != 'zone':
            return
        z = self.level.zone_by_component(self._pid(a.get('Zone')))
        if z is not None and z.pid == zone_pid:
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

    def _pc_descriptions(self):
        """the overlay's PCDescriptions on the level's LevelScript (the
        profile patches the level's objects, pcprofile.apply_overlay)"""
        for o in self.level.objs.values():
            if o.get('type') == 'LevelScript':
                return (o.get('data') or {}).get('PCDescriptions') or {}
        return {}

    def _rott_routine(self):
        rott = self.world.pawns.get('Rottweiler')
        return next((r for r in self.world.routines if r.pawn is rott), None)

    def get_description(self, a):
        """GetDescription (cs:168-176): the mobile strings — under the PC
        profile the PC's own director message (PCDescriptions, the PC
        tutorial's strings.xml text for the action's PC-build key: tools/
        pcref/pc_tutorial_s1.py), else the PC-build key's text"""
        alt = self._alt.get(id(a))
        import pcprofile
        if pcprofile.is_pc():
            key = a.get('AlternateDescription') if alt else a.get('Description')
            pc = self._pc_descriptions().get(key or '')
            if pc:
                return pc
            if key:
                return self.loc(key).replace('\\n', '\n')
        key = a.get('AlternateDescriptionMobile') if alt else a.get('DescriptionMobile')
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
                    woody.freeze()             # Woody.Freeze
                self.state = 'Moving'
        elif self.state == 'Moving':
            if r is not None and r.index == 5:
                if woody is not None:
                    woody.unfreeze()
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
                    woody.freeze()
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
                    woody.unfreeze()
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
                    woody.freeze()
                self.add_action(2)
                self.state = 'TableTrick2'
        elif self.state == 'TableTrick2':
            self._set_locks(left=False, right=False, up=False)
            if r is not None and r.index == 2:
                if woody is not None:
                    woody.unfreeze()
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
                    woody.freeze()
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
                woody.unfreeze()
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
                woody.freeze()
            self.state = 'Moving'
        elif self.state == 'Moving':
            if r is not None and r.index == 4:
                if woody is not None:
                    woody.unfreeze()
                self.snap_woody()
                if ls is not None:
                    ls.complete_current_action()
                self.state = 'Hold'
        elif self.state == 'Hold':
            self._set_locks(up=True, down=True)
            if ls is not None and ls.action_index == 4:
                if woody is not None:
                    woody.freeze()
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
                woody.unfreeze()
            if ls is not None:
                ls.deactivate()
            self.state = 'End'
        # LateUpdate (cs:179-198)
        if self.state in ('Moving', 'Moving2', 'Moving3', 'Hold2'):
            self.snap_rott()
        elif self.state == 'End1':
            self.snap_woody()


def _port_x(zone, pcx):
    """a PC x on a zone's room floor line as the mobile x — world.pc_room_x
    the other way (Zone.pc_room's path1-path2 against the zone's walking
    limits)"""
    pr = zone.pc_room
    w = (pr['x2'] - pr['x1']) or 1.0
    return zone.left + (pcx - pr['x1']) * (zone.right - zone.left) / w


class TutorialPC201(Tutorial):
    """The PC's own 201 tutorial, in place of the mobile's LevelScript and
    TutorialScriptCameraNFH2 under the PC profile (docs/PC_FIDELITY.md
    "201's tutorial"). GameLogic.dll runs it as two scripts: the invisible
    `aux` actor's director — its steps 0x1002818c ... 0x10026640, run once
    a level tick until one stores the next (the `_d_*` methods here, named
    by address) — and the neighbour's (0x1002aac8 ...). The director shows
    a message (fcn.100101f3), puts the marker arrow on objects
    (fcn.10042077), shows and hides the waypoint signs and the closed
    objects' open twins (fcn.10043d66 / fcn.10042b9e, the switches
    fcn.1000f6c7) and polls Woody's arrival at a sign (fcn.1000e2bd: y equal
    and |dx| within the dword at 0x100cc814), his inventory (fcn.10049cec),
    his room (fcn.1000fc33, fcn.10040a7d), the objects present
    (fcn.1000ec67) and the level's mini-game (the level's slot 0x50); the
    two scripts hand each other the `tutorial` behaviour (fcn.1004000a) and
    wait on it (fcn.10013269). The neighbour's script is carried on the
    mobile routine — its stations are the same objects — by setting its
    action list per phase (`_nb_*`) and parking him where the PC's waits
    stand; after the linked crash his script puts him at the entry, runs
    him to the shout spot, wheezes and shouts (pc_trick_hook). The data is
    the overlay's PCTutorial (tools/pcref/pc_tutorial201.py). The mobile's
    door and item locks are not the PC's: the doors stay open, and an
    object shown late on the PC (the chest, the puddle, the vanity bag, the
    spaghetti pot) is the mobile item locked until the director shows it."""

    def __init__(self, d, W, H, loc, viewer, director, pc, cam):
        Tutorial.__init__(self, d, W, H, loc, viewer, director=director)
        self.pc = pc
        self.cam_d = cam or {}
        self.actions = []                 # no LevelScriptActions: current is None
        self.step = '818c'
        self.text = None                  # the message box's text
        self.msg = None                   # its code name
        self.shown = []                   # the messages in the order shown
        self.markers = set()              # the items under the marker arrow
        self.signs = set()                # the waypoints shown
        self.modal = False                # the welcome box (fcn.1001029b)
        self.latch_tutorial = False       # the director's `tutorial` latch
        self.latch_run = False            # its `run` latch (the toolbox's failed)
        self.follow = False               # the neighbour camera (0x1000f51a/0x1000ebbf)
        self.nb_phase = 'start'
        self._nb_sent = False
        self._nb_back = False             # back from the lost game's run
        self._rail_repair = None          # the open rail's repair on his next visit
        self._rail_seen = False
        self._rail_shut = False
        by_name = {z.name: z for z in self.level.zones}
        self.zones = by_name
        items = {it.name: it for it in self.level.items.values()}
        self.items = items
        self.wp = items.get('WaterPuddle')
        self.rail = items.get('DeckRail')
        self.buffet = items.get('Buffet')
        r = self.rott_routine
        self.base = list(r.actions) if r is not None else []
        # the mobile arrows' offsets over the same objects (LevelScript
        # actions' AnimOffset), the sign's over the mobile waypoint
        self.arrow_off = {}
        self.sign_off = (0.0, 0.0)
        for a in d.get('Actions') or []:
            off = a.get('AnimOffset') or {}
            ref = self._pid(a.get('Item'))
            it = self.level.items.get(ref) if ref is not None else None
            if it is not None and (a.get('DrawArrow') or a.get('DrawArrowRight')):
                self.arrow_off.setdefault(it.name, (off.get('x') or 0.0, off.get('y') or 0.0))
            if a.get('DrawSign'):
                self.sign_off = (off.get('x') or 0.0, off.get('y') or 0.0)
        self._setup()

    # -- the level as the PC starts it ---------------------------------------
    def _setup(self):
        """the PC's start: level.xml's woody in bottomleft (the entrance —
        the respawn's room is topleft, World._pc_respawn_zone), the
        neighbour at the bridge (the entry's neighbor_entry), the doors
        open, the closed objects' mobile items locked, the others Woody may
        use at once unlocked (the rail, the hat: no closed twin on the PC)"""
        w = self.world
        woody = w.woody
        z, x, _y = self._pc_point(self.pc.get('woody'))
        if woody is not None and z is not None:
            woody.sprite.x, woody.sprite.y = x, woody.floor_y(z)
            woody.zone = z
            woody.pos_snap = True
            self.level.entrance_location = (woody.sprite.x, woody.sprite.y)
        rott = self.rott
        z, x, _y = self._pc_point(self.pc.get('entry'))
        if rott is not None and z is not None:
            rott.sprite.x, rott.sprite.y = x, rott.floor_y(z)
            rott.zone = z
            rott.pos_snap = True
        for key in ('LeftSideStair', 'RightSideStair', 'UpTransition', 'DownTransition'):
            door = self.level.door_by_pid(self._pid(self.cam_d.get(key)))
            if door is not None:
                door.locked = False
        for name, locked in (('SoapChest', True), ('WaterPuddle', True),
                             ('VanityBag', True), ('SpaghettiCar', True),
                             ('DeckRail', False), ('CaptainHat', False)):
            it = self.items.get(name)
            if it is not None:
                it.locked = locked
        if self.wp is not None:
            # the soap chest holds 999 (ship1/objects.xml): the puddle takes
            # soap again after each crash
            self.wp.use_once = False

    def _pc_point(self, rec):
        """[zone, pc x, pc y] -> (zone, mobile x, pc y)"""
        if not rec:
            return None, 0.0, 0.0
        z = self.zones.get(rec[0])
        if z is None or getattr(z, 'pc_room', None) is None:
            return None, 0.0, 0.0
        return z, _port_x(z, rec[1]), rec[2]

    def _item(self, pc_name):
        return self.items.get((self.pc.get('items') or {}).get(pc_name))

    @property
    def rott(self):
        return self.world.pawns.get('Rottweiler')

    @property
    def rott_routine(self):
        rott = self.rott
        return next((r for r in self.world.routines if r.pawn is rott), None)

    # -- the lifecycle -------------------------------------------------------
    def activate(self):
        if self.active:
            return
        self.active = True
        if self.director is not None:
            self.director.restart()

    def dismiss(self):
        """the welcome box's button"""
        self.modal = False

    def tick(self, dt):
        if not self.active:
            return
        if self.director is not None:
            self.director.tick(dt)
        if self.modal:
            return
        getattr(self, '_d_' + self.step)()
        self._nb_tick()
        if self.follow:
            r = self.rott
            if r is not None:
                self.viewer.cam.x, self.viewer.cam.y = r.sprite.x, r.sprite.y
                self.viewer._clamp_camera()

    def _go(self, step):
        self.step = step

    # -- the director's element helpers --------------------------------------
    def _msg(self, name):
        """fcn.100101f3: the message box shows the text"""
        if self.msg == name:
            return
        self.msg = name
        self.text = (self.pc.get('texts') or {}).get(name) if name else None
        if name:
            self.shown.append(name)
        if self.director is not None:
            self.director.animating = True
            self.director.restart()

    def _marker(self, pc_name, on):
        """fcn.10042077: the marker arrow over the object ('ms') or none"""
        it = self._item(pc_name)
        if it is None:
            return
        if on:
            self.markers.add(it.name)
        else:
            self.markers.discard(it.name)

    def _sign(self, name, on):
        if on:
            self.signs.add(name)
        else:
            self.signs.discard(name)

    def _open(self, pc_name):
        """the closed object hidden and its open twin shown (fcn.10042b9e /
        fcn.10043d66, the switch fcn.1000f6c7): Woody may use the item"""
        it = self._item(pc_name)
        if it is not None:
            it.locked = False

    def _at(self, name):
        """fcn.1000e2bd(woody, waypoint): his y the sign's (the floor line)
        and |dx| within at_px"""
        woody = self.world.woody
        z, x, _y = self._pc_point((self.pc.get('waypoints') or {}).get(name))
        if woody is None or z is None or woody.zone is not z:
            return False
        if abs(woody.sprite.y - woody.floor_y(z)) > 0.05:
            return False
        from world import pc_room_x
        return abs(pc_room_x(z, woody.sprite.x) - pc_room_x(z, x)) <= (self.pc.get('at_px') or 0)

    def _moving(self):
        """fcn.10008874: Woody's flag 0x80000, set through his movements
        (fcn.10009489 / fcn.10009889)"""
        woody = self.world.woody
        return woody is not None and woody.state in woody.MOVING

    def _has(self, pc_inv):
        """fcn.10026853 -> fcn.10049cec: the inventory holds the item"""
        typ = (self.pc.get('inventory') or {}).get(pc_inv)
        return typ is not None and self.world.inventory.has(typ)

    def _room(self, pawn):
        """fcn.10040a7d: the actor's room (none inside a pass)"""
        if pawn is None:
            return None
        z = pawn.pc_room()
        return z.name if z is not None else None

    def _in(self, zone_name, pawn):
        """fcn.1000fc33(room, actor)"""
        return self._room(pawn) == zone_name

    def _lower(self, pawn):
        """the lower deck: bottomleft or bottomright (the room compares of
        0x1002791d, 0x1002725b, 0x10026d08)"""
        rooms = self.pc.get('rooms') or {}
        return self._room(pawn) in (rooms.get('bottomleft'), rooms.get('bottomright'))

    def _entry(self, behaviour='tutorial'):
        """TUTENTRY(aux, neighbor, behaviour) — fcn.1004000a"""
        if behaviour == 'tutorial':
            self._nb_entry()

    # -- the director's steps (GameLogic.dll, the `aux` script) ----------------
    def _d_818c(self):
        # the welcome box (fcn.1001029b) and waypoint1 shown in bottomleft
        self.modal = True
        self.text = (self.pc.get('texts') or {}).get('welcome')
        self._sign('waypoint1', True)
        self._go('8087')

    def _d_8087(self):
        self._msg('waypoint1')
        if self._moving():
            self._go('7fe0')

    def _d_7fe0(self):
        if self._at('waypoint1'):
            self._sign('waypoint1', False)
            self._sign('waypoint2', True)
            self._go('7edb')

    def _d_7edb(self):
        self._msg('waypoint2')
        if self._moving():
            self._go('7df6')

    def _d_7df6(self):
        # at waypoint2: the chest opens in bottomright (soapchest_closed hidden)
        if self._at('waypoint2'):
            self._sign('waypoint2', False)
            self._open('bottomleft/soapchest')
            self._go('7c6b')

    def _d_7c6b(self):
        self._msg('soapbox')
        self._marker('bottomleft/soapchest', True)
        if self._has('soap'):
            self._marker('bottomleft/soapchest', False)
            self._sign('waypoint3', True)
            self._go('7b75')

    def _d_7b75(self):
        self._msg('waypoint3')
        if self._at('waypoint3'):
            self._sign('waypoint3', False)
            self._entry()
            self._go('7ac5')

    def _d_7ac5(self):
        self._msg('neighbordemo')
        if self.latch_tutorial:
            self.latch_tutorial = False
            # the trickable puddle in the closed one's place (topright)
            self._open('topright/waterpuddle')
            self._go('7a0d')

    def _d_7a0d(self):
        self._msg('soappuddle')
        if self.wp is not None and not self.wp.tricked:
            self._marker('topright/waterpuddle', True)
        else:
            self._marker('topright/waterpuddle', False)
            self._go('791d')

    def _d_791d(self):
        self._msg('moveaway')
        if self._lower(self.world.woody):
            self._entry()
            self._go('7820')

    def _d_7820(self):
        self._msg('awaitslip')
        if self.latch_tutorial:
            self.latch_tutorial = False
            self._open('bottomleft/beautycase')
            self._go('7687')

    def _d_7687(self):
        if self._has('hairpin'):
            self._marker('bottomleft/beautycase', False)
            self._sign('waypoint4', True)
            self._go('7581')
        else:
            self._marker('bottomleft/beautycase', True)
            self._msg('beautycase')

    def _d_7581(self):
        self._msg('toolbox')
        if self._at('waypoint4'):
            self._marker('bottomright/toolbox', True)
            self._sign('waypoint4', False)
            self._go('74fc')
        elif self.world.is_dexterity_on:
            self._marker('bottomright/toolbox', False)
            self._sign('waypoint4', False)
            self._go('7407')

    def _d_74fc(self):
        self._msg('minigame_desc')
        if self.world.is_dexterity_on:
            self._marker('bottomright/toolbox', False)
            self._go('7407')

    def _d_7407(self):
        self._msg('minigame')
        if self._has('knife'):
            self._go('734b')
        elif self.latch_run:
            # the toolbox's `failed` sent `run` to aux: relayed to him with
            # the toolbox as the object (TUTENTRY(neighbor, run))
            self.latch_run = False
            self._nb_run()
            self._go('6c17')

    def _d_734b(self):
        self._marker('topleft/buffet', True)
        self._msg('table')
        if self.buffet is not None and self.buffet.tricked:
            self._marker('topleft/buffet', False)
            self._go('725b')

    def _d_725b(self):
        self._msg('moveaway2')
        if self._lower(self.world.woody):
            self._entry()
            self._go('71f5')

    def _d_71f5(self):
        self._msg('awaitpain')
        if self.latch_tutorial:
            self.latch_tutorial = False
            self._go('705a')

    def _soaped(self):
        return self.wp is not None and self.wp.tricked

    def _opened(self):
        return self.rail is not None and self.rail.tricked

    def _d_705a(self):
        self._msg('combo')
        self._marker('bottomleft/soapchest', not self._has('soap'))
        self._marker('topright/reling', True)
        self._marker('topright/waterpuddle', True)
        if self._soaped():
            self._marker('bottomleft/soapchest', False)
            self._marker('topright/waterpuddle', False)
            self._go('6f0a')
        if self._opened():
            self._marker('topright/reling', False)
            self._go('6fa3')

    def _d_6f0a(self):
        self._msg('combo2')
        if self._opened():
            self._marker('topright/reling', False)
            self._go('6d08')

    def _d_6fa3(self):
        self._msg('combo3')
        if self._soaped():
            self._marker('bottomleft/soapchest', False)
            self._marker('topright/waterpuddle', False)
            self._go('6d08')

    def _d_6d08(self):
        self._msg('combo4')
        if self._lower(self.world.woody):
            self._entry()
            self._go('6bb1')

    def _d_6bb1(self):
        self._msg('awaitslip2')
        if self.latch_tutorial:
            self.latch_tutorial = False
            self._go('6a3d')

    def _d_6a3d(self):
        self._msg('danke')
        self._open('topleft/spaghetticar')
        self._go('6640')

    def _d_6640(self):
        # the last step: the box clears while Woody has no room (a pass)
        if self._room(self.world.woody) is None:
            self._msg(None)

    # the lost game (0x10026c17 ...)
    def _d_6c17(self):
        self._msg('hurry')
        woody, rott = self.world.woody, self.rott
        rooms = self.pc.get('rooms') or {}
        if self._in(rooms.get('bottomleft'), woody) and self._in(rooms.get('bottomleft'), rott):
            self._go('6929')
        elif self._in(rooms.get('topleft'), woody):
            self._go('6b27')

    def _d_6929(self):
        self._msg('auweia')
        if self._in((self.pc.get('rooms') or {}).get('topleft'), self.world.woody):
            self._go('651c')

    def _d_6b27(self):
        self._msg('wait1')
        if self._in((self.pc.get('rooms') or {}).get('bottomleft'), self.rott):
            self._go('69b3')

    def _d_69b3(self):
        self._msg('wait1')
        if not self._in((self.pc.get('rooms') or {}).get('bottomleft'), self.rott):
            self._go('65ae')

    def _d_651c(self):
        self._msg('wait2')
        if self._woody_at_toolbox():
            self._go('74fc')

    def _d_65ae(self):
        self._msg('goback')
        if self._woody_at_toolbox():
            self._go('74fc')

    def _woody_at_toolbox(self):
        """fcn.1000e172(toolbox, woody): at the object's woody hotspot"""
        woody = self.world.woody
        tb = self._item('bottomright/toolbox')
        return woody is not None and tb is not None and woody.at_use_range(tb)

    # -- the world's signals ---------------------------------------------------
    def on_behaviour(self, name, item=None):
        """a behaviour sent to `aux`: the toolbox's `failed` action carries
        behavior="run" behavioractor="aux" (ship1/objects.xml) — the latch
        the minigame step reads"""
        if name == 'run':
            self.latch_run = True

    # -- the neighbour's script (0x1002aac8 ...) -----------------------------
    def _park(self, item, freeze=True):
        """a MoveOnly step to the station's PC hotspot (the script's GoTo
        with no DoAction after it) that freezes the manager: his wait"""
        z = self.level.zone_by_pid(item.zone) if item is not None else None
        ap = (item.pc_approach.get('Rottweiler') if item is not None else None) or {}
        x = ap.get('x')
        if isinstance(x, list):
            x = x[0]
        mx = _port_x(z, x) if (z is not None and x is not None
                               and getattr(z, 'pc_room', None)) else (item.x if item else 0.0)
        a = _blank_move_action(item.zone if item is not None else None, freeze=freeze, move_x=mx)
        return a

    def _run_actions(self, actions):
        r = self.rott_routine
        if r is None:
            return
        r.actions = list(actions)
        r.index = 0
        r.unfreeze(start_next=True)

    def _wp_side(self):
        """the puddle's visit slot by the side the mobile's prime toggle
        plays next (primed: the use rightwards — PCApproach's first x and
        tx; unprimed: the prime leg leftwards)"""
        if self.wp is not None:
            self.wp.pc_use_visit = 0 if self.wp.primed else 1

    def _nb_entry(self):
        """the director's TUTENTRY(neighbor, tutorial): his waiting step's
        latch (fcn.10013269) lets it go on"""
        {'start': self._nb_demo, 'cap': self._nb_slip, 'rail': self._nb_buffet,
         'buffet': self._nb_combo}.get(self.nb_phase, lambda: None)()

    def _nb_demo(self):
        # 0x1002aa5b -> 0x1002a933: the hat (lookaround, use), the buffet's
        # flirt, the closed puddle's slip, the rail's look, the left slip —
        # its step tells the director (0x1002a4ea) — and to the hat to wait
        # (0x1002a462 -> 0x1002a3b0); the mobile's demo lap is the same five
        # stations, its park moved to the hat
        b = self.base
        if len(b) < 5:
            return
        cap = self.items.get('CaptainHat')
        if self.wp is not None:
            # the mobile Start's puddle write (TutorialScriptCameraNFH2.cs:
            # 76-80): its slip's stand shift
            self.wp.final_normal = (-0.6, self.wp.final_normal[1])
        self._wp_side()
        self._run_actions(b[:5] + [self._park(cap)])
        self.follow = True
        self._nb_sent = False
        self.nb_phase = 'demo'

    def _nb_slip(self):
        # 0x1002a3b0 -> 0x1002a1cb: to the soaped puddle, crash_short, the
        # puddle back, the shout; 0x1002a14a tells the director; the rail's
        # look (0x1002a06d) and the wait there (0x10029f84)
        b = self.base
        self._wp_side()
        # his wait is at the rail he looked at (0x10029f84: no DoAction, its
        # GoTo finds him there): the look freezes the manager on completion
        self._run_actions([b[2], dict(b[3], freeze_after_completion=True)])
        self.follow = True
        self._nb_sent = False
        self.nb_phase = 'slip'

    def _nb_buffet(self):
        # 0x10029f84 -> 0x10029ea4: the left slip, the hat, the damaged
        # buffet (the flirt, Olga's crash, his, her fight), the repair; then
        # 0x100299c5 tells the director and he waits at the buffet (0x10029939)
        b = self.base
        self._wp_side()
        # he waits at the buffet he repaired (0x10029939: no GoTo)
        self._run_actions([b[4], b[0], dict(b[1], freeze_after_completion=True)])
        self.follow = True
        self._nb_sent = False
        self.nb_phase = 'pain'

    def _nb_combo(self):
        # 0x10029939 -> 0x100297c5: to the soaped puddle by the open rail,
        # crash_long; the entry, the run, the wheeze and the shout follow
        # (pc_trick_hook); then the free lap from the puddle (0x100291cf)
        b = self.base
        self._wp_side()
        r = self.rott_routine
        if r is None or len(b) < 5:
            return
        r.actions = list(b[:5])
        r.index = 2
        r.unfreeze(start_next=True)
        self.follow = True
        self._nb_sent = False
        self.nb_phase = 'combo'

    def _nb_run(self):
        """TUTENTRY(bottomright_toolbox, neighbor, run): the generic `run`
        (0x1003e278: the alarm, the running GoTo to the object, `search`),
        out of his wait — after it the waiting step walks him back
        (0x10029f84's GoTo to the rail)"""
        r = self.rott_routine
        tb = self._item('bottomright/toolbox')
        if r is None or tb is None:
            return
        from world import _dex_surprise
        r.frozen = False
        self._nb_back = self.nb_phase == 'rail'
        _dex_surprise(self.world, r, tb)

    def _nb_reply(self):
        """TUTENTRY(aux, tutorial): the director's latch"""
        if not self._nb_sent:
            self._nb_sent = True
            self.latch_tutorial = True

    def _nb_tick(self):
        r = self.rott_routine
        if r is None:
            return
        idx = r.index % len(r.actions) if r.actions else -1
        parked = r.frozen and r.state == r.IDLE
        if self.nb_phase == 'demo':
            if idx == 4 and r.state != r.IDLE:
                self._nb_reply()          # 0x1002a4ea: as the left slip's step starts
            if idx == 5:
                self.follow = False       # its Eebbf after the slip
            if parked and idx == 5:
                self.nb_phase = 'cap'
        elif self.nb_phase == 'slip':
            if idx == 1 and not self._nb_sent:
                # 0x1002a14a after the crash's sequence (its Eebbf the camera's
                # end); the mobile's Hold3 write: the next pass is the left one
                self._nb_reply()
                self.follow = False
                if self.wp is not None:
                    self.wp.primed = False
            if parked and idx == 1:
                self.nb_phase = 'rail'
            if self._nb_back and r.state == r.USING and r.item is self.rail \
                    and r.urgent_item is None:
                # back from the lost game's run: 0x10029f84's GoTo walks him to
                # the rail and he waits — no second look
                self._nb_back = False
                r.pawn.anim.skip_clip = True
        elif self.nb_phase == 'pain':
            if parked and idx == 2 and not self._nb_sent:
                self._nb_reply()          # 0x100299c5 after the repair
                self.follow = False
                self.nb_phase = 'buffet'
        elif self.nb_phase == 'free' and self._rail_repair is not None:
            rail = self.rail
            anim = r.pawn.anim
            if r.item is rail and r.state == r.USING:
                self._rail_seen = True
                if anim.anim is not None and anim.anim.name != self._rail_repair['clip'] \
                        and not self._rail_shut:
                    # the repair played: reling_open switched back (0x10029063)
                    self._rail_shut = True
                    self.world.play_item_anim(rail, rail.idle)
            elif self._rail_seen:
                rail.use_anim['Rottweiler'] = self._rail_repair['use']
                rail.pc_use_secs = self._rail_repair['secs']
                rail.pc_clip_secs = self._rail_repair['clips']
                if not self._rail_shut:
                    self.world.play_item_anim(rail, rail.idle)
                self._rail_repair = None

    def pc_trick_hook(self, r, it, target):
        """Routine._finish's tricked stop: the combo's crash_long is followed
        by the script's entry, run, wheeze and shout instead of the angry in
        place (0x100297c5 -> 0x1002968d: the actor put at the entry's
        neighbor_entry, fcn.100418f6, in its room, fcn.10041ad0, the gait 2;
        0x100294fc: the GoTo to neighbor_shout, the wheeze, SHOUT 2)"""
        if self.nb_phase != 'combo' or it is not self.wp or not self._opened():
            return False
        w = self.world
        pawn = r.pawn
        if not target.pc_credited:
            w.pc_s2_credit(pawn, target)  # the crash_long's records pay as it ends
        z, x, _y = self._pc_point(self.pc.get('entry'))
        sz, sx, _sy = self._pc_point(self.pc.get('shout'))
        if z is None or sz is None:
            return False
        pawn.steps = []
        pawn._step = None
        pawn.sprite.x, pawn.sprite.y = x, pawn.floor_y(z)
        pawn.zone = z
        pawn.pos_snap = True
        pawn.pc_run = True
        pawn.in_urgent = True
        r.state = r.MOVING

        def wheeze():
            pawn.pc_run = False
            pawn.in_urgent = False
            r.state = r.USING
            r.timer = 0.0
            pawn._stand()                 # no wheeze clip in the mobile set
            r.pc_hold = float(self.pc.get('wheeze') or 0) / 12.0
            r.pc_hold_cb = shout

        def shout():
            fl = it.final_linked
            it.final_linked = (0.0, 0.0)  # the linked stand shift is the crash spot's
            r._angry_target = target
            w.play_angry(pawn, target, on_done=shouted)
            it.final_linked = fl

        def shouted():
            # 0x1002947b tells the director; the free lap from the puddle
            # (0x100291cf), its slip rightwards (the mobile End1's write)
            self._nb_reply()
            self.follow = False
            if self.wp is not None and not self.wp.primed:
                w.set_primed(self.wp, True)
            self._wp_side()
            self._open_rail()
            r.index = 1                   # the pending advance lands on the puddle
            self.nb_phase = 'free'
            r._angry_done()

        if not pawn.goto_zone(sz, sx, on_arrive=wheeze):
            wheeze()
        return True

    def _open_rail(self):
        """the rail stays open after the crash_long (0x100297c5 switches only
        the puddle back) until his next rail visit, which repairs it first
        (0x10029063: reling_open's `repair`, then the switch back) and looks
        (0x10028f86); the mobile's linked use has closed it: its open pose
        is shown and that visit's clips are the repair and the look at their
        PC ticks (PCTutorial rail_repair, the rail's PCUseSeconds)"""
        rail = self.rail
        rott = self.rott
        ticks = self.pc.get('rail_repair')
        if rail is None or rott is None or not ticks:
            return
        clip = rail.fix_animation
        use = list(rail.use_anim.get('Rottweiler') or [])
        if not clip or not rott.anim.has(clip) or not use:
            return
        secs = rail.pc_use_secs
        look = secs[0] if isinstance(secs, list) and secs else secs
        self._rail_repair = {'clip': clip, 'use': use, 'secs': secs,
                             'clips': getattr(rail, 'pc_clip_secs', None)}
        self._rail_seen = False
        self._rail_shut = False
        rail.use_anim['Rottweiler'] = [clip] + use
        rail.pc_use_secs = None           # the visit timed per clip
        rail.pc_clip_secs = dict({clip: float(ticks) / 12.0},
                                 **({use[0]: float(look)} if look else {}))
        if rail.idle_tricked:
            self.world.play_item_anim(rail, rail.idle_tricked)

    def pc_shout(self, pawn, item):
        """the scripted shout's level where the tutorial's step is not the
        lap's (SHOUT, fcn.1000f977: 2 after the wheeze, 0x100294fc, where
        the puddle's lap step shouts 1, 0x1002847f); None: the item's own
        (PCShout — the buffet's 0x10029a6c pushes ebx, 1 by its
        `xor ebx, ebx; inc ebx`)"""
        if pawn is self.rott and item is self.wp and self.nb_phase == 'combo':
            return 2
        return None

    # -- the drawing -------------------------------------------------------------
    @property
    def current(self):
        return None

    def draw(self, g, dt, menu_open=False):
        if menu_open:
            return
        cam = self.viewer.cam
        if self.arrow:
            s = self.H * 64 // 768
            self.arrow_anim.update(dt)
            for name in sorted(self.markers):
                it = self.items.get(name)
                if it is None:
                    continue
                ox, oy = self.arrow_off.get(name, (0.0, 0.0))
                sx, sy = cam.world_to_screen(it.x + ox, it.y + oy, self.W, self.H)
                g.tex(self.arrow[self.arrow_anim.frame], (sx, sy, s, s))
        if self.sign:
            w = self.W * 128 // 1024
            h = self.H * 64 // 768
            self.sign_anim.update(dt)
            for name in sorted(self.signs):
                z, x, _y = self._pc_point((self.pc.get('waypoints') or {}).get(name))
                if z is None:
                    continue
                sx, sy = cam.world_to_screen(x + self.sign_off[0],
                                             z.ty + self.sign_off[1], self.W, self.H)
                g.tex(self.sign[self.sign_anim.frame], (sx, sy, w, h))
        if self.text:
            g.tex(self.message_background, self.message_rect)
            g.label(self.description_rect, self.text, self.message_style, self.font)
            if self.director is not None:
                self.director.draw(g)


PC_TICK = 1.0 / 12.0


class _PCScript:
    """one GameLogic.dll level script of TutorialPC206: its step, run once a
    level tick while the actor's queue is idle until it stores the next (the
    level update's script pass), the jobs its steps push onto the actor's
    queue — each a count of level ticks, the runner going on past a done job
    in the same tick (fcn.100492a8) —, its GoTo in progress and its latches
    (fcn.10013269: a behaviour of the latch's name arrived)"""

    def __init__(self, name, step):
        self.name = name
        self.step = step
        self.queue = []                   # [{'ticks', 'start', 'end', 'at'}]
        self.cur = None
        self.left = 0
        self.age = 0
        self.walking = False
        self.arrived = None               # the target the last GoTo reached
        self.latches = set()
        self.icon = None

    def idle(self):
        return self.cur is None and not self.queue and not self.walking

    def take(self, name):
        if name in self.latches:
            self.latches.discard(name)
            return True
        return False


class TutorialPC206(Tutorial):
    """The PC's own 206 lesson, in place of the mobile's LevelScript and
    TutorialScriptCameraNFH2206 under the PC profile (docs/PC_FIDELITY.md
    "206's lesson"). GameLogic.dll runs it as three scripts (_PCScript):
    the invisible `aux` actor's director (fcn.1002b64d: 0x1002b5e7 ...
    0x1002afee — the messages fcn.100101f3, the markers fcn.10042077, the
    gates on Woody's inventory fcn.1002b0d9, an object present
    fcn.1000ec67, his lower-deck rooms fcn.1000ed06 and his hideout flag 4
    through the level's slot 0x18), the Mother's (0x1002c3af ...
    0x1002bb39) and the neighbour's (0x1002f15a ... 0x1002e926), which hand
    each other `call` and `order` (generic/objects.xml's callneighbor and
    order), `mother_pillow` (the chair's give), `mother_fight` (the fight)
    and `tutorial` (fcn.1004000a): a job's behaviour posted as it ends, a
    post offered on the tick after, where the waiting step reads it. The
    jobs are the mobile pawns' clips paced to the PC's job ticks
    (PCTutorial `ticks`, tools/pcref/pc_tutorial206.py), the GoTos the
    pawns' walks to the stations' PC hotspots (a run where the step writes
    gait 2); both routines stay frozen until the lap — his from the mobile's
    selected index (0x1002e926 -> 0x1002e63c, DogFifi's take), hers the
    mobile's End1 (her chair; the PC's 0x1002b9fe bar)."""

    def __init__(self, d, W, H, loc, viewer, director, pc, cam):
        Tutorial.__init__(self, d, W, H, loc, viewer, director=director)
        self.pc = pc
        self.cam_d = cam or {}
        self.actions = []                 # no LevelScriptActions: current is None
        self.text = None
        self.msg = None
        self.shown = []
        self.markers = set()
        self.follow = False
        self.ticks = self.pc.get('ticks') or {}
        self.zones = {z.name: z for z in self.level.zones}
        self.items = {it.name: it for it in self.level.items.values()}
        self.aux = _PCScript('aux', 'b5e7')
        self.mom = _PCScript('mother', 'c3af')
        self.nb = _PCScript('neighbor', 'f15a')
        self.scripts = (self.aux, self.mom, self.nb)
        self.posts = []                   # [(offer tick, script, behaviour)]
        self.tick_n = 0
        self._acc = 0.0
        self.inside = False               # the Mother in her chair (the hideout)
        self.done = False
        r = self.rott_routine
        self.base = list(r.actions) if r is not None else []
        # the mobile arrows' offsets over the same objects (LevelScript
        # actions' AnimOffset); the pipe's arrow points right
        self.arrow_off = {}
        self.arrow_right_items = set()
        for a in d.get('Actions') or []:
            off = a.get('AnimOffset') or {}
            ref = self._pid(a.get('Item'))
            it = self.level.items.get(ref) if ref is not None else None
            if it is not None and (a.get('DrawArrow') or a.get('DrawArrowRight')):
                self.arrow_off.setdefault(it.name, (off.get('x') or 0.0, off.get('y') or 0.0))
                if a.get('DrawArrowRight'):
                    self.arrow_right_items.add(it.name)
        self._setup()

    # -- the level as the PC starts it ---------------------------------------
    def _setup(self):
        """level.xml's starts: Woody in bottomright, the neighbour at Fifi
        laughing (`laughleft`, the mobile's LaughLeftInfinite), the Mother by
        her chair; the doors open (the remaster's stair locks are its
        lesson's); both routines frozen for the scripts"""
        w = self.world
        for key, pawn in (('woody', w.woody), ('neighbor', self.rott),
                          ('mother', w.pawns.get('Mother'))):
            z, x, _y = self._pc_point(self.pc.get(key))
            if pawn is None or z is None:
                continue
            pawn.sprite.x, pawn.sprite.y = x, pawn.floor_y(z)
            pawn.zone = z
            pawn.pos_snap = True
            if key == 'woody':
                self.level.entrance_location = (pawn.sprite.x, pawn.sprite.y)
        for key in ('LeftSideStair', 'RightSideStair', 'UpTransition', 'DownTransition'):
            door = self.level.door_by_pid(self._pid(self.cam_d.get(key)))
            if door is not None:
                door.locked = False
        for r in (self.rott_routine, self.mother_routine):
            if r is not None:
                r.frozen = True
                r.delay_start = 0.0
        rott = self.rott
        if rott is not None and rott.anim.has('LaughLeftInfinite'):
            rott.anim.play_looping('LaughLeftInfinite')
        fifi = self._item('topleft/fifi')
        if fifi is not None and not fifi.primed:
            # the mobile's opening DogFifi visit is its prime leg
            # (RottweilerPrimeAnimation LaughLeft, LaughLeftInfinite): the
            # PC's start pose — his lap's first visit takes her; the first
            # prime's DogFifi arm swaps the later primes to the put
            # (Item.RottweilerPrime, Routine._use's toggle)
            w.set_primed(fifi, True)
            if not fifi.prime_item_aux:
                fifi.prime_item_aux = True
                fifi.rott_prime_anim = ['FifiPutLeft']

    def _pc_point(self, rec):
        """[zone, pc x, pc y, ...] -> (zone, mobile x, pc y)"""
        if not rec:
            return None, 0.0, 0.0
        z = self.zones.get(rec[0])
        if z is None or getattr(z, 'pc_room', None) is None:
            return None, 0.0, 0.0
        return z, _port_x(z, rec[1]), rec[2]

    def _item(self, pc_name):
        return self.items.get((self.pc.get('items') or {}).get(pc_name))

    @property
    def rott(self):
        return self.world.pawns.get('Rottweiler')

    @property
    def mother(self):
        return self.world.pawns.get('Mother')

    @property
    def rott_routine(self):
        rott = self.rott
        return next((r for r in self.world.routines if r.pawn is rott), None)

    @property
    def mother_routine(self):
        m = self.mother
        return next((r for r in self.world.routines if r.pawn is m), None)

    # -- the lifecycle -------------------------------------------------------
    def activate(self):
        if self.active:
            return
        self.active = True
        if self.director is not None:
            self.director.restart()

    def tick(self, dt):
        if not self.active:
            return
        if self.director is not None:
            self.director.tick(dt)
        if not self.done:
            self._acc += dt
            while self._acc >= PC_TICK - 1e-9 and not self.done:
                self._acc -= PC_TICK
                self._level_tick()
        if self.follow:
            r = self.rott
            if r is not None:
                self.viewer.cam.x, self.viewer.cam.y = r.sprite.x, r.sprite.y
                self.viewer._clamp_camera()

    def _level_tick(self):
        self.tick_n += 1
        due = [p for p in self.posts if p[0] <= self.tick_n]
        self.posts = [p for p in self.posts if p[0] > self.tick_n]
        for _t, s, name in due:
            s.latches.add(name)
        for s in self.scripts:
            self._run_queue(s)
            if s.idle() and s.step is not None:
                getattr(self, '_%s_%s' % (s.name[0], s.step))(s)

    def _run_queue(self, s):
        """the actor's queue for this tick: the running job's count, its end,
        and the next job's first tick in the same pass"""
        while True:
            if s.cur is None:
                if not s.queue:
                    return
                s.cur = s.queue.pop(0)
                s.left = int(s.cur.get('ticks') or 0)
                s.age = 0
                if s.cur.get('start'):
                    s.cur['start']()
            s.age += 1
            at = s.cur.get('at')
            if at and s.age == at[0]:
                at[1]()
            if s.age >= s.left:
                job, s.cur = s.cur, None
                if job.get('end'):
                    job['end']()
                continue
            return

    def _push(self, s, *jobs):
        """elements pushed onto the actor's queue without a first run
        (fcn.10049216, the builder's fcn.1000eec6): the first counts from
        the next tick (the queues run before the steps, _level_tick)"""
        s.queue.extend(jobs)

    def _post(self, s, name):
        """fcn.1004000a: the behaviour offered on the tick after"""
        self.posts.append((self.tick_n + 1, s, name))

    def _icon(self, s, name):
        """fcn.100422a5: the actor's bubble (the routine's pc_bubble; ''
        clears it)"""
        r = self.mother_routine if s is self.mom else self.rott_routine
        if r is not None:
            r.pc_bubble = name

    def _goto(self, s, pawn, item, run=False):
        """fcn.1000e3e0: the GoTo pushed with a first run, the step run again
        each tick until it returns 0 — at the object's hotspot the GoTo
        finds the actor there and returns at once"""
        if s.arrived is item:
            return True
        if s.walking:
            return False
        pawn.pc_run = run
        pawn.in_urgent = run

        def arrive(s=s, item=item, pawn=pawn):
            s.walking = False
            s.arrived = item
            pawn.pc_run = False
            pawn.in_urgent = False
        s.walking = True
        if not pawn.goto_item(item, on_arrive=arrive):
            arrive()
        return False

    def _leave_station(self, s):
        s.arrived = None

    def _clip(self, pawn, seq, ticks, loop=None):
        """a job's clips: the mobile sequence paced to the PC job's ticks,
        then its next animation looping (the action's actornextanim)"""
        seq = [a for a in seq if pawn.anim.has(a)]
        if not seq:
            if loop and pawn.anim.has(loop):
                pawn.anim.play_looping(loop)
            return
        mobile = pawn.anim.sequence_seconds(seq)
        secs = ticks * PC_TICK
        pawn.anim.time_scale = mobile / secs if (mobile > 0.0 and secs > 0.0) else 1.0

        def ended(pawn=pawn, loop=loop):
            pawn.anim.time_scale = 1.0
            if loop and pawn.anim.has(loop):
                pawn.anim.play_looping(loop)
        pawn.anim.play_sequence(seq, on_end=ended, as_sequence=False)

    def _job(self, name, pawn, seq, loop=None, end=None, at=None):
        t = int(self.ticks.get(name) or 0)
        return {'ticks': t, 'start': lambda: self._clip(pawn, seq, t, loop),
                'end': end, 'at': at}

    # -- the director's helpers ------------------------------------------------
    def _msg(self, name):
        """fcn.100101f3: the message box shows the text (none: it closes)"""
        if self.msg == name:
            return
        self.msg = name
        self.text = (self.pc.get('texts') or {}).get(name) if name else None
        if name:
            self.shown.append(name)
            if self.director is not None:
                self.director.animating = True
                self.director.restart()

    def _marker(self, pc_name, on):
        """fcn.10042077: the marker arrow over the object ('ms') or none"""
        it = self._item(pc_name)
        if it is None:
            return
        if on:
            self.markers.add(it.name)
        else:
            self.markers.discard(it.name)

    def _has(self, pc_inv):
        """fcn.1002b0d9 -> fcn.10049cec: Woody's inventory holds the item"""
        typ = (self.pc.get('inventory') or {}).get(pc_inv)
        return typ is not None and self.world.inventory.has(typ)

    def _manip(self):
        """fcn.1000ec67(topright_pillows_manip): the fart bag on the pillows
        (the mobile's tricked Pillows)"""
        it = self._item('topright/pillows_manip')
        return it is not None and it.tricked

    def _lower(self):
        """fcn.1000ed06(bottomright, bottomleft): Woody's room one of them"""
        woody = self.world.woody
        z = woody.pc_room() if woody is not None else None
        return z is not None and z.name in (self.pc.get('lower') or ())

    def _hidden(self):
        """the level's slot 0x18 (woody, 4): his flag 4, in a hideout"""
        woody = self.world.woody
        return woody is not None and bool(woody.hiding)

    # -- the director (GameLogic.dll, the `aux` script) ----------------------
    def _a_b5e7(self, s):
        self._msg('step1')
        if s.take('tutorial'):
            s.step = 'b51c'

    def _a_b51c(self, s):
        self._marker('bottomleft/toybox', True)
        self._msg('step2')
        if self._has('fartbag'):
            self._marker('bottomleft/toybox', False)
            s.step = 'b434'

    def _a_b434(self, s):
        self._marker('topright/pillows', True)
        self._msg('step2a')
        if self._manip():
            self._marker('topright/pillows', False)
            self._msg('step3')
            s.step = 'b28c'

    def _a_b28c(self, s):
        self._marker('topright/ventpipe', True)
        if self._lower():
            self._msg('step3a')
        if self._hidden():
            self._post(self.mom, 'tutorial')
            self._post(self.nb, 'tutorial')
            self._marker('topright/ventpipe', False)
            s.step = 'b226'

    def _a_b226(self, s):
        self._msg('step4')
        if s.take('tutorial'):
            s.step = 'b1af'

    def _a_b1af(self, s):
        self._msg('step5')
        if not self._hidden():
            s.step = 'afee'

    def _a_afee(self, s):
        self._msg(None)
        s.step = None

    # -- the Mother's script -----------------------------------------------------
    def _m_c3af(self, s):
        # to her chair's `mother` hotspot
        if self._goto(s, self.mother, self._item('topleft/deckchair')):
            s.step = 'c2d9'

    def _m_call(self, s):
        """the builder's leave, pillow_slip and callneighbor (0x1002c2d9,
        0x1002bf25): the leave done at its first update when she is not in
        the chair (0x10006945 -> 0x10006ab7), its getup when she is; the
        call's `call` to him as its job ends"""
        m = self.mother
        jobs = []
        if self.inside:
            def up():
                self.inside = False
            jobs.append(self._job('leave', m, ['MotherGetUpPillow'], end=up))
        jobs.append(self._job('pillow_slip', m, ['MotherHoldPillow', 'MotherThrowPillow']))
        jobs.append(self._job('callneighbor', m, ['MotherCall'], loop='MotherStandDownInfinite',
                              end=lambda: self._post(self.nb, 'call')))
        self._push(s, *jobs)

    def _m_c2d9(self, s):
        self._icon(s, 'neighbor')
        self._m_call(s)
        s.step = 'c1d9'

    def _m_order(self, s):
        """fcn.1000e172: he stands at the chair's `neighbor` hotspot (his
        GoTo there done, waiting for her) — her `order`, posted to him as
        its job ends"""
        if not (self.nb.step in ('f082', 'ecb5') and self.nb.arrived is not None
                and self.nb.arrived is self._item('topleft/deckchair')):
            return False
        self._icon(s, 'bring_pillow')
        self._push(s, self._job('order', self.mother, ['MotherOrder'], loop='MotherStandDownInfinite',
                                end=lambda: self._post(self.nb, 'order')))
        return True

    def _m_c1d9(self, s):
        self._icon(s, 'neighbor')
        if self._m_order(s):
            s.step = 'c183'

    def _m_c183(self, s):
        self._icon(s, '')
        if s.take('mother_pillow'):
            s.step = 'c09b'

    def _m_c09b(self, s):
        if not self._goto(s, self.mother, self._item('topleft/deckchair')):
            return
        self._post(self.aux, 'tutorial')

        def sat():
            self.inside = True
        # fcn.1000ea30: the chair's enter (sitdown_pillow), then its `look`
        self._push(s, self._job('enter', self.mother, ['MotherSitPillow'], loop='MotherLookLoop', end=sat))
        s.step = 'bf25'

    def _m_bf25(self, s):
        if s.take('tutorial'):
            self._icon(s, 'neighbor')
            self._m_call(s)
            s.step = 'be25'

    def _m_be25(self, s):
        self._icon(s, 'neighbor')
        if self._m_order(s):
            s.step = 'bd7d'

    def _m_bd7d(self, s):
        self._icon(s, '')
        if s.take('mother_pillow'):
            # (the record `time` ticks after the job's first)
            rec = int(self.pc.get('fart_record') or 0)
            self._push(s, self._job('fart', self.mother, ['MotherSitFart'],
                                    at=(rec + 1, self._fart_pays) if rec else None, end=self._fart_end))
            s.step = 'bd04'

    def _fart_pays(self):
        """the fart's fartbag record at its `time` (fcn.1000140b): the coin
        and the rage (the neighbour's) of the chair's trick — the mobile's
        DeckChair, whose trick the pillows activate (its AngerAmount 45, the
        record's 45000)"""
        it = self._item('topleft/deckchair')
        rott = self.rott
        if it is not None and rott is not None:
            self.world.pc_s2_credit(rott, it)

    def _fart_end(self):
        """sitdown_fart's objnextanim `ms`: the chair plain again"""
        ch = self._item('topleft/deckchair')
        if ch is not None:
            ch.tricked = False

    def _m_bd04(self, s):
        self._icon(s, '')        # m_hurt_n: no remaster texture, none shown
        # fcn.1000eb19: to him (fcn.1000e601, his x less or plus 50 px on
        # her side), then the generic `fight` (fight_neighbor, him `inv`)
        if not s.walking and s.arrived != 'fight':
            m, rott = self.mother, self.rott
            z = rott.zone
            if z is None or getattr(z, 'pc_room', None) is None:
                s.arrived = 'fight'
            else:
                from world import pc_room_x
                gap = self.pc.get('fight_gap') or 50
                hx = pc_room_x(z, rott.sprite.x)
                mx = pc_room_x(z, m.sprite.x) if m.zone is z else hx - gap
                tx = hx - gap if mx <= hx else hx + gap
                m.pc_run = True
                m.in_urgent = True

                def arrive():
                    s.walking = False
                    s.arrived = 'fight'
                    m.pc_run = False
                    m.in_urgent = False
                s.walking = True
                if not m.goto_zone(z, _port_x(z, tx), on_arrive=arrive):
                    arrive()
                return
        if s.arrived != 'fight':
            return
        rott = self.rott

        def hide():
            rott.set_hidden(True)

        def shown():
            rott.set_hidden(False)
            self._post(self.nb, 'mother_fight')
        job = self._job('fight', self.mother, ['MotherHitNeighbor'], end=shown)
        start = job['start']
        job['start'] = lambda: (hide(), start())
        self._push(s, job)
        s.step = 'bb39'

    def _m_bb39(self, s):
        self._post(self.aux, 'tutorial')
        self._icon(s, None)
        s.step = None
        self._mother_lap()

    def _mother_lap(self):
        """her lap: the mobile End1's (TutorialScriptCameraNFH2206.cs:151-163:
        her chair from index 3, looping from it, the chair's sleep) for the
        PC's 0x1002b9fe (the chair's `sleep` bar)"""
        m = self.mother_routine
        if m is None:
            return
        m.pc_bubble = None
        # (the mobile's surgery once the pillows are tricked, Hold2,
        # TutorialScriptCameraNFH2206.cs:112-126: her throw's stands, her
        # chair's look a single — the loop's own chair visits go on to the
        # second use's sleep; the PC's 0x1002b9fe sits her down and puts her
        # to sleep at once, the look after the 720-tick bar: her first visit
        # the sit alone, the second use's set her loop, paced by her script,
        # PCClipSecondsRole)
        its = self.level.items
        if len(m.actions) > 3:
            it0 = its.get(m.actions[0]['item']) if m.actions[0]['item'] else None
            if it0 is not None:
                it0.use_anim['Mother'] = ['MotherStandDownSingle'] * 8
            it3 = its.get(m.actions[3]['item']) if m.actions[3]['item'] else None
            if it3 is not None:
                it3.use_anim['Mother'] = ['MotherSitPillow']
        if self.rott is not None:
            self.rott.deck_chair_aux = True
        m.index = 3
        m.loop_from_selected = True
        m.frozen = False
        m._pending = 'start'
        deck = self._item('topleft/deckchair')
        mp = self.mother
        if mp is not None and deck is not None:
            seq = [a for a in (deck.mother_second_use or []) if mp.anim.has(a)]
            if seq:
                mp.anim.play_sequence(seq)

    # -- the neighbour's script --------------------------------------------------
    def _n_f15a(self, s):
        self.follow = True               # Ef51a: the camera on him
        s.step = 'f11d'

    def _n_f11d(self, s):
        if s.take('call'):
            s.step = 'f082'

    def _n_chair(self, s, nxt):
        """to the chair's `neighbor` hotspot at a run, then his wait there
        for her `order` (0x1002f082, 0x1002ecb5)"""
        self._icon(s, 'mother')
        if not self._goto(s, self.rott, self._item('topleft/deckchair'), run=True):
            return
        if s.take('order'):
            self._leave_station(s)
            s.step = nxt

    def _n_f082(self, s):
        self._n_chair(s, 'ef9e')

    def _n_pillows(self, s, nxt, manip):
        self._icon(s, 'get_pillow')
        pil = self._item('topright/pillows')
        if not self._goto(s, self.rott, pil, run=True):
            return
        self._leave_station(s)
        end = None
        if manip:
            def end():
                # the switch back to the plain pillows (0x1002ec4c)
                pil.tricked = False
        self._push(s, self._job('take', self.rott, ['TakeHigh'], end=end))
        s.step = nxt

    def _n_ef9e(self, s):
        self._n_pillows(s, 'ee4d', False)

    def _n_give(self, s, nxt, camera_off):
        self._icon(s, 'bring_pillow')
        if not self._goto(s, self.rott, self._item('topleft/deckchair'), run=True):
            return
        self._leave_station(s)

        def given():
            self._post(self.mom, 'mother_pillow')
            if camera_off:
                self.follow = False      # Eebbf, done at its first update
        self._push(s, self._job('give', self.rott, ['TakeLeft'], end=given))
        s.step = nxt

    def _n_ee4d(self, s):
        self._n_give(s, 'ed50', True)

    def _n_ed50(self, s):
        self._icon(s, '')
        if not self._goto(s, self.rott, self._item('topleft/fifi')):
            return
        rott = self.rott
        # fcn.100419a3: his `wait`
        if rott.anim.has('WaitWatch') and (rott.anim.anim is None or rott.anim.anim.name != 'WaitWatch'):
            rott.anim.play_looping('WaitWatch')
        if s.take('tutorial'):
            self.follow = True           # Ef51a
        if s.take('call'):
            self._leave_station(s)
            s.step = 'ecb5'

    def _n_ecb5(self, s):
        self._n_chair(s, 'eb3b')

    def _n_eb3b(self, s):
        self._n_pillows(s, 'ea57', True)

    def _n_ea57(self, s):
        self._n_give(s, 'e926', False)

    def _n_e926(self, s):
        self._icon(s, '')        # m_hurt_n: no remaster texture, none shown
        if not s.take('mother_fight'):
            return
        import pcprofile
        import random
        rott = self.rott
        level = self.pc.get('shout') or 1
        secs = pcprofile.s2_reaction_seconds(level, random, rott.pc_rage_full)
        ticks = int(round(secs * 12))

        def shouted():
            self.follow = False          # Eebbf
        self._push(s, {'ticks': ticks,
                       'start': lambda: self._clip(rott, ['AngryEasyUp', 'AngryHard'], ticks),
                       'end': shouted})
        s.step = 'lap'

    def _n_lap(self, s):
        """0x1002e63c: the lap, the mobile's loop from its selected index"""
        s.step = None
        self._icon(s, None)
        r = self.rott_routine
        if r is not None and len(self.base) > 4:
            r.actions = list(self.base)
            r.index = 4
            r.unfreeze(start_next=True)
        self.done = True

    # -- the drawing -------------------------------------------------------------
    @property
    def current(self):
        return None

    def draw(self, g, dt, menu_open=False):
        if menu_open:
            return
        cam = self.viewer.cam
        s = self.H * 64 // 768
        if self.arrow:
            self.arrow_anim.update(dt)
        if self.arrow_right:
            self.arrow_right_anim.update(dt)
        for name in sorted(self.markers):
            it = self.items.get(name)
            if it is None:
                continue
            right = name in self.arrow_right_items and self.arrow_right
            tex = (self.arrow_right[self.arrow_right_anim.frame] if right
                   else (self.arrow[self.arrow_anim.frame] if self.arrow else None))
            if tex is None:
                continue
            ox, oy = self.arrow_off.get(name, (0.0, 0.0))
            sx, sy = cam.world_to_screen(it.x + ox, it.y + oy, self.W, self.H)
            g.tex(tex, (sx, sy, s, s))
        if self.text:
            g.tex(self.message_background, self.message_rect)
            g.label(self.description_rect, self.text, self.message_style, self.font)
            if self.director is not None:
                self.director.draw(g)


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
    kind, pc = _pc_tutorial(viewer)
    if pc is not None:
        # the PC profile's 201 and 206: the PC's own tutorial replaces the
        # LevelScript and the camera script (TutorialPC201, TutorialPC206)
        found = scene_data.find(kind)
        cls = TutorialPC206 if kind == 'TutorialScriptCameraNFH2206' else TutorialPC201
        tut = cls(d, W, H, loc, viewer, director, pc, found[0][1] if found else None)
        return tut, None
    tut = Tutorial(d, W, H, loc, viewer, director=director)
    cam = None
    for typ, cls in CAMERA_CLASSES.items():
        found = scene_data.find(typ)
        if found:
            cam = cls(found[0][1], W, H, viewer, tut)
            tut.camera_script = cam
            break
    return tut, cam


def _pc_tutorial(viewer):
    """(the camera component, the overlay's PCTutorial on it) of the level —
    its TutorialScriptCameraNFH2 (201) or TutorialScriptCameraNFH2206 (206),
    patched by pcprofile.apply_overlay — under the PC profile"""
    import pcprofile
    if not pcprofile.is_pc():
        return None, None
    for o in viewer.level.objs.values():
        if o.get('type') in ('TutorialScriptCameraNFH2', 'TutorialScriptCameraNFH2206'):
            pc = (o.get('data') or {}).get('PCTutorial')
            if pc is not None:
                return o.get('type'), pc
    return None, None

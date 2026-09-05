"""The per-level scripted behaviors, ported class by class.

Each class mirrors one src/Assembly-CSharp behavior: the ActorBehavior
subclasses hang off Actor.Behavior / SecondaryBehaviors and receive
PlayAnimation / OnAdvanceFrame from the animation controller
(Actor.cs:93-115, AnimationControllerBase.cs:112-114, 384), the sequence-end
and caught hooks from the Rottweiler (Rottweiler.cs:448, 514-524, 1223-1239)
and a MonoBehaviour Update per tick; RoutineBehavior gets the ActionManager's
start/move hooks (ActionManager.cs:119-124, 165-168); SearchBehavior gets
Woody.OnSearchItemUsed (Woody.cs:985-991).

Serialized references resolve against the live world: Items by component pid,
Pawns by the owning component's pid, Zones via Level.zone_by_component.
"""

import os
from scene import GUI_DEPTH

NONE = ('NONE', None)


class Behavior:
    def __init__(self, world, d):
        self.world = world
        self.level = world.level
        self.d = d
        self.enabled = True
        self.current_animation = None    # ActorBehavior.CurrentAnimation

    # -- serialized-reference resolution -----------------------------------
    def item(self, field):
        ref = self.d.get(field) or {}
        return self.level.items.get(ref.get('path'))

    def pawn(self, field):
        pid = (self.d.get(field) or {}).get('path')
        for role, spec in self.level.pawns.items():
            if spec.get('pid') == pid:
                return self.world.pawns.get(role)
        return None

    def zone(self, field):
        return self.level.zone_by_component(
            (self.d.get(field) or {}).get('path'))

    def value(self, field, default=None):
        v = self.d.get(field)
        return default if v is None else v

    def anim_name(self, field, default=None):
        v = self.d.get(field)
        return default if v in NONE else v

    def vec(self, field, default=(0.0, 0.0)):
        v = self.d.get(field) or {}
        return (v.get('x', default[0]), v.get('y', default[1]))

    # -- world shortcuts (port plumbing for the C# singletons: GameInfo.
    #    Instance.Rottweiler, <pawn>.ActionManager, <item>.AnimController) --
    def rott(self):
        """GameInfo.Instance.Rottweiler"""
        return self.world.pawns.get('Rottweiler')

    def routine(self, role='Rottweiler'):
        """GameInfo.Instance.<role>.ActionManager"""
        return next((r for r in self.world.routines if r.role == role), None)

    def routine_of(self, pawn):
        """pawn.ActionManager"""
        return next((r for r in self.world.routines if r.pawn is pawn), None)

    def action_item(self, role='Rottweiler'):
        """GameInfo.Instance.<pawn>.ActionManager.CurrentAction.Item — the
        urgent action's item when one runs, else the routine's"""
        rt = self.routine(role)
        if rt is None:
            return None
        return rt.urgent_item if rt.urgent_item is not None else rt.item

    def player(self, it):
        """item.AnimController (the port's AnimPlayer of the item's sprite)"""
        if it is None or it.sprite is None:
            return None
        return self.world.players.get(id(it.sprite))

    # -- the C# helpers the behaviors lean on ------------------------------
    def hide_obj(self, it, hidden):
        """Item.SetObjectHidden (Item.cs:1984-1995): the object's OWN
        renderer — the backdrop quad on a static item (L101's Binoculars)
        — and its controller; world.set_object_hidden carries both"""
        if it is not None:
            self.world.set_object_hidden(it, hidden)

    def set_active(self, it, active):
        """GameObject.SetActive on an item's object"""
        if it is not None:
            self.world.set_active(it, active)

    def go_set_active(self, field, active):
        """GameObject.SetActive: an object carrying an Item goes through
        World.set_active — the renderer, the click box and the active flag
        together (the Washbucket and the Cloth of L214 are items Woody must
        click); a bare visual object toggles its sprite, else its backdrop
        quad by name"""
        go = (self.d.get(field) or {}).get('path')
        if go is None:
            return
        it = next((x for x in self.level.items.values() if x.go == go), None)
        if it is not None:
            self.world.set_active(it, active)
            return
        for s in self.level.sprites:
            if s.go == go:
                s.hidden = not active
                return
        o = self.level._o(go)
        name = (o.get('data') or {}).get('name') if o else None
        for q in self.level.quads:
            if q.get('name') == name:
                q['active'] = active
                return

    def play_item(self, it, name):
        """TrickItem.PlayItemAnimation"""
        if it is not None:
            self.world.play_item_anim(it, name)

    def play_directly(self, it, name):
        """it.AnimController.PlayAnimationDirectly"""
        p = self.player(it)
        if p is not None and name and p.has(name):
            p.play_directly(name)

    def play_looping(self, it, name):
        """it.AnimController.PlayLoopingAnimation"""
        p = self.player(it)
        if p is not None and name and p.has(name):
            p.play_looping(name)

    def depth(self, target, name):
        """AnimController.AnimationGUIDepth = GUIDepth.<name>; target is a
        Pawn or an Item"""
        v = GUI_DEPTH.get(name)
        if v is None or target is None:
            return
        sprite = target.sprite
        if sprite is not None:
            sprite.depth = v

    def collider(self, it, on):
        """((Component)it).GetComponent<Collider>().enabled"""
        if it is not None:
            it.clickable = on
            if os.environ.get('NFH_TRACE_COLLIDER'):    # the bench's Collider.enabled trace
                print('collider %s %s t=%s' % (it.name, on, getattr(self.world, 't', None)), flush=True)

    # -- hook defaults (ActorBehavior.cs, RoutineBehavior.cs) --------------
    def play_animation(self, name):
        self.current_animation = name    # ActorBehavior.PlayAnimation base

    def on_advance_frame(self, idx):
        pass

    def on_animation_sequence_ended(self):
        pass

    def can_see_woody(self):
        return True

    def on_caught_woody(self):
        pass

    def can_check_surprise_action_far(self):
        return True

    def on_start_routine_action(self, item, action):
        pass

    def on_move_to_routine_action(self, item, action):
        pass

    def on_search_item_used(self, item):
        pass

    def update(self, dt):
        pass


# ---------------------------------------------------------------------------
# Season 1
# ---------------------------------------------------------------------------

class Level101Behavior(Behavior):
    """Level101Behavior.cs: the neighbour's binocular peep hides the item —
    the sheets draw it in his hands — and a tricked peep writes the
    binoculars out of the routine's use set."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.binoculars = self.item('Binoculars')
        self.peep_trick_aux = False
        self.bino_aux = False

    def play_animation(self, name):
        super().play_animation(name)
        b = self.binoculars
        if b is None:
            return
        if self.peep_trick_aux:                       # cs:19-23
            self.peep_trick_aux = False
            if b.use_anim.get('Rottweiler'):
                b.use_anim['Rottweiler'][0] = 'RottLookNoBin'
        if self.bino_aux:                             # cs:24-28
            self.bino_aux = False
            self.hide_obj(b, False)
        if name == 'PeepTrick':                       # cs:29-33
            self.peep_trick_aux = True
            self.set_active(b, False)
        if name == 'PeepLoop':                        # cs:34-38
            self.hide_obj(b, True)
            self.bino_aux = True


class Level105Behavior(Behavior):
    """Level105Behavior.cs: the tricked football rewrites the piano's use to
    PlayPianoLong. The looping phone-ring AudioSource is outside the port's
    frame-keyed sound model; its gate flags are kept."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.piano = self.item('Piano')
        self.football = self.item('Football')
        self.phone_aux = False
        self.one_time = False
        self.can_play_audio = True

    def update(self, dt):
        w = self.world.woody
        if w is not None and w.anim.anim.name == 'MobileCall' \
                and not self.phone_aux and self.can_play_audio:
            self.phone_aux = True                     # cs:29-34 (audio on)
        if not self.one_time and self.football is not None \
                and self.football.got_tricked and self.piano is not None:
            self.piano.use_anim['Rottweiler'] = ['PlayPianoLong']   # cs:35-40
            self.one_time = True

    def play_animation(self, name):
        super().play_animation(name)
        if name == 'TalkPhone':                       # cs:58-63
            self.phone_aux = False
            self.can_play_audio = False
        else:
            self.can_play_audio = True


class Level105RoutineBehavior(Behavior):
    """Level105RoutineBehavior.cs: the piano visit closes the alarm gate,
    the walk to the stinking plant opens it."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.piano = self.item('Piano')
        self.plant_stink = self.item('PlantStink')

    def on_start_routine_action(self, item, action):
        if item is not None and item is self.piano:   # cs:9-16
            rt = self.routine('Rottweiler')
            if rt is not None:
                rt.alarm_next_action = False

    def on_move_to_routine_action(self, item, action):
        if item is not None and item is self.plant_stink:   # cs:18-25
            rt = self.routine('Rottweiler')
            if rt is not None:
                rt.alarm_next_action = True


class Level108Behavior(Behavior):
    """Level108Behavior.cs: the lotion bottle vanishes at frame 8 of the
    sun-bathing rub and returns with the next animation."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.sun_lotion = self.item('SunLotion')
        self.aux = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.aux:                                  # cs:19-24
            self.aux = False
            self.set_active(self.sun_lotion, True)

    def on_advance_frame(self, idx):
        if self.current_animation == 'SunBathLotion' and idx == 8 \
                and not self.aux:                     # cs:29-33
            self.aux = True
            self.set_active(self.sun_lotion, False)


class Level109Behavior(Behavior):
    """Level109Behavior.cs: the pig hides while being fed, and the tricked
    teeth cup empties at frame 5 of the take."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.teeth = self.item('Teeth')
        self.pig = self.item('Pig')
        self.teeth_aux = False
        self.pig_aux = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.teeth_aux:                            # cs:21-24
            self.teeth_aux = False
        if self.pig_aux:                              # cs:25-29
            self.pig_aux = False
            self.hide_obj(self.pig, False)
        if name == 'FeedPig':                         # cs:30-34
            self.pig_aux = True
            self.hide_obj(self.pig, True)

    def on_advance_frame(self, idx):
        rt = self.routine('Rottweiler')
        it = rt.item if rt is not None else None
        if (self.teeth is not None and self.teeth.tricked
                and self.current_animation == 'TakeInventory'
                and it is not None and it.name == 'Teeth' and idx == 5
                and rt.index - 1 > 0 and not self.teeth_aux):   # cs:40-44
            self.play_directly(self.teeth, 'TeethCupEmpty')
            self.teeth_aux = True


class Level110Behavior(Behavior):
    """Level110Behavior.cs: the steak table eats along with the neighbour."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.steak_table = self.item('SteakTable')
        self.last_was_eating = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.last_was_eating:                      # cs:10-13
            self.play_item(self.steak_table, 'SteakTableEmpty')
            self.last_was_eating = False
        if name == 'SitSteakEat':                     # cs:15-19
            self.last_was_eating = True
            self.play_item(self.steak_table, 'SteakTableEating')


class Level113Behavior(Behavior):
    """Level113Behavior.cs: the chair assembly saws itself once the book is
    swapped, and reappears when the neighbour misses it."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.chair = self.item('Chair')
        self.chair_book = self.item('ChairBook')
        self.chair_aux = False
        self.chair_angry_aux = False
        self.chair_not_found_aux = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.chair_aux:                            # cs:23-26
            self.chair_aux = False
        if self.chair_angry_aux:                      # cs:27-31
            self.chair_angry_aux = False
            self.play_looping(self.chair, 'ChairAssemblySAW')
        if name == 'ChairAssemblyElectric' and self.chair_book is not None \
                and self.chair_book.tricked and not self.chair_aux:  # cs:32-36
            self.chair_aux = True
            self.chair_angry_aux = True
        if self.chair_not_found_aux:                  # cs:37-40
            self.chair_not_found_aux = False
        if name == 'SurpriseNotFound' and not self.chair_not_found_aux:
            self.chair_not_found_aux = True           # cs:41-46
            self.hide_obj(self.chair, False)
            self.play_looping(self.chair, 'ChairAssembly')


class Level114Behavior(Behavior):
    """Level114Behavior.cs: the gramophone's needle-drop counter. Both arms
    only toggle looping AudioSources, which sit outside the port's
    frame-keyed sound model; the counter is kept for fidelity."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.gramaphone = self.item('Gramaphone')
        self.count = -1

    def play_animation(self, name):
        super().play_animation(name)
        it = self.action_item('Rottweiler')
        if it is None or it is not self.gramaphone or name != 'TakeInventory':
            return                                    # cs:63-66
        self.count += 1
        if self.count == 2:                           # cs:80-85
            self.count = -1


class Woody114Behavior(Behavior):
    """Woody114Behavior.cs: the whistle stops Woody in his tracks. The
    original's StopMovement pauses until the blocking animation ends
    (Woody.OnBlockingAnimationEnded -> ContinueMovement); the port kills the
    walk outright, which is the surviving effect."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.whistle_animation = self.anim_name('WhistleAnimation')

    def play_animation(self, name):
        super().play_animation(name)
        w = self.world.woody
        if name == self.whistle_animation and w is not None:   # cs:10-14
            w.steps = []
            w.state = w.IDLE


class VacuumBehavior(Behavior):
    """VacuumBehavior.cs: the vacuum trails the carpet-cleaning run — dust
    at frame 8 of the explosion, dust or vacuum-dust under the angry set,
    parked and hidden again when the neighbour walks off. The component is
    shared by the Rottweiler and the vacuum item, so both controllers feed
    PlayAnimation, exactly as in the original."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.vacuum = self.item('Vacuum')
        self.dirty = False
        self.start_cleaning = False

    def on_advance_frame(self, idx):
        if self.dirty and not self.start_cleaning and idx == 8:   # cs:14-19
            self.start_cleaning = True
            if self.vacuum is not None and self.vacuum.sprite is not None:
                self.vacuum.sprite.hidden = False
            self.play_looping(self.vacuum, 'CarpetDust')

    def play_animation(self, name):
        super().play_animation(name)
        if not self.enabled:                          # cs:25-28
            return
        if self.current_animation == 'VacuumDustExplosion':   # cs:29-31
            self.dirty = True
        elif self.dirty:
            if self.current_animation.startswith('Angry'):    # cs:35-37
                self.play_looping(self.vacuum, 'CarpetDustVacuum')
            elif self.current_animation == 'VacuumLoop':      # cs:39-41
                self.play_looping(self.vacuum, 'CarpetDust')
            elif self.current_animation == 'Walk_Right':      # cs:43-48
                self.enabled = False
                self.play_looping(self.vacuum, 'VacuumNormal')
                if self.vacuum is not None and self.vacuum.sprite is not None:
                    self.vacuum.sprite.hidden = True


class RollerSkaterBehavior(Behavior):
    """RollerSkaterBehavior.cs: the Level112 skate ride — SlideSkate slides
    the neighbour along x, the window swallows him (ScriptFreeze at the fall
    frame), four seconds later he re-enters at the street door, runs to the
    breath spot, shouts the skates off and resumes."""

    SKATE, FALL, COMEBACK, BREATH, SHOUT, FINAL = range(6)

    def __init__(self, world, d):
        super().__init__(world, d)
        self.enabled = False                          # driven by Start()
        self.window_x = self.value('WindowX', 0.0)
        self.fall_delay = self.value('FallDelay', 0.0)
        self.entrance_zone = self.zone('EntranceZone')
        self.entrance_location = self.vec('EntranceLocation')
        self.breath_zone = self.zone('BreathZone')
        self.breath_location = self.vec('BreathLocation')
        self.min_x_delta = self.value('MinXDelta', 0.3)
        self.velocity = self.vec('Velocity')
        self.fall_animation = self.anim_name('FallAnimation', 'FallWindow')
        self.breath_animation = self.anim_name('BreathAnimation', 'Breath')
        self.fall_hide_frame = self.value('FallHideFrame', 0)
        self.breath_end_frame = self.value('BreathEndFrame', 0)
        self.roller_skater = self.item('RollerSkater')
        self.fish = self.item('Fish')
        self.fish_aux = False
        self.state = self.FINAL
        self._fall_left = 0.0

    def play_animation(self, name):
        super().play_animation(name)
        if self.current_animation == 'SlideSkate':    # cs:55-57
            self._start()
        elif self.current_animation.startswith('Stand_') \
                and self._at(self.breath_location[0]) \
                and self.state == self.COMEBACK:      # cs:58-61
            self._breath()
        if self.fish_aux:                             # cs:63-67
            self.fish_aux = False
            self.set_active(self.fish, True)

    def on_advance_frame(self, idx):
        if self.state == self.FALL:
            if idx == self.fall_hide_frame:           # cs:73-79
                self._script_freeze()
        elif self.state == self.BREATH and idx == self.breath_end_frame:
            self._shout()                             # cs:80-83
        if idx == 1 and self.current_animation == 'FeedFish' \
                and not self.fish_aux:                # cs:84-88
            self.fish_aux = True
            self.set_active(self.fish, False)

    def on_animation_sequence_ended(self):
        if self.state == self.SHOUT:                  # cs:91-98
            self._end()

    def update(self, dt):
        rott = self.rott()
        if rott is None:
            return
        if self.state == self.SKATE:                  # cs:106-118
            if self._at(self.window_x):
                self._fall()
            else:
                rott.sprite.x += self.velocity[0] * dt
                rott.sprite.y += self.velocity[1] * dt
        elif self.state == self.FALL and self._fall_left > 0.0:   # cs:119-128
            self._fall_left -= dt
            if self._fall_left <= 0.0:
                self._come_back()

    def can_see_woody(self):
        """cs:147-154: he cannot spot Woody from inside the wall"""
        return self.state not in (self.FALL, self.COMEBACK)

    def on_caught_woody(self):
        self._end()                                   # cs:156-159

    def _at(self, x):
        rott = self.rott()
        return rott is not None and abs(rott.sprite.x - x) < self.min_x_delta

    def _start(self):
        if not self.enabled:                          # cs:132-140
            self.state = self.SKATE
            self.enabled = True
            self.hide_obj(self.roller_skater, True)   # SetActiveObjectHidden

    def _fall(self):
        self.state = self.FALL                        # cs:161-166
        self._fall_left = self.fall_delay
        rott = self.rott()
        if rott is not None and rott.anim.has(self.fall_animation):
            rott.anim.play_single(self.fall_animation)
        rt = self.routine('Rottweiler')
        if rt is not None:
            rt.postpone_alarm()                       # Rottweiler.PostponeAlarm

    def _script_freeze(self):
        """Rottweiler.ScriptFreeze (Rottweiler.cs:1205-1209)"""
        rott = self.rott()
        rt = self.routine('Rottweiler')
        if rott is not None:
            rott.sprite.hidden = True                 # AnimController.Hidden
        if rt is not None:
            rt.frozen = True                          # ActionManager.Freeze

    def _come_back(self):
        self.state = self.COMEBACK                    # cs:168-179
        rott = self.rott()
        if rott is None:
            return
        rott.sprite.hidden = False
        rott.movement_paused = False                  # ContinueMovement
        rott.sprite.x, rott.sprite.y = self.entrance_location
        rott.pos_snap = True
        if self.entrance_zone is not None:
            rott.zone = self.entrance_zone
        if self.breath_zone is not None:
            rott.in_urgent = True                     # MoveToGoalUrgent
            rott.goto_zone(self.breath_zone, self.breath_location[0])

    def _breath(self):
        self.state = self.BREATH                      # cs:181-185
        rott = self.rott()
        if rott is not None and rott.anim.has(self.breath_animation):
            rott.anim.play_single(self.breath_animation)

    def _shout(self):
        self.state = self.SHOUT                       # cs:187-192
        rott = self.rott()
        if rott is not None and self.roller_skater is not None:
            self.world.play_angry(rott, self.roller_skater)
            self.world._fix(self.roller_skater)       # RollerSkater.Fix()

    def _end(self):
        self.state = self.FINAL                       # cs:194-200
        self.enabled = False
        rott = self.rott()
        rt = self.routine('Rottweiler')
        if rott is not None:                          # Rottweiler.ScriptUnfreeze
            rott.movement_paused = False
            rott.sprite.hidden = False
        if rt is not None:
            rt.frozen = False
            rt._pending = 'first'                     # Unfreeze -> StartNextAction
            rt.continue_alarm()                       # Rottweiler.ContinueAlarm


class TrickProgressBarBehavior(Behavior):
    """TrickProgressBarBehavior.cs (Level102's sofa saw): toggles the
    TrickProgressBar object with the SawSofa animation. The bar's own
    ProgressBarTrick rendering is the unported progress-bar HUD; the state
    flag is kept."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.target = self.item('Item')
        self.is_playing = False

    def play_animation(self, name):
        super().play_animation(name)
        if name == 'SawSofa':                         # cs:12-19
            if not self.is_playing:
                self.is_playing = True
        elif self.is_playing:                         # cs:20-24
            self.is_playing = False


# ---------------------------------------------------------------------------
# Season 2
# ---------------------------------------------------------------------------

class Level201Behavior(Behavior):
    """Level201Behavior.cs: Olga slips behind the fence for the buffet gags."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.olga = self.pawn('Olga')
        self.table_aux = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.table_aux:                            # cs:18-21
            self.depth(self.olga, 'FrontDoors')
            self.table_aux = False
        if name in ('BuffetFlirt', 'BuffetCrash'):    # cs:23-27
            self.depth(self.olga, 'LevelFence')
            self.table_aux = True


class Level202Behavior(Behavior):
    """Level202Behavior.cs: the bridge rail reappears after the look/leave
    sequences drain."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.bridge_rail = self.item('BridgeRail')
        self.toggle_look = False
        self.toggle_leave = False

    def play_animation(self, name):
        if name == 'BridgeLook':                      # cs:11-13
            self.toggle_look = True
        if name == 'BridgeLeave':                     # cs:15-17
            self.toggle_leave = True
        super().play_animation(name)

    def on_animation_sequence_ended(self):
        if self.toggle_look:                          # cs:25-29
            self.hide_obj(self.bridge_rail, False)
            self.toggle_look = False
        if self.toggle_leave:                         # cs:30-34
            self.hide_obj(self.bridge_rail, False)
            self.toggle_leave = False


class Level204Behavior(Behavior):
    """Level204Behavior.cs: the kart-pull shuffles Olga and the neighbour,
    and the tricked jade necklace plays its pose at frame 1 of the crash."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.olga = self.pawn('Olga')
        self.rottweiler = self.pawn('Rottweiler')
        self.kart = self.item('Kart')
        self.jade = self.item('JadeNeckless')
        self.olga_new_position = (-1.0, 0.0)          # ctor, cs:29
        self.rott_pos = (-1.0, 0.0)                   # ctor, cs:30
        self.rott_pos_aux = False
        self.jade_tricked = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.rott_pos_aux:                         # cs:44-49
            self.rott_pos_aux = False
            if self.rottweiler is not None:
                self.rottweiler.sprite.x += self.rott_pos[0]
                self.rottweiler.sprite.y += self.rott_pos[1]
                self.rottweiler.pos_snap = True
        if name == 'CartPullGrease' and self.olga is not None:   # cs:50-54
            self.olga.sprite.x += self.olga_new_position[0]
            self.olga.pos_snap = True
            self.olga.sprite.y += self.olga_new_position[1]
        if name == 'WaitInFear':                      # cs:55-59
            self.hide_obj(self.kart, False)
            self.rott_pos_aux = True
        if name in ('VaseCrash', 'VaseCrashLong') and self.jade is not None \
                and self.jade.tricked:                # cs:60-63
            self.jade_tricked = True

    def on_advance_frame(self, idx):
        if self.jade_tricked and idx == 1:            # cs:74-78
            self.play_item(self.jade, 'N2TrickItemUseNormal')
            self.jade_tricked = False


class Level204OlgaBehavior(Behavior):
    """Level204OlgaBehavior.cs: the HitPawn parks Olga frozen at the kart
    until the neighbour's FixMid lets her routine go again."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.olga = self.pawn('Olga')
        self.rottweiler = self.pawn('Rottweiler')
        self.olga_pos = (-4.314246, -3.751539)        # ctor, cs:23
        self.hit_pawn_flag = False
        self.olga_kart_ready = False
        self.go_back_to_kart = False

    def play_animation(self, name):
        super().play_animation(name)
        rt = self.routine_of(self.olga) if self.olga is not None else None
        if self.hit_pawn_flag:                        # cs:31-38
            self.hit_pawn_flag = False
            if rt is not None:
                rt.frozen = True                      # ActionManager.Frozen
            if self.olga is not None:
                st = self.olga._stand_name()          # SwitchToStandAnimation
                if st:
                    self.olga.anim.play_looping(st)
                self.olga.sprite.x, self.olga.sprite.y = self.olga_pos
                self.olga.pos_snap = True
            self.olga_kart_ready = True
        if self.go_back_to_kart:                      # cs:39-43
            self.go_back_to_kart = False
            if rt is not None:
                rt.frozen = False
        if name == 'HitPawn':                         # cs:44-47
            self.hit_pawn_flag = True

    def update(self, dt):
        rott = self.rottweiler
        if rott is not None and rott.anim.anim.name == 'FixMid' \
                and self.olga_kart_ready:             # cs:50-57
            self.olga_kart_ready = False
            self.go_back_to_kart = True


class Level206Behavior(Behavior):
    """Level206Behavior.cs: Fifi rides the harpoon — the tricked launch pad
    re-poses the search-item Fifi, the fire hides her, WaitInFear brings her
    down tricked, and the fix resets the cycle."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.launch_pad = self.item('LaunchPad')
        self.fifi_harpoon = self.item('FifiHarpoon')
        self.one_time = False
        self.fifi_tricked = False
        self.fifi_tricked1 = False
        self.fix_launch_pad = False
        self.fix_launch_pad1 = False

    def update(self, dt):
        if self.launch_pad is not None and self.launch_pad.tricked \
                and not self.one_time:                # cs:25-31
            self.one_time = True
            if self.fifi_harpoon is not None:
                self.fifi_harpoon.primed_animation = 'N2TrickItemExtra1'
                self.depth(self.fifi_harpoon, 'LevelFence')
            self.fifi_tricked = True

    def play_animation(self, name):
        super().play_animation(name)
        f = self.fifi_harpoon
        if self.fix_launch_pad1:                      # cs:38-41
            self.fix_launch_pad1 = False
            self.one_time = False
        if self.fifi_tricked1 and name == 'WaitInFear' and f is not None:
            self.fifi_tricked1 = False                # cs:43-50
            f.primed_animation = 'N2TrickItemIdleTricked'
            self.hide_obj(f, False)
            self.play_directly(f, f.primed_animation)
            self.fix_launch_pad = True
        if self.fix_launch_pad and name == 'FixMid':  # cs:51-55
            self.fix_launch_pad = False
            self.fix_launch_pad1 = True
        if self.fifi_tricked and name in ('FifiFire', 'FifiFireManip') \
                and f is not None:                    # cs:56-62
            self.depth(f, 'Items')
            self.fifi_tricked = False
            self.hide_obj(f, True)
            self.fifi_tricked1 = True


class Level206MotherBehavior(Behavior):
    """Level206MotherBehavior.cs: the second MotherHitNeighbor onwards shifts
    two of the Mother's animation offsets."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.second_time = 0

    def play_animation(self, name):
        if name == 'MotherHitNeighbor':               # cs:11-18
            self.second_time += 1
            if self.second_time >= 2:
                self._adjust()

    def _adjust(self):
        """cs:21-30: Animations[23].DeltaLocation = (-12.5, -6.1),
        Animations[33].DeltaLocation.y = -5.7 — by the serialized index"""
        mother = self.world.pawns.get('Mother')
        if mother is None:
            return
        for a in mother.sprite.anims:
            if a.src_index == 23:
                a.dx = -12.5
                a.dy = -6.1
            elif a.src_index == 33:
                a.dy = -5.7


class Level206RoutineBehavior(Behavior):
    """Level206RoutineBehavior.cs: every third launch-pad visit after a trick
    clears GotTricked and re-arms the pad."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.launch_pad = self.item('LaunchPad')
        self.aux = False
        self.launch_count = 0

    def on_start_routine_action(self, item, action):
        lp = self.launch_pad
        if lp is None:
            return
        if item is lp:                                # cs:15-17
            self.launch_count += 1
        if item is lp and lp.tricked:                 # cs:19-21
            self.aux = True
        if self.aux and item is lp and self.launch_count == 3:   # cs:23-29
            self.aux = False
            self.launch_count = 0
            lp.got_tricked = False
            lp.used = False                           # SetUnUsed
        if self.launch_count == 3:                    # cs:30-33
            self.launch_count = 0


class Level207MotherBehavior(Behavior):
    """Level207MotherBehavior.cs: the Mother on the pool ladder swaps the
    pool board's use sets to the WaitWatch-prefixed versions, and frame 49 of
    her leave releases the neighbour's infinite wait and restores them."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.poolboard = self.item('Poolboard')
        self.aux = False

    def play_animation(self, name):
        if name == 'MotherPoolLadderEnter' and self.poolboard is not None:
            self.poolboard.use_anim['Rottweiler'] = [        # cs:9-30
                'WaitWatch', 'PoolDive', 'PoolGetOut']
            self.poolboard.use_tricked_anim['Rottweiler'] = [
                'WaitWatch', 'PoolSpring', 'PoolAwningFall', 'PoolGetOut']
            self.poolboard.use_tricked_linked = [
                'WaitWatch', 'PoolSpring', 'CrashMother']
        if name == 'MotherPoolLadderLeave':           # cs:31-34
            self.aux = True

    def on_advance_frame(self, idx):
        if self.aux and idx == 49:                    # cs:38-59
            self.aux = False
            rott = self.rott()
            if rott is not None:
                rott.anim.ignore_infinite = True      # SetIgnoreInfiniteLoopOnce
                rott.anim.ignore_infinite_once = True
            if self.poolboard is not None:
                self.poolboard.use_anim['Rottweiler'] = [
                    'PoolDive', 'PoolGetOut']
                self.poolboard.use_tricked_anim['Rottweiler'] = [
                    'PoolSpring', 'PoolAwningFall', 'PoolGetOut']
                self.poolboard.use_tricked_linked = [
                    'PoolSpring', 'CrashMother']


class Level208Behaviors(Behavior):
    """Level208Behaviors.cs (the scene Level209 wires it): a show/hide script
    for the fakir yard — fire channel, hot shoe, Tadj Mahal, drain, coal
    trough, cow — plus the cow-crap collider windows."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.fire_channel = self.item('FireChannel')
        self.hot_shoe = self.item('HotShoe')
        self.tadj_mahal = self.item('TadjMahal')
        self.drain = self.item('Drain')
        self.coal = self.item('Coal')
        self.though = self.item('Though')
        self.cow = self.item('Cow')
        self.cow_crap = self.item('CowCrap')
        self.fire_channel_hide = False
        self.shoe_aux = False
        self.drain_aux = False
        self.coal_aux = False
        self.cow_aux = False
        self.cow_get_up_aux = False
        self.cow_get_up_aux1 = False
        self.cow_crap_aux = False
        self.cow_crap_aux1 = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.fire_channel_hide:                    # cs:45-49
            self.hide_obj(self.fire_channel, False)
            self.fire_channel_hide = False
        if self.shoe_aux:                             # cs:50-54
            self.hide_obj(self.hot_shoe, False)
            self.shoe_aux = False
        if self.drain_aux:                            # cs:55-59
            self.hide_obj(self.drain, False)
            self.drain_aux = False
        if self.coal_aux:                             # cs:60-65
            self.coal_aux = False
            self.hide_obj(self.though, False)
            self.hide_obj(self.coal, False)
        if self.cow_aux:                              # cs:66-70
            self.cow_aux = False
            self.hide_obj(self.cow, False)
        if self.cow_get_up_aux1 and self.cow is not None:   # cs:71-74
            self.play_directly(self.cow, self.cow.idle)
        if self.cow_get_up_aux:                       # cs:75-80
            self.cow_get_up_aux = False
            self.play_directly(self.cow, 'N2TrickItemUseNormal')
            self.cow_get_up_aux1 = True
        if name == 'FireChannelBurn':                 # cs:81-84
            self.fire_channel_hide = True
        if name in ('ShoeOff', 'ShoeOn'):             # cs:85-89
            self.hide_obj(self.hot_shoe, True)
            self.shoe_aux = True
        if name == 'TadjMahalEnter':                  # cs:90-93
            self.hide_obj(self.tadj_mahal, True)
        if name in ('DrainJump', 'DrainOpenJump'):    # cs:94-100
            self.hide_obj(self.hot_shoe, False)
            self.play_looping(self.hot_shoe, 'N2TrickItemIdleNormal')
            self.hide_obj(self.drain, True)
            self.drain_aux = True
        if name in ('CoalWalk', 'CoalFuelWalk', 'CoalHotFuelWalk',
                    'CoalHotWalk'):                   # cs:101-106
            self.coal_aux = True
            self.hide_obj(self.though, True)
            self.hide_obj(self.coal, True)
        if name == 'CowCrash':                        # cs:107-111
            self.hide_obj(self.cow, True)
            self.cow_aux = True
        if name == 'CowRide':                         # cs:112-115
            self.cow_get_up_aux = True

    def on_advance_frame(self, idx):
        cow = self.cow
        crap = self.cow_crap
        if cow is None or crap is None:
            return
        p = self.player(cow)
        cur = p.anim.name if p is not None else None
        cur_frame = p.frame if p is not None else -1
        if cur in ('N2TrickItemPrimedNormal', 'N2TrickItemPrimedTricked') \
                and cur_frame == 27 and not self.cow_crap_aux:   # cs:121-126
            self.cow_crap_aux = True
            self.collider(crap, True)
            self.cow_crap_aux1 = False
        if not crap.clickable and not self.cow_crap_aux1:        # cs:127-131
            self.cow_crap_aux = False
            self.cow_crap_aux1 = True


class Level210Behavior(Behavior):
    """Level210Behavior.cs: the turban-shop Fifi hand-off, the dog basket's
    tickle/take/put cycle, the elephant-Fifi appearance, and the cricket-bat
    disappearance."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.elephant = self.item('Elephant')
        self.cricket_bat = self.item('CricketBat')
        self.fifi_elephant = self.item('FifiElephant')
        self.turban_shop = self.item('TurbanShop')
        self.dog_basket = self.item('DogBasket')
        self.fifi_turban = self.item('FifiTurban')
        self.fifi_prime_aux = False
        self.cricket_aux = False
        self.dog_basket_aux = False
        self.dog_basket_aux1 = False
        self.basket_got_tricked = False
        self.angry_colapse = False
        self.linked_trick_dog = False
        self.dont_trick = False
        self.put_dog_normal = False
        self.show_fifi = False
        self.turban_shop_aux = False
        self.fifi_elephant_aux = False
        self.fix_aux = False

    def play_animation(self, name):
        super().play_animation(name)
        it = self.action_item('Rottweiler')
        if it is not None and it is self.turban_shop:   # cs:51-61
            if name == 'FifiPutLeft':
                self.fifi_prime_aux = True
            elif name == 'FifiTakeLeft':
                self.hide_obj(self.fifi_turban, True)
        db = self.dog_basket
        if self.dog_basket_aux1 and db is not None:   # cs:62-68
            self.dog_basket_aux1 = False
            self.world.set_primed(db, True)
            self.hide_obj(db, False)
            self.play_directly(db, 'N2TrickItemIdleTricked')
        if self.angry_colapse:                        # cs:69-73
            self.angry_colapse = False
            self.hide_obj(db, False)
        if self.dog_basket_aux and db is not None:    # cs:74-80
            self.dog_basket_aux = False
            self.hide_obj(db, False)
            self.play_directly(db, 'N2TrickItemIdleTricked')
            self.angry_colapse = True
        if self.turban_shop_aux:                      # cs:81-85
            self.turban_shop_aux = False
            self.hide_obj(self.turban_shop, False)
        if self.linked_trick_dog:                     # cs:86-89
            self.hide_obj(db, False)
        if self.put_dog_normal:                       # cs:90-93
            self.put_dog_normal = False
        if self.show_fifi and db is not None:         # cs:94-99
            self.show_fifi = False
            self.hide_obj(db, False)
            self.world.set_primed(db, True)
        if self.fix_aux:                              # cs:100-104
            self.fix_aux = False
            self.hide_obj(self.fifi_elephant, True)
        if name == 'Stand_Right' and self.elephant is not None \
                and self.elephant.tricked and self.cricket_bat is not None \
                and self.cricket_bat.tricked:         # cs:105-110
            self.cricket_aux = True
            self.hide_obj(self.cricket_bat, True)
            self.collider(self.cricket_bat, False)
        if name == 'RottTickle' and db is not None and db.tricked:  # cs:111-116
            self.play_directly(db, 'N2TrickItemExtra1')
            self.dog_basket_aux = True
            self.basket_got_tricked = True
        rt_item = self.action_item('Rottweiler')
        if name == 'FifiTakeRight' and self.basket_got_tricked \
                and db is not None:                   # cs:117-136
            self.basket_got_tricked = False
            self.world.set_primed(db, False)
            self.hide_obj(db, False)
            if not self.dont_trick:
                db.tricked = True
                self.play_directly(db, 'N2TrickItemExtra2')
            else:
                self.hide_obj(db, True)
                self.put_dog_normal = True
            if self.linked_trick_dog:
                self.linked_trick_dog = False
        if name == 'FifiPutRight' and db is not None and rt_item is not None \
                and rt_item.name == 'DogBasketPut':   # cs:137-144
            if db.tricked:
                self.dog_basket_aux1 = True
            else:
                self.show_fifi = True
        if name in ('PoolFallWater', 'PoolFallEmpty') and db is not None \
                and db.tricked:                       # cs:145-149
            self.linked_trick_dog = True
            rott = self.rott()
            if rott is not None:
                rott.has_fifi = False                 # SetHasFifi(false)
        if name == 'PoolFallEmpty' and db is not None and db.tricked:
            self.dont_trick = True                    # cs:150-153
        if name == 'RottLookAroundFifi' and self.elephant is not None \
                and self.elephant.tricked and self.cricket_bat is not None \
                and self.cricket_bat.tricked and not self.fifi_elephant_aux:
            self.set_active(self.fifi_elephant, True)   # cs:154-159
            self.play_directly(self.fifi_elephant, 'N2TrickItemIdleNormal')
            self.fifi_elephant_aux = True
        if self.fifi_elephant_aux and name == 'FixMid' \
                and self.elephant is not None and self.elephant.tricked \
                and self.cricket_bat is not None and self.cricket_bat.tricked:
            self.fifi_elephant_aux = False            # cs:160-164
            self.fix_aux = True
        if name in ('ShopTryHedgehog', 'ShopTryOctopus') \
                and self.turban_shop is not None and self.turban_shop.tricked:
            self.hide_obj(self.turban_shop, True)     # cs:165-177
            if name == 'ShopTryHedgehog':
                self.play_directly(self.turban_shop, 'N2TrickItemIdleNormal')
            else:
                self.play_directly(self.turban_shop, 'N2TrickItemIdleFuckedup')
            self.turban_shop_aux = True

    def on_advance_frame(self, idx):
        if self.fifi_prime_aux and idx == 12:         # cs:183-188
            self.fifi_prime_aux = False
            self.hide_obj(self.fifi_turban, True)
            if self.fifi_turban is not None:
                self.world.set_primed(self.fifi_turban, True)   # FifiPrime


class Level211Behavior(Behavior):
    """Level211Behavior.cs: the sea-side toilets, the fall-boat pose swap and
    the kid's depth dance around Olga's puke run."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.toilet_men = self.item('ToiletMen')
        self.kid = self.item('Kid')
        self.olga = self.pawn('Olga')
        self.boat = self.item('Boat')
        self.toilet_men_aux = False
        self.wait_in_fear_aux = False
        self.boat_aux = False
        self.show_boat = False
        self.boat_aux2 = False
        self.cont = 0

    def play_animation(self, name):
        super().play_animation(name)
        if self.toilet_men_aux:                       # cs:35-39
            self.toilet_men_aux = False
            self.hide_obj(self.toilet_men, False)
        if self.boat_aux and self.boat is not None:   # cs:40-49
            self.play_directly(self.boat, self.boat.idle)
            self.collider(self.boat, False)
            self.boat_aux = False
        if self.boat_aux2:                            # cs:50-54
            self.boat_aux2 = False
            self.hide_obj(self.boat, False)
        if self.show_boat:                            # cs:55-60
            self.show_boat = False
            self.hide_obj(self.boat, True)
            self.boat_aux2 = True
        if name == 'PukeFemale':                      # cs:61-65
            if self.olga is not None:
                self.olga.set_hidden(True)
            self.depth(self.kid, 'LevelFence')
        if self.olga is not None \
                and self.olga.anim.anim.name == 'HitPawn':   # cs:66-69
            self.depth(self.kid, 'FrontDoors')
        if name == 'WaitInFear2' and self.olga is not None:  # cs:70-73
            self.olga.set_hidden(False)
        if name == 'PukeMale':                        # cs:74-78
            self.hide_obj(self.toilet_men, True)
            self.toilet_men_aux = True
        if name == 'FallBoat' and self.boat is not None:     # cs:79-83
            self.boat_aux = True
            self.boat.idle = 'N2TrickItemIdleFuckedup'
        if name == 'LookAround':                      # cs:84-88
            self.show_boat = True
            self.hide_obj(self.boat, False)

    def on_advance_frame(self, idx):
        if idx == 3 and self.current_animation == 'WaitInFear2':   # cs:94-101
            self.cont += 1
            if self.cont == 7:
                self.depth(self.kid, 'Alerters')


class Level211LifeBoatBehavior(Behavior):
    """Level211LifeBoatBehavior.cs: getting caught during the life-boat
    action brings the boat back into view, for good."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.life_boat = self.item('LifeBoat')
        self.caught_woody = False                     # Start(), cs:9-12

    def on_caught_woody(self):
        it = self.action_item('Rottweiler')
        if it is not None and it is self.life_boat:   # cs:14-23
            self.play_item(self.life_boat, 'N2TrickItemIdleNormal')
            self.hide_obj(self.life_boat, False)
            self.caught_woody = True

    def update(self, dt):
        if self.caught_woody:                         # cs:25-31
            self.hide_obj(self.life_boat, False)


class Level212Behavior(Behavior):
    """Level212Behavior.cs: both branches are empty in the shipped build —
    the CowCrash check guards a no-op."""


class Level213Behavior(Behavior):
    """Level213Behavior.cs: depth choreography for the picnic boat and the
    mechanical-bull activation."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.bull = self.item('Bull')
        self.bull_controls = self.item('BullControls')
        self.olga = self.pawn('Olga')
        self.rottweiler = self.pawn('Rottweiler')
        self.one_time = False
        self.olga_picnic_left_aux = False
        self.rott_leave = False
        self.rott_left = False
        self.bull_visible = False
        self.controls_aux = False

    def update(self, dt):
        if self.olga is None:
            return
        cur = self.olga.anim.anim.name
        if cur == 'PicnicEnter' and not self.one_time:       # cs:33-37
            self.one_time = True
            self.depth(self.olga, 'LevelFence')
        if cur == 'PicnicLeave' and not self.olga_picnic_left_aux:  # cs:38-42
            self.olga_picnic_left_aux = True
            self.depth(self.olga, 'LevelFence')
        if cur == 'Walk_Left' and self.olga_picnic_left_aux:  # cs:43-47
            self.depth(self.olga, 'Alerters')

    def play_animation(self, name):
        super().play_animation(name)
        if self.rott_left:                            # cs:53-58
            self.rott_left = False
            self.one_time = False
            self.depth(self.olga, 'Alerters')
        if self.bull_visible:                         # cs:59-62
            self.bull_visible = False
        if self.controls_aux:                         # cs:63-67
            self.controls_aux = False
            self.hide_obj(self.bull_controls, False)
        if self.rott_leave and name != 'PicnicLeave':  # cs:68-73
            self.rott_leave = False
            self.depth(self.rottweiler, 'Rottweiler')
            self.rott_left = True
        if name in ('PicnicEnter', 'PicnicCrash'):    # cs:74-78
            self.depth(self.rottweiler, 'LevelFence')
            self.rott_leave = True
        if name == 'BullActivateManip' and not self.bull_visible:  # cs:79-85
            self.hide_obj(self.bull_controls, True)
            self.hide_obj(self.bull, True)
            self.bull_visible = True
            self.controls_aux = True


class Level213OlgaBehavior(Behavior):
    """Level213OlgaBehavior.cs: Olga's bull crash and workout depths."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.bull = self.item('Bull')
        self.bull_controls = self.item('BullControls')
        self.bull_aux = False
        self.olga_hit = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.bull_aux:                             # cs:20-24
            self.bull_aux = False
            self.hide_obj(self.bull, False)
        if self.olga_hit:                             # cs:25-29
            self.olga_hit = False
            self.depth(self.bull_controls, 'FrontDoors')
        if name == 'BullCrash':                       # cs:30-32
            self.bull_aux = True
        if name == 'Workout':                         # cs:34-37
            self.depth(self.world.pawns.get('Olga'), 'LevelFenceBack')
        if name == 'HitPawn' and self.bull is not None and self.bull.tricked:
            self.olga_hit = True                      # cs:38-42
            self.depth(self.bull_controls, 'Items')


class FifiBehavior(Behavior):
    """FifiBehavior.cs: the tricked Fifi bone walks the take-Fifi figure
    across the yard; the fix walks everything back."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.fifi = self.item('Fifi')
        self.take_fifi = self.item('TakeFifi')
        self.speed = self.value('FifiSpeed', 1.0)
        self.start_position = (5.09, -3.049)          # ctor, cs:30
        self.end_position = (-1.0, -3.049)            # ctor, cs:31
        self.fifi_tricked = False
        self.play_animation_aux = False
        self.after_fix = False

    def _move_towards(self, dt):
        """Vector3.MoveTowards for the take-Fifi transform + its sprite"""
        tf = self.take_fifi
        step = self.speed * dt
        dx = self.end_position[0] - tf.x
        dy = self.end_position[1] - tf.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= step or dist == 0.0:
            nx, ny = self.end_position
        else:
            nx = tf.x + dx / dist * step
            ny = tf.y + dy / dist * step
        if tf.sprite is not None:
            tf.sprite.x += nx - tf.x
            tf.sprite.y += ny - tf.y
        tf.x, tf.y = nx, ny

    def update(self, dt):
        f, tf = self.fifi, self.take_fifi
        if f is None or tf is None:
            return
        if f.tricked and not self.fifi_tricked:       # cs:42-52
            if not self.play_animation_aux:
                self.hide_obj(tf, False)
                f.use_once = True
                self.play_looping(tf, 'N2TrickItemExtra1')
                self.play_animation_aux = True
            if (tf.x, tf.y) == self.end_position:     # StartMovement, cs:86-105
                self.fifi_tricked = True
                self.play_looping(tf, 'N2TrickItemExtra2')
            else:
                self._move_towards(dt)
        elif not f.tricked:                           # cs:53-59
            f.use_once = False
            self.play_animation_aux = False
            self.fifi_tricked = False
            if tf.sprite is not None:
                tf.sprite.x += self.start_position[0] - tf.x
                tf.sprite.y += self.start_position[1] - tf.y
            tf.x, tf.y = self.start_position

    def play_animation(self, name):
        super().play_animation(name)
        f, tf = self.fifi, self.take_fifi
        if self.after_fix:                            # cs:64-69
            self.after_fix = False
            if f is not None:
                self.play_looping(f, f.idle)
            self.hide_obj(tf, True)
        if name == 'FifiTakeLeft' and f is not None and f.tricked:  # cs:70-72
            self.hide_obj(tf, True)
        elif name == 'FixLow':                        # cs:74-78
            self.after_fix = True
            self.hide_obj(tf, False)


class SandCastleBehavior(Behavior):
    """SandCastleBehavior.cs: the sand-castle build — beach logo / castle
    swap, the kid's crying, and the depth dance around Olga's lift."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.destroy_castle_animation = self.anim_name('DestroyCastleAnimation')
        self.beach_logo = self.item('BeachLogo')
        self.sand_castle = self.item('SandCastle')
        self.same_zone = self.zone('SameZone')
        self.rott_angry_pos = (-2.5, -0.5)            # ctor, cs:33
        self.is_beach_logo_anim = False
        self.olga_update_aux = False
        self.kid_update_aux = False

    def update(self, dt):
        rott = self.rott()
        olga = self.world.pawns.get('Olga')
        kid = self.world.pawns.get('Kid')
        if rott is None or olga is None:
            return
        if self.same_zone is not None and rott.zone is self.same_zone \
                and olga.zone is rott.zone:           # cs:39-48
            self.depth(olga, 'LevelFence')
            self.olga_update_aux = True
        elif self.olga_update_aux:
            self.depth(olga, 'Alerters')
            self.olga_update_aux = False
        if olga.anim.anim.name == 'SandCastleLiftOlga' and kid is not None:
            self.depth(kid, 'BackHUD')                # cs:49-53
            self.kid_update_aux = True
        elif self.kid_update_aux and kid is not None:  # cs:54-58
            self.depth(kid, 'FrontDoors')
            self.kid_update_aux = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.is_beach_logo_anim:                   # cs:68-78
            self.is_beach_logo_anim = False
            self.hide_obj(self.beach_logo, False)
            if self.beach_logo is not None:
                self.world.set_primed(self.beach_logo, True)
            if self.sand_castle is not None:
                self.sand_castle.locked = True
            rott = self.rott()
            if rott is not None:
                rott.sprite.x += self.rott_angry_pos[0]
                rott.sprite.y += self.rott_angry_pos[1]
                rott.pos_snap = True
            rt = self.routine('Rottweiler')
            if rt is not None and len(rt.actions) > 4:
                rt.actions.pop(4)                     # RemoveActionByIndex(4)
                rt.index -= 1                         # ActiveActionIndex--
        if name == self.destroy_castle_animation:     # cs:79-82
            self.world.kid_start_crying()             # Kid.StartCrying
        if name == 'BeachLogo':                       # cs:83-89
            self.hide_obj(self.beach_logo, True)
            self.hide_obj(self.sand_castle, False)
            if self.sand_castle is not None:
                self.world.set_primed(self.sand_castle, True)
            self.is_beach_logo_anim = True
        if name == 'SandCastleFall':                  # cs:90-93
            self.depth(self.world.pawns.get('Kid'), 'Rottweiler')

    def on_advance_frame(self, idx):
        if idx == 8 and self.current_animation == 'SplashCrayfish':  # cs:99-102
            self.play_looping(self.sand_castle, 'N2TrickItemIdleNormal')


class SkiBehavior(Behavior):
    """SkiBehavior.cs: the ski-lift ride slides the neighbour back and forth
    across the slope; the nail trick swaps the aux skis in."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.enabled = False                          # driven by StartBehavior
        self.ski_normal = self.anim_name('SkiNormal', 'Ski')
        self.ski_tricked = self.anim_name('SkiTricked', 'SkiNail')
        self.ski_return = self.anim_name('SkiReturn', 'SkiHandleReturn')
        self.ski_return_nail = self.anim_name('SkiReturnNail',
                                              'SkiHandleReturnNail')
        self.skii_aux = self.item('SkiiAux')
        self.start_x = self.value('StartX', -10.5)
        self.end_x = self.value('EndX', 7.0)
        self.right_velocity = self.vec('RightVelocity', (2.4, 0.0))
        self.left_velocity = self.vec('LeftVelocity', (-2.4, 0.0))
        self.rott_pos_aux = (-5.745195, -1.984)       # ctor, cs:55
        self.velocity = (0.0, 0.0)
        self.original_position = (0.0, 0.0)
        self.ski_aux = False
        self.ski_aux1 = False
        self.sky_nail = False

    def play_animation(self, name):
        super().play_animation(name)
        if name in (self.ski_normal, self.ski_tricked):      # cs:63-66
            self._start()
        elif name in (self.ski_return, self.ski_return_nail):  # cs:67-70
            self._stop()
        rott = self.rott()
        if self.ski_aux1:                             # cs:71-76
            self.ski_aux1 = False
            if rott is not None:
                rott.sprite.x, rott.sprite.y = self.rott_pos_aux
                rott.pos_snap = True
            self.set_active(self.skii_aux, False)
        if self.sky_nail:                             # cs:77-81
            self.sky_nail = False
            self.set_active(self.skii_aux, True)
        if name == 'SkiStartNail':                    # cs:82-84
            self.ski_aux = True
        if name == 'FixMid' and self.ski_aux:         # cs:86-90
            self.ski_aux = False
            self.ski_aux1 = True
        if name == 'SkiStartNail':                    # cs:91-94
            self.sky_nail = True

    def _start(self):
        """cs:104-120"""
        rott = self.rott()
        if rott is None:
            return
        self.enabled = True
        self.original_position = (rott.sprite.x, rott.sprite.y)
        rott.sprite.x = self.start_x
        rott.pos_snap = True
        self.velocity = self.right_velocity

    def _stop(self):
        """cs:97-102"""
        rott = self.rott()
        self.enabled = False
        if rott is not None:
            rott.sprite.x, rott.sprite.y = self.original_position
            rott.pos_snap = True

    def update(self, dt):
        rott = self.rott()
        if rott is None:
            return
        rott.sprite.x += self.velocity[0] * dt        # cs:122-143
        rott.sprite.y += self.velocity[1] * dt
        if rott.sprite.x > self.end_x:
            self.velocity = self.left_velocity
        elif rott.sprite.x < self.start_x:
            self._stop()


class BirdMovementBehavior(Behavior):
    """BirdMovementBehavior.cs: the unwired free-running bird — it flies off
    when someone enters its zone and returns when the zone clears; a tricked
    glass grounds it for good. The original schedules a MoveTowards step per
    Update through Invoke(DelayTimeToMove); the port keeps the delay queue."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.bird = self.item('Bird')
        self.glass = self.item('Glass')
        self.bird_dead = self.item('BirdDead')
        self.speed = self.value('Speed', 1.8)
        self.delay = self.value('DelayTimeToMove', 0.0)
        self.start_position = (-2.318666, 1.763572)   # ctor, cs:53
        self.end_position = (-7.8, 2.5)               # ctor, cs:54
        self.end_position_tricked = (-5.5, 1.763572)  # ctor, cs:55
        self.one_time_leave_aux = False
        self.one_time_leave_tricked_aux = False
        self.one_time_come_back_aux = False
        self.can_go_back = False
        self.can_leave = True
        self.first_time = False
        self.second_time = False
        self.stop_movement_tricked = False
        self.only_once_tricked = False
        self.stop_now = False
        self._invokes = []                            # (time left, fn)

    def _invoke(self, fn, delay):
        self._invokes.append([delay, fn])

    def _cancel_invoke(self):
        self._invokes = []

    def _pawn_in_bird_zone(self):
        w = self.world.woody
        r = self.rott()
        bz = self.bird.zone if self.bird is not None else None
        return ((w is not None and w.zone is not None and w.zone.pid == bz)
                or (r is not None and r.zone is not None and r.zone.pid == bz))

    def _step(self, target, on_done=None, guard=None):
        b = self.bird
        step = self.speed * (1.0 / 60.0)              # one MoveTowards step
        dx, dy = target[0] - b.x, target[1] - b.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= step or dist == 0.0:
            nx, ny = target
        else:
            nx, ny = b.x + dx / dist * step, b.y + dy / dist * step
        if b.sprite is not None:
            b.sprite.x += nx - b.x
            b.sprite.y += ny - b.y
        b.x, b.y = nx, ny

    def update(self, dt):
        for entry in self._invokes[:]:
            entry[0] -= dt
            if entry[0] <= 0.0:
                self._invokes.remove(entry)
                entry[1]()
        b = self.bird
        if b is None:
            return
        if not self.stop_now:                         # cs:67-95
            if self._pawn_in_bird_zone():
                if not self.one_time_leave_aux and not self.can_go_back:
                    self.first_time = True
                    self.one_time_come_back_aux = False
                    self.one_time_leave_aux = True
                    self.play_item(b, 'N2TrickItemUseNormal')
            elif not self.one_time_come_back_aux and self.can_go_back:
                self.second_time = True
                self.one_time_leave_aux = False
                self.one_time_come_back_aux = True
                self.play_item(b, 'N2TrickItemUseTricked')
            if self.can_leave and self.first_time and not self.can_go_back:
                self._invoke(self._start_movement, self.delay)
            elif self.can_go_back and self.second_time and not self.can_leave:
                self._invoke(self._get_back_movement, self.delay)
        elif (self.glass is not None and self.glass.tricked and self.can_leave
                and not self.first_time and self._pawn_in_bird_zone()):
            if not self.one_time_leave_tricked_aux:   # cs:96-107
                self.one_time_leave_tricked_aux = True
                self.play_item(b, 'N2TrickItemIdleTricked')
            if not self.stop_movement_tricked:
                self._invoke(self._start_movement_tricked, self.delay)

    def _start_movement(self):
        """cs:110-131"""
        b = self.bird
        if (b.x, b.y) == self.end_position:
            self.first_time = False
            self.can_go_back = True
            self.can_leave = False
        else:
            self._step(self.end_position)

    def _start_movement_tricked(self):
        """cs:133-151"""
        b = self.bird
        if (b.x, b.y) != self.end_position_tricked \
                and not self.stop_movement_tricked:
            self._step(self.end_position_tricked)
        elif not self.only_once_tricked:
            self.only_once_tricked = True
            self.stop_movement_tricked = True
            self._invoke(self._activate_dead_bird, 2.0)

    def _activate_dead_bird(self):
        """cs:153-157"""
        self.set_active(self.bird, False)
        self.set_active(self.bird_dead, True)

    def _get_back_movement(self):
        """cs:159-185"""
        b = self.bird
        if (b.x, b.y) == self.start_position:
            if self.glass is not None and self.glass.tricked:
                self.stop_now = True
            self.second_time = False
            self.can_leave = True
            self.can_go_back = False
            self.world._return_to_idle(b)             # Bird.ReturnToIdleAnimation
            self._cancel_invoke()
        else:
            self._step(self.start_position)


class BirdPerchBehavior(Behavior):
    """BirdPerchBehavior.cs: the perch animation releases Olga's infinite
    loop after TimeToStopAnimation seconds."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.enabled = False                          # Start(), cs:13-16
        self.start_animation = self.anim_name('StartAnimation')
        self.olga = self.pawn('Olga')
        self.time_to_stop = self.value('TimeToStopAnimation', 3.0)
        self.start_time = -1.0

    def play_animation(self, name):
        super().play_animation(name)
        if name == self.start_animation:              # cs:18-26
            self.enabled = True
            self.start_time = self.world.time

    def update(self, dt):
        if self.start_time > 0.0 and \
                self.world.time - self.start_time >= self.time_to_stop:
            self.enabled = False                      # cs:28-36
            self.start_time = -1.0
            if self.olga is not None:                 # SetIgnoreInfiniteLoopOnce
                self.olga.anim.ignore_infinite = True
                self.olga.anim.ignore_infinite_once = True


class ParrotLedgeBehavior(Behavior):
    """ParrotLedgeBehavior.cs (a RoutineBehavior): moving to the parrot
    ledge teleports the neighbour up onto it — height delta, depths and the
    primed flag ride along; the jump-off to the throne restores them."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.parrot_ledge = self.item('ParrotLedge')
        self.parrot_crap = self.item('ParrotCrap')
        self.aztec_throne = self.item('AztecThrone')
        self.ledge_start = self.vec('LedgeStartLocation')
        self.ledge_end = self.vec('LedgeEndLocation')
        self.fence = self.item('Fence')
        self.ledge_height_delta = self.value('LedgeHeightDelta', 0.0)
        self.is_jumping = False
        self.original_height_delta = 0.0

    def on_start_routine_action(self, item, action):
        self.is_jumping = item is self.parrot_ledge   # cs:25-29

    def on_move_to_routine_action(self, item, action):
        if item is None:
            return
        rott = self.rott()
        if rott is None:
            return
        if item is self.parrot_ledge:                 # cs:36-49
            rott.sprite.x, rott.sprite.y = self.ledge_start
            rott.pos_snap = True
            self.original_height_delta = rott.height_delta
            rott.height_delta = self.ledge_height_delta
            self.depth(rott, 'Woody')
            self.depth(self.fence, 'Rottweiler')
            if self.parrot_ledge is not None:
                self.world.set_primed(self.parrot_ledge, True)
                if self.parrot_ledge.tricked:
                    self.set_active(self.parrot_crap, True)
        elif item is self.aztec_throne and self.is_jumping:  # cs:50-57
            rott.sprite.x, rott.sprite.y = self.ledge_end
            rott.pos_snap = True
            rott.height_delta = self.original_height_delta
            self.depth(rott, 'Rottweiler')
            self.depth(self.fence, 'LevelFence')
            if self.parrot_ledge is not None:
                self.world.set_primed(self.parrot_ledge, False)


class ParrotLedgeFallBehavior(Behavior):
    """ParrotLedgeFallBehavior.cs: past the fall frame the crash animation
    drags the neighbour toward the landing spot; MoveTowards gets Time.time
    as its step, so it effectively snaps — kept bug-for-bug."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.fall_animation = self.anim_name('LedgeFallAnimation', 'CliffCrash')
        self.start_fall_index = self.value('StartFallIndex', 40)
        self.in_fall = False

    def play_animation(self, name):
        super().play_animation(name)
        self.in_fall = name == self.fall_animation    # cs:15-19

    def on_advance_frame(self, idx):
        rott = self.rott()
        if self.in_fall and idx >= self.start_fall_index and rott is not None:
            step = self.world.time                    # cs:30-33
            tx, ty = 5.7, -3.6 - 0.65
            dx, dy = tx - rott.sprite.x, ty - rott.sprite.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= step or dist == 0.0:
                rott.sprite.x, rott.sprite.y = tx, ty
                rott.pos_snap = True
            else:
                rott.sprite.x += dx / dist * step
                rott.sprite.y += dy / dist * step


class ParrotLedgeJumpBehavior(Behavior):
    """ParrotLedgeJumpBehavior.cs: the cliff jump's landing drag, the cigar
    box's exit-delta swaps, the bench/boat crashes, and the Mother's depth
    around the sleeping bench."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.jump_animation = self.anim_name('LedgeJumpAnimation', 'CliffJump')
        self.cigar_box = self.item('CigarBox')
        self.bull = self.item('Bull')
        self.parrot_crap = self.item('ParrotCrap')
        self.boat = self.item('Boat')
        self.parrot_ledge = self.item('ParrotLedge')
        self.sleep_bench = self.item('SleepBench')
        self.start_fall_index = self.value('StartFallIndex', 13)
        self.one_time = False
        self.second_time = False
        self.bull_aux = False
        self.boat_tricked = False
        self.in_jump = False

    def _mother_depth(self, near_name):
        mother = self.world.pawns.get('Mother')
        if mother is None:
            return
        rott = self.rott()
        it = self.action_item('Rottweiler')
        if rott is not None and mother.zone is rott.zone and it is not None \
                and (it is self.sleep_bench or it is self.cigar_box):
            self.depth(mother, near_name)
        else:
            self.depth(mother, 'Alerters')

    def play_animation(self, name):
        super().play_animation(name)
        self.in_jump = name == self.jump_animation    # cs:53
        if self.bull_aux:                             # cs:55-59
            self.bull_aux = False
            self.hide_obj(self.bull, False)
        cb = self.cigar_box
        if cb is not None and cb.tricked and not self.one_time:  # cs:60-68
            self.one_time = True
            self.second_time = False
            cb.rott_use_exit_delta[0] = -0.4
            cb.rott_use_exit_delta[1] = 0.0
            cb.rott_use_item_exit_delta[0] = 0.8
            cb.rott_use_item_exit_delta[1] = -0.2
        if cb is not None and not cb.tricked and not self.second_time:
            self.second_time = True                   # cs:69-77
            self.one_time = False
            cb.rott_use_exit_delta[0] = 0.0
            cb.rott_use_exit_delta[1] = -0.2
            cb.rott_use_item_exit_delta[0] = 0.0
            cb.rott_use_item_exit_delta[1] = 0.0
        if self.boat_tricked:                         # cs:78-81
            self.boat_tricked = False
        if name == 'BenchCrash':                      # cs:82-86
            self.hide_obj(self.bull, True)
            self.bull_aux = True
        if name == 'CliffBoatCrash':                  # cs:87-90
            self.set_active(self.boat, False)
        if self.boat is not None and self.boat.tricked \
                and self.parrot_ledge is not None \
                and self.parrot_ledge.tricked and name == 'CliffBoatCrash':
            self.boat_tricked = True                  # cs:91-94
        self._mother_depth('Rottweiler')              # cs:95-105

    def on_advance_frame(self, idx):
        rott = self.rott()
        if self.in_jump and idx >= self.start_fall_index and rott is not None:
            step = self.world.time                    # cs:117-120 (Time.time)
            tx, ty = 5.7, -3.6 - 0.65
            dx, dy = tx - rott.sprite.x, ty - rott.sprite.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= step or dist == 0.0:
                rott.sprite.x, rott.sprite.y = tx, ty
                rott.pos_snap = True
            else:
                rott.sprite.x += dx / dist * step
                rott.sprite.y += dy / dist * step
        if self.current_animation == 'CliffCrash' and idx == 5:  # cs:121-124
            self.set_active(self.parrot_crap, False)

    def update(self, dt):
        self._mother_depth('Woody')                   # cs:127-140


class PoolJumpBehavior(Behavior):
    """PoolJumpBehavior.cs: the diving-board choreography — the board hides
    under the diver, the awning falls with the pole pose and collider, and
    the linked crash swaps the Mother back in."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.pool_board = self.item('PoolBoard')
        self.pool_awning = self.item('PoolAwning')
        self.pole = self.item('Pole')
        self.mother = self.pawn('Mother')
        self.rottweiler = self.pawn('Rottweiler')
        self.rott_pos = (-3.2, 1.2)                   # ctor, cs:33
        self.last_animation = False
        self.last_animation_linked = False
        self.pool_awning_aux = False

    def on_advance_frame(self, idx):
        if idx == 3 and self.current_animation == 'PoolAwningFall':
            self.play_directly(self.pole, 'N2TrickItemIdleNormal')  # cs:43-45
        elif idx == 6 and self.current_animation == 'PoolAwningFall':
            self.collider(self.pool_awning, True)     # cs:47-50

    def play_animation(self, name):
        self.current_animation = name
        if self.last_animation:                       # cs:57-60
            self.last_animation = False
        if self.last_animation_linked:                # cs:61-66
            if self.mother is not None:
                self.mother.set_hidden(False)
            if self.rottweiler is not None:
                self.rottweiler.sprite.x, self.rottweiler.sprite.y = \
                    self.rott_pos
                self.rottweiler.pos_snap = True
            self.last_animation_linked = False
        if name == 'PoolGetOut' and self.pool_board is not None \
                and self.pool_board.tricked and self.pool_awning is not None \
                and not self.pool_awning.tricked:     # cs:67-72
            self.last_animation = True
            self.set_active(self.pole, False)
            self.world.set_primed(self.pool_awning, True)
        if name == 'CrashMother' and self.pool_board is not None \
                and self.pool_board.tricked and self.pool_awning is not None \
                and self.pool_awning.tricked:         # cs:73-77
            self.last_animation_linked = True
            if self.mother is not None:
                self.mother.set_hidden(True)
        if name == 'WaitWatch':                       # cs:78-82
            rott = self.rottweiler
            if rott is not None:
                rott.anim.ignore_infinite = False     # SetIgnoreInfiniteLoop
            self.hide_obj(self.pool_board, False)
        if name in ('PoolDive', 'PoolSpring'):        # cs:83-86
            self.hide_obj(self.pool_board, True)
        if name in ('PoolGetOut', 'PoolAwningFall', 'CrashMother'):
            self.hide_obj(self.pool_board, False)     # cs:87-90
        if self.pool_awning_aux:                      # cs:91-95
            self.pool_awning_aux = False
            self.hide_obj(self.pool_awning, False)
        if name == 'PoolAwningFall' and self.pool_awning is not None \
                and not self.pool_awning.tricked:     # cs:96-100
            self.hide_obj(self.pool_awning, True)
            self.pool_awning_aux = True


class IndianPlatformBehavior(Behavior):
    """IndianPlatformBehavior.cs: the levitation platform — the double trick
    plays the magician's tricked set at the hover, and the seesaw crashes
    reveal the kid and the rake."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.kid = self.item('Kid')
        self.indian_platform = self.item('IndianPlatform')
        self.magician = self.item('Magician')
        self.arms_bowl = self.item('ArmsBowl')
        self.rake = self.item('Rake')
        self.is_falling = False
        self.rake_aux = False

    def play_animation(self, name):
        super().play_animation(name)
        if self.is_falling:                           # cs:29-33
            self.is_falling = False
            self.hide_obj(self.kid, False)
        if self.rake_aux:                             # cs:34-38
            self.rake_aux = False
            self.hide_obj(self.rake, False)
        ip = self.indian_platform
        if ip is not None and ip.tricked and ip.linked_item_trick is not None:
            linked = self.level.items.get(ip.linked_item_trick)
            if linked is not None and linked.tricked \
                    and name == 'PlatformHover' and self.magician is not None:
                p = self.player(self.magician)        # cs:39-42
                seq = [a for a in self.magician.use_tricked_sequence
                       if p is not None and p.has(a)]
                if p is not None and seq:
                    p.play_sequence(seq)
        if name in ('SeesawCrash', 'SeesawShovelCrash'):     # cs:43-46
            self.is_falling = True
        if name == 'RakeBazarCrash':                  # cs:47-51
            self.hide_obj(self.rake, True)
            self.rake_aux = True

    def on_advance_frame(self, idx):
        if idx == 3 and self.current_animation == 'TakeSnake':   # cs:57-60
            self.play_looping(self.arms_bowl, 'N2TrickItemIdleNormal')


class OlgaBraBehavior(Behavior):
    """OlgaBraBehavior.cs: the shower puts the bra within reach and takes it
    back out."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.put_animation = self.anim_name('PutAnimation', 'OlgaShowerPutBra')
        self.take_animation = self.anim_name('TakeAnimation',
                                             'OlgaShowerTakeBra')
        self.target = self.item('TargetItem')

    def play_animation(self, name):
        super().play_animation(name)
        t = self.target
        if t is None:
            return
        if self.current_animation == self.put_animation:     # cs:14-19
            self.collider(t, True)
            if t.sprite is not None:
                t.sprite.hidden = False               # AnimController.Hidden
            self.world.search_play(t, 'N2TrickItemIdleNormal')
        elif self.current_animation == self.take_animation:  # cs:20-24
            self.collider(t, False)
            if t.sprite is not None:
                t.sprite.hidden = True


class OlgaSubmarineBehavior(Behavior):
    """OlgaSubmarineBehavior.cs: laying the towel down disables the
    submarine's collider."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.submarine = self.item('Submarine')

    def play_animation(self, name):
        super().play_animation(name)
        if name == 'TowelLaydown':                    # cs:9-13
            self.collider(self.submarine, False)


class BraSearchBehavior(Behavior):
    """BraSearchBehavior.cs: taking the bra drops Olga's mat action, swaps
    her shower use to the loop and pushes her routine on."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.target_bra = self.item('TargetBra')
        self.target_mat = self.item('TargetMat')
        self.target_shower = self.item('TargetShower')
        self.target_loop = self.anim_name('TargetLoopAnimation')

    def on_search_item_used(self, item):
        if item is not self.target_bra or self.target_bra is None:
            return                                    # cs:17-25
        rt = self.routine('Olga')
        if rt is not None and self.target_mat is not None:
            rt.remove_actions_by_item(self.target_mat.pid)
        if self.target_shower is not None and self.target_loop:
            self.target_shower.use_anim['Olga'] = [self.target_loop]
        if rt is not None:
            # ActionManager.StartNextAction: the running action is dropped
            # (StartAction stops it first) and the current index restarts
            rt.pawn.anim.on_end = None
            rt.pawn.anim.as_sequence = False
            rt._pending = 'first'
        self.collider(self.target_bra, False)


class MugBehavior(Behavior):
    """MugBehavior.cs: the captain's idle raises and lowers the mug on fixed
    frames of the pose loops. Wired to the captain item's controller."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.mug = self.item('Mug')

    def on_advance_frame(self, idx):
        cur = self.current_animation
        if cur == 'N2TrickItemIdleNormal' and idx == 25:     # cs:19-23
            self.hide_obj(self.mug, True)
            self.collider(self.mug, False)
        elif cur == 'N2TrickItemIdleNormal' and idx == 57:   # cs:24-28
            self.hide_obj(self.mug, False)
            self.collider(self.mug, True)
        elif cur == 'N2TrickItemIdleTricked' and idx == 15:  # cs:29-33
            self.hide_obj(self.mug, True)
            self.collider(self.mug, False)


class ToiletBehavior(Behavior):
    """ToiletBehavior.cs: the rice-toilet runs hide the paper roll for the
    frames the neighbour holds it."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.paper = self.item('Paper')

    def on_advance_frame(self, idx):
        cur = self.current_animation
        if cur == 'RiceToiletPaper' and idx == 100:   # cs:19-23
            self.hide_obj(self.paper, True)
            self.collider(self.paper, False)
        elif cur == 'RiceToiletPaper' and idx == 120:  # cs:24-28
            self.hide_obj(self.paper, False)
            self.collider(self.paper, True)
        if cur == 'RiceToiletPaperChili' and idx == 120:     # cs:29-33
            self.hide_obj(self.paper, True)
            self.collider(self.paper, False)
        elif cur == 'RiceToiletPaperChili' and idx == 180:   # cs:34-38
            self.hide_obj(self.paper, False)
            self.collider(self.paper, True)


class MotherSleepBehaviour(Behavior):
    """MotherSleepBehaviour.cs: the Mother's sit/wake cycle raises the
    OnMotherSit / OnMotherWake events the neighbour's pistol play listens
    to, and the RottweilerMotherBehaviour's OnMotherSleep forces her back to
    sleep."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.first_animation = self.anim_name('FirstAnimation')
        self.last_animation = self.anim_name('LastAnimation')
        self.target_animation = self.anim_name('TargetAnimation')
        self.mother = self.pawn('TargetMother')
        self.mother_item = self.item('MotherItem')
        self.target_item = self.item('TargetItem')
        self.repeat_sleep = bool(self.value('RepeatSleep', True))
        world.subscribe('mother_sleep', self.force_sleep)    # OnEnable, cs:63-66

    def play_animation(self, name):
        super().play_animation(name)
        it = self.action_item('Mother')
        if it is not None and it is self.mother_item \
                and name != self.target_animation:    # cs:36-55
            if name == self.first_animation:
                self.world.fire_event('mother_sit')
                if self.repeat_sleep and self.target_item is not None \
                        and self.target_item.already_tricked:
                    self.repeat_sleep = False
                    self._force_sleep_after_trick()
                if self.mother is not None:
                    self.mother.anim.ignore_infinite = False
            elif name == self.last_animation:
                self.world.fire_event('mother_wake')
        if name == 'MotherHitNeighbor':               # cs:56-60
            self.repeat_sleep = True
            if self.mother_item is not None:
                self.mother_item.tricked = False

    def force_sleep(self):
        """cs:73-83: the untricked arm plays MotherItem.GetMotherSecondUse
        Animation(), which stamps CurrentAnimationSequence = MotherSecondUse
        (Item.cs:936-940) — the window L214's DeckChairMother bar reads
        (ProgressBar.cs:143-148); the tricked arm reads the raw
        MotherUseTrickedAnimation field, no stamp"""
        if self.mother is None or self.mother_item is None:
            return
        if self.target_item is not None and not self.target_item.tricked:
            self.mother_item.current_sequence = 'MotherSecondUse'   # Item.cs:938
            seq = self.mother_item.mother_second_use
        else:
            seq = self.mother_item.use_tricked_anim.get('Mother') or []
        seq = [a for a in seq if self.mother.anim.has(a)]
        if seq:
            self._resequence(seq)

    def _force_sleep_after_trick(self):
        """cs:85-88: MotherItem.GetMotherExtraUseAnimation() stamps
        CurrentAnimationSequence = MotherExtraUse (Item.cs:977-981)"""
        if self.mother is None or self.mother_item is None:
            return
        self.mother_item.current_sequence = 'MotherExtraUse'       # Item.cs:979
        seq = [a for a in self.mother_item.mother_extra_use
               if self.mother.anim.has(a)]
        if seq:
            self._resequence(seq)

    def _resequence(self, seq):
        """TargetMother.AnimController.PlayAnimationSequence(seq) over her
        running action: the controller keeps its ActionManager, so the NEW
        sequence's end still lands in ActionManager.StopCurrentAction
        (AnimationControllerBase.cs:242-246 — ShouldStopAction is raised
        when the last element is pulled, cs:289-292) and her DeckChairMother
        action advances (to MotherWait, then the sit again -> OnMotherSit).
        The port's stand-in for that stop is the pending on_end of her use
        (Routine._finish), carried over here."""
        self.mother.anim.play_sequence(seq, on_end=self.mother.anim.on_end)


class MotherWakeSleepBehavior(Behavior):
    """MotherWakeSleepBehavior.cs: the target animation redirects the
    Mother's running sequence through SetSequenceOverride and releases her
    loop once, and 2 s later re-arms the sleep bar (Invoke("ProgressBarDelay",
    2f) -> ProgressBar.RestoreVariables, cs:33/40, 46-52) — the only re-arm
    of L210's Mother210 bar, which never deactivates (ProgressBar.cs:164-172)
    but whose ExecutedOnce SetSleeping cleared (cs:175-179); an urgent Mother
    action resets the override to the head."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.target_animation = self.anim_name('TargetAnimation')
        self.mother = self.pawn('TargetMother')
        self.target_item = self.item('TargetItem')
        self.target_sequence_index = self.value('TargetSequenceIndex', 0)
        # the ProgressBar GameObject (cs:16): the bar component on it
        self.progress_bar_go = (self.d.get('ProgressBar') or {}).get('path')
        world.subscribe('mother_urgent', self._on_mother_urgent)  # cs:17-20

    def play_animation(self, name):
        super().play_animation(name)
        if name != self.target_animation or self.mother is None:
            return                                    # cs:30-43
        it = self.action_item('Rottweiler')
        self.mother.anim.ignore_infinite = True       # SetIgnoreInfiniteLoopOnce
        self.mother.anim.ignore_infinite_once = True
        if it is not self.target_item:
            self.mother.anim.set_sequence_override(self.target_sequence_index)
        # both arms end in Invoke("ProgressBarDelay", 2f) (cs:33, 40)
        self.world.call_later(2.0, self._progress_bar_delay)

    def _progress_bar_delay(self):
        """ProgressBarDelay (cs:46-52): ProgressBar.RestoreVariables on the
        bar component of the serialized GameObject"""
        if self.progress_bar_go is None:
            return
        for pb in self.world.progress_bars:
            if pb.spec.get('go') == self.progress_bar_go:
                pb.restore()

    def _on_mother_urgent(self):
        if self.mother is not None:                   # cs:54-60
            self.mother.anim.set_sequence_override(0)


class RottweilerMotherBehaviour(Behavior):
    """RottweilerMotherBehaviour.cs: the ship's pistol play — a tricked
    pistol drops the Mother (OnMotherSleep), her sit/wake events swap the
    pistol's use sets, and the hatch / bucket / fish poses ride along."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.first_anim_tricked = self.anim_name('FirstAnimTricked')
        self.mother = self.pawn('TargetMother')
        self.target_item = self.item('TargetItem')
        self.target_item_mother = self.item('TargetItemMother')
        self.hatch = self.item('Hatch')
        self.bucket = self.item('Bucket')
        self.fish = self.item('Fish')
        self.bucket_aux = False
        self.hatch1 = False
        self.hatch2 = False
        self.hatch_close = False
        self.hide_bool = False
        world.subscribe('mother_sit', self._unfreeze)        # OnEnable, cs:130-135
        world.subscribe('mother_sit', self._delete_animation)
        world.subscribe('mother_wake', self._add_animation)

    def play_animation(self, name):
        super().play_animation(name)
        it = self.action_item('Rottweiler')
        if it is not None and it is self.target_item \
                and self.target_item is not None and self.target_item.tricked \
                and name == self.first_anim_tricked:  # cs:47-56
            self.hide_obj(self.target_item, True)
            self.hide_bool = True
            if self.target_item_mother is not None:
                self.target_item_mother.tricked = True
            self.world.fire_event('mother_sleep')
        if name == 'PistolPlay':                      # cs:57-61
            self.hide_bool = True
            self.hide_obj(self.target_item, True)
        if name == 'WaitWatch':                       # cs:62-65
            rott = self.rott()
            if rott is not None:
                rott.anim.ignore_infinite = False     # SetIgnoreInfiniteLoop
        if name == 'BucketCrash':                     # cs:66-69
            self.hide_obj(self.bucket, True)
        if self.bucket_aux:                           # cs:70-74
            self.bucket_aux = False
            self.depth(self.bucket, 'Rottweiler')
        if name == 'WaitInFear' and not self.bucket_aux \
                and self.bucket is not None and self.bucket.tricked:
            self.hide_obj(self.bucket, False)         # cs:75-80
            self.depth(self.bucket, 'Items')
            self.bucket_aux = True
        if self.hatch_close:                          # cs:81-85
            self.hatch_close = False
            self.hide_obj(self.hatch, True)
        if self.hatch1:                               # cs:86-92
            self.hatch1 = False
            self.hide_obj(self.hatch, False)
            self.play_directly(self.hatch, 'N2TrickItemIdleNormal')
            self.hatch_close = True
        if self.hatch2:                               # cs:93-98
            self.hatch2 = False
            self.hide_obj(self.hatch, False)
            self.play_directly(self.hatch, 'N2TrickItemIdleFuckedup')
        if name == 'HatchCarpet' and self.hatch is not None \
                and self.hatch.tricked:               # cs:99-102
            self.hatch1 = True
        if name == 'HatchCrash' and self.hatch is not None \
                and self.hatch.tricked:               # cs:103-106
            self.hatch2 = True
        if name == 'RottComeBackHatch':               # cs:107-110
            self.hide_obj(self.fish, False)

    def on_animation_sequence_ended(self):
        it = self.action_item('Rottweiler')
        if it is not None and it is self.target_item:  # cs:116-119
            self.world.fire_event('mother_sleep')
        if self.hide_bool:                            # cs:123-127
            self.hide_bool = False
            self.hide_obj(self.target_item, False)

    def _unfreeze(self):
        """cs:144-147"""
        rott = self.rott()
        if rott is not None:
            rott.anim.ignore_infinite = True          # SetIgnoreInfiniteLoop(true)

    def _add_animation(self):
        """cs:149-163"""
        t = self.target_item
        if t is None:
            return
        if not t.tricked:
            t.use_anim['Rottweiler'] = ['WaitWatch', 'PistolPlay']
        else:
            t.use_tricked_anim['Rottweiler'] = ['WaitWatch', 'PistolFire']

    def _delete_animation(self):
        """cs:165-177"""
        t = self.target_item
        if t is None:
            return
        it = self.action_item('Rottweiler')
        if it is not t and not t.tricked:
            t.use_anim['Rottweiler'] = ['PistolPlay']
        elif t.tricked:
            t.use_tricked_anim['Rottweiler'] = ['PistolFire']

    def on_advance_frame(self, idx):
        if self.current_animation == self.first_anim_tricked and idx == 65:
            if self.mother is not None:               # cs:179-186
                self.mother.anim.ignore_infinite = True
                self.mother.anim.ignore_infinite_once = True
                if self.mother.anim.has('MotherPistolShotCrash'):
                    self.mother.anim.play_single('MotherPistolShotCrash')


class WashbucketBehavior(Behavior):
    """WashbucketBehavior.cs: Olga's shower run — the bucket pose brings the
    wash bucket out and turns the shower's prime into its use set; the cloth
    and end poses follow."""

    def __init__(self, world, d):
        super().__init__(world, d)
        self.shower = self.item('Shower')
        self.bucket_animation = self.anim_name('BucketAnimation')
        self.cloth_animation = self.anim_name('ClothAnimation')
        self.end_animation = self.anim_name('EndAnimation')

    def play_animation(self, name):
        super().play_animation(name)
        if name == self.bucket_animation:             # cs:24-33
            if self.enabled:
                self.enabled = False
                self.go_set_active('Washbucket', True)
                if self.shower is not None:
                    self.shower.rott_prime_anim = \
                        list(self.shower.use_anim.get('Rottweiler') or [])
        elif name == self.cloth_animation:            # cs:34-37
            self.go_set_active('Cloth', True)
        elif name == self.end_animation:              # cs:38-46
            if self.shower is not None:
                self.shower.use_anim['Olga'] = [
                    'OlgaShipShowerEnter', 'OlgaShipShowerIdle']


REGISTRY = {
    'Level101Behavior': Level101Behavior,
    'Level105Behavior': Level105Behavior,
    'Level105RoutineBehavior': Level105RoutineBehavior,
    'Level108Behavior': Level108Behavior,
    'Level109Behavior': Level109Behavior,
    'Level110Behavior': Level110Behavior,
    'Level113Behavior': Level113Behavior,
    'Level114Behavior': Level114Behavior,
    'Woody114Behavior': Woody114Behavior,
    'VacuumBehavior': VacuumBehavior,
    'RollerSkaterBehavior': RollerSkaterBehavior,
    'TrickProgressBarBehavior': TrickProgressBarBehavior,
    'Level201Behavior': Level201Behavior,
    'Level202Behavior': Level202Behavior,
    'Level204Behavior': Level204Behavior,
    'Level204OlgaBehavior': Level204OlgaBehavior,
    'Level206Behavior': Level206Behavior,
    'Level206MotherBehavior': Level206MotherBehavior,
    'Level206RoutineBehavior': Level206RoutineBehavior,
    'Level207MotherBehavior': Level207MotherBehavior,
    'Level208Behaviors': Level208Behaviors,
    'Level210Behavior': Level210Behavior,
    'Level211Behavior': Level211Behavior,
    'Level211LifeBoatBehavior': Level211LifeBoatBehavior,
    'Level212Behavior': Level212Behavior,
    'Level213Behavior': Level213Behavior,
    'Level213OlgaBehavior': Level213OlgaBehavior,
    'FifiBehavior': FifiBehavior,
    'SandCastleBehavior': SandCastleBehavior,
    'SkiBehavior': SkiBehavior,
    'BirdMovementBehavior': BirdMovementBehavior,
    'BirdPerchBehavior': BirdPerchBehavior,
    'ParrotLedgeBehavior': ParrotLedgeBehavior,
    'ParrotLedgeFallBehavior': ParrotLedgeFallBehavior,
    'ParrotLedgeJumpBehavior': ParrotLedgeJumpBehavior,
    'PoolJumpBehavior': PoolJumpBehavior,
    'IndianPlatformBehavior': IndianPlatformBehavior,
    'OlgaBraBehavior': OlgaBraBehavior,
    'OlgaSubmarineBehavior': OlgaSubmarineBehavior,
    'BraSearchBehavior': BraSearchBehavior,
    'MugBehavior': MugBehavior,
    'ToiletBehavior': ToiletBehavior,
    'MotherSleepBehaviour': MotherSleepBehaviour,
    'MotherWakeSleepBehavior': MotherWakeSleepBehavior,
    'RottweilerMotherBehaviour': RottweilerMotherBehaviour,
    'WashbucketBehavior': WashbucketBehavior,
}

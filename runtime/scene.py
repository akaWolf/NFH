"""Turn an exported level JSON into something drawable.

Everything here follows docs/GAMEPLAY.md §8: sprites are screen-space blits from
sheet atlases, ordered by the GUIDepth enum, sized against a fixed 800x600
design resolution.
"""
import json, os

DESIGN_W, DESIGN_H = 800.0, 600.0

# lower value draws in front (Unity's GUI.depth convention)
GUI_DEPTH = {
    'BackItems': 72, 'BackDoors': 64, 'Items': 32, 'ItemsFront': 24,
    'Doors': 22, 'Alerters': 20, 'FrontDoors': 19, 'Rottweiler': 18,
    'Woody': 16, 'LevelFenceBack': 14, 'LevelFence': 13, 'BackHUD': 12,
    'HUD': 11, 'MainMenu': 10, 'Menu': 9, 'MainMenuControl': 8,
    'MainMenuFont': 7, 'ConfirmMessage': 2, 'MouseIcon': 1,
}

# the built-in Plane the levels use for their backdrop is 10x10 units
UNITY_PLANE_SIZE = 10.0


class Anim:
    __slots__ = ('name', 'sheet', 'cols', 'rows', 'start', 'end', 'fps',
                 'ow', 'oh', 'dx', 'dy', 'loop', 'hold', 'pattern',
                 'infinite', 'type_looping', 'sounds', 'blocking',
                 'src_index')

    def __init__(self, d, base_path=''):
        self.name = d.get('Name')
        # AnimationInstance.LoadTexture does Resources.Load(BaseAnimationPath +
        # TextureFileName), so an empty TextureFileName means the base path is
        # itself the asset. Textures are extracted under their own name, which
        # is the last path component either way.
        self.sheet = os.path.basename((base_path or '') + (d.get('TextureFileName') or ''))
        self.cols = max(1, d.get('SheetColumns') or 1)
        self.rows = max(1, d.get('SheetRows') or 1)
        self.start = d.get('StartFrame') or 0
        self.end = d.get('EndFrame') or 0
        self.fps = d.get('FrameRate') or 10.0
        self.ow = d.get('OriginalWidth') or 0.0
        self.oh = d.get('OriginalHeight') or 0.0
        dl = d.get('DeltaLocation') or {}
        self.dx = dl.get('x', 0.0); self.dy = dl.get('y', 0.0)
        # two independent things: InfiniteLoop is a runtime flag that always
        # wins, while Type==Looping only applies when the animation is started
        # as a looping one — PlaySingleAnimation overrides the type to Single.
        self.infinite = bool(d.get('InfiniteLoop'))
        self.type_looping = d.get('Type') == 'Looping'
        self.loop = self.infinite or self.type_looping
        self.hold = bool(d.get('HoldOnLastFrame'))
        self.blocking = bool(d.get('Blocking'))     # AnimationInstance.Blocking
        self.pattern = d.get('Pattern') or None
        self.sounds = [(sd.get('Frame'), sd.get('FileName'))
                       for sd in (d.get('Sounds') or []) if sd.get('FileName')]

    def frame_at(self, t):
        """frame index for elapsed time t, honouring Pattern when present"""
        if self.pattern:
            i = int(t * self.fps)
            if not self.loop and i >= len(self.pattern):
                i = len(self.pattern) - 1 if self.hold else i % len(self.pattern)
            return self.pattern[i % len(self.pattern)]
        n = self.end - self.start + 1
        if n <= 0:
            return self.start
        i = int(t * self.fps)
        if not self.loop and i >= n:
            i = n - 1 if self.hold else i % n
        return self.start + (i % n)


class Sprite:
    """one drawable: a world position, a depth, and an animation to play"""
    __slots__ = ('name', 'x', 'y', 'depth', 'anims', 'current', 'ctrl_dx',
                 'ctrl_dy', 'kind', 'go', 'hidden', 'cur_frame')

    def __init__(self, name, x, y, depth, anims, current, ctrl_dx, ctrl_dy,
                 kind, go=None):
        self.name = name; self.x = x; self.y = y; self.depth = depth
        self.anims = anims; self.current = current
        self.ctrl_dx = ctrl_dx; self.ctrl_dy = ctrl_dy; self.kind = kind
        self.go = go; self.hidden = False; self.cur_frame = None


def _anim_name(v):
    """the enum's NONE means no animation"""
    return None if v in (None, 'NONE') else v


class Zone:
    __slots__ = ('name', 'pid', 'x', 'y', 'w', 'h', 'exit',
                 'play_left', 'play_right', 'ty', 'height_delta', 'tx')

    def __init__(self, name, pid, x, y, w, h, is_exit, ty=0.0, height_delta=0.0,
                 tx=0.0):
        self.name = name; self.pid = pid
        self.x = x; self.y = y
        self.w = w; self.h = h; self.exit = is_exit
        self.ty = ty                        # transform y, floor reference
        self.tx = tx                        # transform x (Entrance/StartLocation)
        self.height_delta = height_delta    # Zone.HeightDelta
        # Level.SetPlayLeft/SetPlayRight, filled in from the Level component;
        # the collider box is containment, these are the walking limits
        self.play_left = x - w * 0.5
        self.play_right = x + w * 0.5

    @property
    def left(self):
        return self.play_left

    @property
    def right(self):
        return self.play_right


class Item:
    """Anything the neighbour's routine can act on, or Woody can trick."""
    __slots__ = ('name', 'pid', 'kind', 'x', 'y', 'zone', 'dx', 'dy',
                 'use_distance', 'delta_olga_x', 'delta_mother_x',
                 'should_walk_up', 'should_walk_down', 'item_use_height',
                 'delta_use_height', 'enter_zone', 'leave_zone',
                 'animation', 'take_animation', 'empty_animation',
                 'use_woody_sequence', 'animation_sequence',
                 'use_take_sequence', 'take_sequence',
                 'angry_easy_up', 'angry_easy_down', 'angry_hard',
                 'fix_animation', 'fix_sequence', 'use_fix_sequence',
                 'fix_without_animations', 'can_fix', 'dont_get_angry',
                 'dont_laugh', 'grab_directly', 'keep_after_use',
                 'can_undo_trick', 'get_tricked_at_once', 'require_priming',
                 'primed', 'second_required', 'locked', 'used', 'use_once',
                 'wrong_trick', 'fucked_up', 'was_priming',
                 'require_priming_only_tricked', 'remove_inv_after_priming',
                 'dont_prime_while_tricked', 'priming_item',
                 'prime_with_inventory', 'primed_inventory_type',
                 'object_to_prime', 'unlock_object_to_prime',
                 'woody_prime_anim', 'prime_other',
                 'rott_toggles_prime', 'require_unprime', 'is_using',
                 'rott_prime_anim', 'rott_unprime_anim',
                 'force_whatsup_not_primed',
                 'primed_normal', 'primed_tricked', 'primed_fucked_up',
                 'force_primed_on_start', 'show_only_when_primed',
                 'hide_when_primed', 'delta_primed_x', 'delta_primed_y',
                 'fixing_item', 'force_use_fixing_item', 'fix_depends_on',
                 'delta_fix_x', 'delta_fix_y', 'let_untrick',
                 'bubble_icon', 'bubble_icon_active', 'bubble_icon_mad',
                 'destroy_after_use_tricked',
                 'remove_from_routine_after_use_tricked',
                 'remove_after_first_use', 'main_valve_open',
                 'take_off_iron_primed', 'fix_all', 'use_item_multiple_times',
                 'keep_full', 'trick_after_woody_use', 'depends_pig_keys',
                 'pig_keys', 'pig_milk', 'cow_flowers', 'change_iron_routine',
                 'change_iron_routine_last_path', 'item_removed', 'clickable',
                 'prime_item_aux', 'double_priming_item',
                 'compound', 'compound_required', 'compound_tricked',
                 'compound_tricked_anim', 'compound_double_anim',
                 'inventory_items', 'dont_remove_inventory',
                 'activate_item_trick', 'set_tricked_on_item',
                 'linked_item_trick', 'fix_item_trick', 'depends_on_2',
                 'use_depends_on_when_tricked', 'force_fix_original',
                 'hide_anim', 'hide_idle', 'leave_animation', 'hide_woody',
                 'sleep_sequence', 'alert_start', 'alert_left', 'alert_right',
                 'wake_sequence', 'poor_sequence', 'alerter_delay',
                 'alert_on_start_timer', 'rott_surprise',
                 'surprise_far_left', 'surprise_far_right', 'notice_enter',
                 'collider',
                 'use_anim', 'use_tricked_anim', 'idle', 'idle_tricked', 'animating',
                 'required_inventory', 'trick_score', 'anger', 'sprite',
                 'tricked', 'got_tricked', 'already_tricked', 'depends_on',
                 'use_at_other_place', 'neutral',
                 # behaviors and the alarm plumbing
                 'use_tricked_linked', 'kid_item', 'behavior',
                 'full_animation', 'primed_animation', 'tricked_animation',
                 'looping_flag', 'hide_when_not_animating', 'use_anim_type',
                 'aux1', 'aux2', 'aux3', 'aux4',
                 'alarm_animation', 'alert_animation',
                 'enable_collider_when_alerted',
                 'cause_alarm', 'cause_alarm_when_trick', 'wake_alerter_flag',
                 'direct_use', 'alarm_item', 'action_duration',
                 'cause_alarm_interval', 'last_alarm_time', 'can_use',
                 'mother_second_use', 'mother_extra_use',
                 'use_tricked_sequence', 'rott_use_exit_delta',
                 'rott_use_item_exit_delta', 'notice_near', 'cause_slip',
                 'surprise_delta', 'surprise_left', 'surprise_right',
                 'change_actions_208',
                 # the use side-effect block (RoutineActionUse / RottweilerUse
                 # / PlayAngryAnimation / InternalUse)
                 'go', 'teleport_woody_on_use', 'set_woody_x_on_use',
                 'woody_target_y', 'set_olga_x_on_use',
                 'teleport_rott_on_use', 'rott_teleport_offset',
                 'is_bed', 'is_rottweiler_sleeping',
                 'rush_to_toilet', 'cause_sickness',
                 'pawn_to_affect', 'pawn_to_affect_only_linked',
                 'show_item_when_affected', 'change_item_anim_when_affected',
                 'item_anim_when_affected', 'change_item_anim_when_angry',
                 'item_anim_when_angry', 'use_olga_tricked_flag',
                 'use_mother_tricked_flag',
                 'reuse_after_fix', 'angry_without_animations', 'fix_directly',
                 'rott_extra_angry', 'before_angry', 'sand_castle_flag',
                 'hide_during_rott_animation', 'hide_object_during_animation',
                 'disable_collider_after_use', 'give_bowling_when_tricked',
                 'remove_bowling', 'force_fuckedup_when_tricked',
                 'idle_fucked_up', 'use_fucked_up', 'use_normal',
                 'use_tricked_single', 'use_normal_sequence',
                 'play_use_normal_seq', 'play_use_tricked_seq',
                 'final_normal', 'final_tricked', 'final_linked',
                 'exact_normal', 'exact_tricked', 'exact_linked',
                 'use_final_positions_in_beginning',
                 'should_return', 'at_home',
                 'dont_use_on', 'still_use_not_tricked_delta',
                 'rott_prime_exit_delta', 'rott_use_not_tricked_exit_delta',
                 'exit_delta_aux', 'exit_delta_not_tricked_aux',
                 'hide_during_woody_anim', 'hide_during_woody_use_anim',
                 'hide_other_object_woody', 'hide_before_use',
                 'hide_after_use', 'show_after_use',
                 'pawn_to_change_layer_during_hide', 'layer_depth',
                 'tricked_object_go', 'is_ground_trick', 'dont_show_on_fix',
                 'next_action_after_gramaphone', 'ignore_woody_when_use',
                 'harpoon_aux', 'child_renderers',
                 'object_to_show_before_angry_go', 'animate_after_use',
                 'mother_rott_angry',
                 # the full TrickItem.PlayAnimation dispatch
                 'rott_compound_use_tricked', 'olga_compound_use_tricked',
                 'rott_custom_tricked', 'olga_custom_tricked',
                 'play_custom_tricked', 'rott_use_fuckedup',
                 'olga_use_fuckedup', 'should_play_rott_fuckedup',
                 'depends_nfh2', 'depends_on_shade_tricked',
                 'use_olga_tricked_anim_flag',
                 'linked_trick_rush_toilet', 'linked_trick_rush_toilet_target',
                 'second_idle_tricked', 'second_already_tricked',
                 'rott_use_second_tricked', 'use_multiple_times',
                 'hover_anim', 'idle_linked_tricked',
                 'compound_trick_score_v', 'extra_coin_linked',
                 'compound_extra_coin', 'plant_carnivore_extra',
                 'extra_coin_206', 'extra_coin_210', 'dog_basket_210',
                 'enable_anim_index_control', 'anims_to_control',
                 'current_sequence', 'current_seq_index',
                 'dexterity', 'dexterity_trick_item', 'dexterity_unlocker',
                 'dexterity_animation', 'play_dexterity_seq',
                 'dexterity_sequence', 'dexterity_cannot_lose',
                 'dexterity_keep_item', 'dexterity_keep_use_item',
                 'take_item_count', 'hide_in_dexterity',
                 'dexterity_run_other', 'activate_trick_if_search',
                 'dexterity_hide_object', 'dexterity_alert',
                 'rabbit_206', 'extra_item_aux',
                 'activate_item_after_using', 'delay_activate_after_using',
                 'captain_door_1', 'captain_door_2', 'extra_item',
                 'change_tooltip_when_tricked', 'name_string',
                 'go_next_action', 'skip_action', 'is_mother_second_use',
                 'execute_once_mother', 'play_angry_after_toilet',
                 'restart_after_tricked', 'activate_item_after_fix',
                 'fix_item_trick_linked', 'block_after_fix',
                 'delta_woody_x', 'delta_woody_y',
                 'rott_use_olga_seq', 'rott_use_tricked_olga_seq',
                 'drawing_current', 'drawing_done_cleaning',
                 'progress_bar_animation', 'progress_bar_object')

    def __init__(self, name, pid, kind, x, y, zone, dx, dy, d):
        self.name = name; self.pid = pid; self.kind = kind
        self.x = x; self.y = y; self.zone = zone
        self.dx = dx; self.dy = dy
        # each pawn type has its own use sequence; an empty one means this
        # item is simply not that character's to use
        self.use_anim = {
            'Rottweiler': d.get('RottweilerUseAnimation') or [],
            'Olga': d.get('OlgaUseAnimation') or [],
            'Mother': d.get('MotherUseAnimation') or [],
        }
        self.use_tricked_anim = {
            'Rottweiler': d.get('RottweilerUseTrickedAnimation') or [],
            'Olga': d.get('OlgaUseTrickedAnimation') or [],
            'Mother': d.get('MotherUseTrickedAnimation') or [],
        }
        self.idle = _anim_name(d.get('IdleNormal'))
        self.idle_tricked = _anim_name(d.get('IdleTricked'))
        # PlayItemAnimation is a no-op unless Animating, and skips NONE outright
        self.animating = bool(d.get('Animating'))
        self.use_distance = d.get('UseDistance') or 0.01
        self.should_walk_up = bool(d.get('ShouldWalkUp'))
        self.should_walk_down = bool(d.get('ShouldWalkDown'))
        self.item_use_height = d.get('ItemUseHeight') or 0.03
        self.delta_use_height = d.get('DeltaUseHeight') or 0.0
        self.enter_zone = _anim_name(d.get('EnterZone'))
        self.leave_zone = _anim_name(d.get('LeaveZone'))
        # Woody's use animation (Woody.TryUseItem plays Animation, or the
        # sequence when UseWoodyAnimationSequence)
        self.animation = _anim_name(d.get('Animation'))
        self.take_animation = _anim_name(d.get('TakeAnimation'))
        self.empty_animation = _anim_name(d.get('EmptyAnimation'))
        self.use_woody_sequence = bool(d.get('UseWoodyAnimationSequence'))
        self.animation_sequence = d.get('AnimationSequence') or []
        self.use_take_sequence = bool(d.get('UseTakeAnimationSequence'))
        self.take_sequence = d.get('TakeAnimationSequence') or []
        # the neighbour's reaction set (Rottweiler.PlayAngryAnimation)
        self.angry_easy_up = _anim_name(d.get('AnimationAngryEasyUp'))
        self.angry_easy_down = _anim_name(d.get('AnimationAngryEasyDown'))
        self.angry_hard = _anim_name(d.get('AnimationAngryHard'))
        self.fix_animation = _anim_name(d.get('FixAnimation'))
        self.fix_sequence = d.get('FixSequence') or []
        self.use_fix_sequence = bool(d.get('UseFixSequence'))
        self.fix_without_animations = bool(d.get('FixWithoutAnimations'))
        self.can_fix = bool(d.get('CanFix'))
        self.dont_get_angry = bool(d.get('DontGetAngry'))
        self.dont_laugh = bool(d.get('DontLaughWhenTrickItem'))
        # trick bookkeeping (Item / TrickItem fields)
        self.grab_directly = bool(d.get('GrabDirectly'))
        self.keep_after_use = bool(d.get('KeepAfterUse'))
        self.can_undo_trick = bool(d.get('CanUndoTrick'))
        self.get_tricked_at_once = bool(d.get('GetTrickedAtOnce'))
        self.require_priming = bool(d.get('RequirePriming'))
        self.primed = bool(d.get('Primed'))
        # priming (Item.cs:334-352, resolved by WoodyPrime / SetPrimed and the
        # CanWoodyUse gates; TrickItem.cs:92-96,126 add the primed idles)
        self.require_priming_only_tricked = bool(d.get('RequirePrimingOnlyWhenTricked'))
        self.remove_inv_after_priming = bool(d.get('RemoveInventoryAfterRequirePriming'))
        self.dont_prime_while_tricked = bool(d.get('DontPrimeWhileTricked'))
        self.priming_item = (d.get('PrimingItem') or {}).get('path')
        self.prime_with_inventory = d.get('PrimeWithInventory')
        self.primed_inventory_type = d.get('PrimedInventoryType')
        self.object_to_prime = (d.get('ObjectToPrimeWhenPrimed') or {}).get('path')
        self.unlock_object_to_prime = bool(d.get('UnlockObjectToPrime'))
        self.woody_prime_anim = d.get('WoodyPrimeAnimation') or []
        self.prime_other = _anim_name(d.get('PrimeOther'))
        self.rott_toggles_prime = bool(d.get('RottweilerUseTogglesPrime'))
        self.require_unprime = bool(d.get('RequireUnprime'))
        self.is_using = False                # Item.IsUsing (RequireUnprime phase)
        self.rott_prime_anim = d.get('RottweilerPrimeAnimation') or []
        self.rott_unprime_anim = d.get('RottweilerUnprimeAnimation') or []
        self.force_whatsup_not_primed = bool(d.get('ForceWhatsUpAnimWhenNotPrimed'))
        self.primed_normal = _anim_name(d.get('PrimedNormal'))
        self.primed_tricked = _anim_name(d.get('PrimedTricked'))
        self.primed_fucked_up = _anim_name(d.get('PrimedFuckedUp'))
        self.force_primed_on_start = bool(d.get('ForcePrimedAnimationOnStart'))
        self.show_only_when_primed = bool(d.get('ShowOnlyWhenPrimed'))
        self.hide_when_primed = bool(d.get('HideWhenPrimed'))
        self.delta_primed_x = (d.get('DeltaPrimedLocation') or {}).get('x', 0.0)
        self.delta_primed_y = (d.get('DeltaPrimedLocation') or {}).get('y', 0.0)
        # the fixing-tool run (Item.cs:847-858, Rottweiler.RunToFixingItem)
        self.fixing_item = (d.get('FixingItem') or {}).get('path')
        self.force_use_fixing_item = bool(d.get('ForceUseFixingItem'))
        self.fix_depends_on = bool(d.get('FixDependsOn'))
        self.delta_fix_x = (d.get('DeltaFixLocation') or {}).get('x', 0.0)
        self.delta_fix_y = (d.get('DeltaFixLocation') or {}).get('y', 0.0)
        self.let_untrick = bool(d.get('LetUntrickTrickedItem'))
        # Actor.Start: BubbleIcon = Resources.Load(GetBaseIconPath() + path);
        # the cache resolves by basename, so keep the raw path tail
        self.bubble_icon = d.get('BubbleIconPath') or None
        self.bubble_icon_active = d.get('BubbleIconActivePath') or None
        self.bubble_icon_mad = d.get('BubbleIconMadPath') or None
        # RoutineActionUse.StopAction removes routine actions once the
        # tricked use lands (RoutineActionUse.cs:415-427)
        self.destroy_after_use_tricked = bool(d.get('DestroyAfterUseTricked'))
        self.remove_from_routine_after_use_tricked = \
            bool(d.get('RemoveFromRoutineAfterUseTricked'))
        self.remove_after_first_use = bool(d.get('RemoveFromRoutineAfterFirstUse'))
        self.main_valve_open = False     # Item.MainValveOpen (the ValveMain hack)
        # the name-hack support fields
        self.take_off_iron_primed = bool(d.get('TakeOffIronPrimed'))
        self.fix_all = bool(d.get('FixAll'))
        self.use_item_multiple_times = bool(d.get('UseItemMultipleTimes'))
        self.keep_full = bool(d.get('KeepFull'))
        self.trick_after_woody_use = bool(d.get('TrickAfterWoodyUse'))
        self.depends_pig_keys = bool(d.get('DependsPigKeys'))
        self.pig_keys = (d.get('PigKeys') or {}).get('path')
        self.pig_milk = (d.get('PigMilk') or {}).get('path')
        self.cow_flowers = (d.get('CowBehaviorFlowers') or {}).get('path')
        self.change_iron_routine = False       # set by TrickItem.Fix
        self.change_iron_routine_last_path = False
        self.item_removed = False              # Item.ItemRemoved (PigKeys)
        self.clickable = True                  # Collider.enabled (the Pipe hack)
        self.prime_item_aux = False            # Item.PrimeItemAux (DogFifi)
        self.double_priming_item = bool(d.get('DoublePrimingItem'))
        self.second_required = d.get('SecondRequiredInventory')
        self.locked = bool(d.get('Locked'))
        self.used = False
        self.use_once = bool(d.get('UseOnce'))
        self.wrong_trick = False
        self.fucked_up = False
        self.was_priming = False
        self.compound = bool(d.get('Compound'))
        self.compound_required = d.get('CompoundRequiredInventory')
        self.compound_tricked = bool(d.get('CompoundTricked'))
        self.compound_tricked_anim = _anim_name(d.get('CompoundTrickedAnim'))
        self.compound_double_anim = _anim_name(d.get('CompoundDoubleTrickedAnim'))
        # SearchItem.InventoryItems
        self.inventory_items = [
            {'type': v.get('Type'), 'use_count': v.get('UseCount') or 0,
             'name': v.get('NameString') or '',
             'desc': v.get('DescriptionString') or ''}
            for v in (d.get('InventoryItems') or [])]
        self.dont_remove_inventory = bool(d.get('DontRemoveInventoryItem'))
        self.activate_item_trick = (d.get('ActivateItemTrick') or {}).get('path')
        self.set_tricked_on_item = (d.get('SetTrickedOnItem') or {}).get('path')
        self.linked_item_trick = (d.get('LinkedItemTrick') or {}).get('path')
        self.fix_item_trick = (d.get('FixItemTrick') or {}).get('path')
        self.use_depends_on_when_tricked = bool(d.get('UseDependsOnWhenTricked'))
        self.force_fix_original = bool(d.get('ForceFixOriginal'))
        # HideItem: the wardrobe's own animations and whether Woody vanishes
        self.hide_anim = _anim_name(d.get('HideAnim'))
        self.hide_idle = _anim_name(d.get('IdleAnim'))
        self.leave_animation = _anim_name(d.get('LeaveAnimation'))
        self.hide_woody = bool(d.get('HideWoody'))
        # Alerter: the sleeping pet's animation sets and timings
        self.sleep_sequence = d.get('SleepSequence') or []
        self.alert_start = _anim_name(d.get('AlertSequenceStart'))
        self.alert_left = _anim_name(d.get('AlertLeft'))
        self.alert_right = _anim_name(d.get('AlertRight'))
        self.wake_sequence = d.get('WakeSequence') or []
        self.poor_sequence = d.get('PoorSequence') or []
        self.alerter_delay = d.get('AlerterDelay') if d.get('AlerterDelay') is not None else 1.0
        self.alert_on_start_timer = d.get('AlertOnStartTimer') or 0.0
        # what the neighbour plays on arriving at a (non-tricked) surprise item
        self.rott_surprise = d.get('RottweilerSurpriseAnimation') or []
        self.surprise_far_left = _anim_name(d.get('SurpriseFarLeft'))
        self.surprise_far_right = _anim_name(d.get('SurpriseFarRight'))
        self.notice_enter = bool(d.get('NoticeWhenEnterZone'))
        self.collider = None                # (cx, cy, w, h), for click hit-tests
        self.delta_olga_x = (d.get('DeltaOlgaLocation') or {}).get('x', 0.0)
        self.delta_mother_x = (d.get('DeltaMotherLocation') or {}).get('x', 0.0)
        self.required_inventory = d.get('RequiredInventory')
        self.trick_score = d.get('TrickScore') or 0
        self.anger = d.get('AngerAmount') or 0
        self.depends_on = (d.get('DependsOn') or {}).get('path')
        self.use_at_other_place = bool(d.get('UseAtOtherPlace'))
        self.neutral = bool(d.get('Neutral'))
        self.sprite = None
        self.tricked = bool(d.get('Tricked'))
        self.got_tricked = False
        self.already_tricked = False
        # the linked-pair use set (TrickItem.PlayAnimation's first branch,
        # TrickItem.cs:804-816); behaviors on 207/210 rewrite it at runtime
        self.use_tricked_linked = d.get('RottweilerUseTrickedLinkedAnimation') or []
        # ActionManager.KidActions reads Actions[last].Item.Kid (cs:415-418)
        self.kid_item = (d.get('Kid') or {}).get('path')
        # Actor.Behavior serialized on the item itself (Vacuum, GroundSkates,
        # PoolBoard, Bird, Mug carry the shared behavior component)
        self.behavior = (d.get('Behavior') or {}).get('path')
        # SearchItem's four-state animation switcher (SearchItem.cs:222-244)
        self.full_animation = _anim_name(d.get('FullAnimation'))
        self.primed_animation = _anim_name(d.get('PrimedAnimation'))
        self.tricked_animation = _anim_name(d.get('TrickedAnimation'))
        self.looping_flag = bool(d.get('Looping'))
        self.hide_when_not_animating = bool(d.get('HideWhenNotAnimating'))
        self.use_anim_type = bool(d.get('UseAnimationType'))
        self.aux1 = self.aux2 = self.aux3 = self.aux4 = True
        # the alarm plumbing (Item.OnIconPressed / PhoneBehavior /
        # PlayAlertAnimation; Item.cs:320-332, 2176-2209, 2429-2448)
        self.alarm_animation = _anim_name(d.get('AlarmAnimation'))
        self.alert_animation = _anim_name(d.get('AlertAnimation'))
        self.enable_collider_when_alerted = bool(d.get('EnableColliderWhenAlerted'))
        self.cause_alarm = bool(d.get('CauseAlarm'))
        self.cause_alarm_when_trick = bool(d.get('CauseAlarmWhenTrickItem'))
        self.wake_alerter_flag = bool(d.get('WakeAlerter'))
        self.direct_use = _anim_name(d.get('DirectUse'))
        self.alarm_item = (d.get('AlarmItem') or {}).get('path')
        self.action_duration = d.get('ActionDuration') or 0.0
        self.cause_alarm_interval = d.get('CauseAlarmInterval') \
            if d.get('CauseAlarmInterval') is not None else 2.0
        self.last_alarm_time = None
        # Item.CanUse gates the click destination (Pawn.GetMoveDestination)
        self.can_use = d.get('CanUse') if d.get('CanUse') is not None else True
        # the Mother's alternate use sets (Item.cs:198-204)
        self.mother_second_use = d.get('MotherSecondUseAnimation') or []
        self.mother_extra_use = d.get('MotherExtraUseAnimation') or []
        # the item's own tricked-use sequence (TrickItem.UseTrickedSequence)
        self.use_tricked_sequence = d.get('UseTrickedSequence') or []
        # exit deltas the ParrotLedgeJumpBehavior rewrites; their application
        # is the unported use-flags block (RoutineActionUse.cs:428-457)
        red = d.get('RottweilerUseExitDelta') or {}
        self.rott_use_exit_delta = [red.get('x', 0.0), red.get('y', 0.0)]
        red = d.get('RottweilerUseItemExitDelta') or {}
        self.rott_use_item_exit_delta = [red.get('x', 0.0), red.get('y', 0.0)]
        # the walk-nearby notice (TrickItem.Start registers into
        # Zone.NoticeWhenNearItems; Rottweiler.UpdateWalking consumes it)
        self.notice_near = bool(d.get('NoticeWhenWalkNearby'))
        # TrickItem.MotherUse injects ActionsToAddInGame on a tricked use
        # (TrickItem.cs:1253-1262)
        self.change_actions_208 = bool(d.get('ChangeActionsWhenTricked208'))
        # -- the use side-effect block ----------------------------------
        def ref(field):
            return (d.get(field) or {}).get('path')
        def vec2(field):
            v = d.get(field) or {}
            return (v.get('x', 0.0), v.get('y', 0.0))
        self.go = None                    # filled by Level._add_item
        # Woody.TryUseItem's teleports (Woody.cs:520-533) and Olga's
        # (Olga.cs:146-152)
        self.teleport_woody_on_use = bool(d.get('TeleportWoodyOnUse'))
        self.set_woody_x_on_use = bool(d.get('SetWoodyXOnUse'))
        self.woody_target_y = d.get('WoodyTargetY') or 0.0
        self.set_olga_x_on_use = bool(d.get('SetOlgaXOnUse'))
        # RoutineActionUse.OnActionStarted's teleport (cs:205-208)
        self.teleport_rott_on_use = bool(d.get('TeleportRottweilerOnUse'))
        self.rott_teleport_offset = vec2('RottweilerTeleportOffset')
        # the Bed state (TrickItem.cs:124, 136; RoutineActionUse.cs:302-306,
        # 513-516) — CanWoodyUse refuses a slept-in bed
        self.is_bed = bool(d.get('IsBed'))
        self.is_rottweiler_sleeping = False
        # the toilet rush (TrickItem.CauseRushToToilet, cs:683-686)
        self.rush_to_toilet = bool(d.get('RushToToilet'))
        self.cause_sickness = bool(d.get('CauseSicknessWhenTricked'))
        # the hit-pawn choreography (Rottweiler.cs:737-753)
        self.pawn_to_affect = ref('PawnToAffectWhenTricked')
        self.pawn_to_affect_only_linked = bool(d.get('PawnToAffectOnlyWhenLinked'))
        self.show_item_when_affected = bool(d.get('ShowItemWhenAffected'))
        self.change_item_anim_when_affected = bool(d.get('ChangeItemAnimationWhenAffected'))
        self.item_anim_when_affected = _anim_name(d.get('ItemAnimationWhenAffected'))
        self.change_item_anim_when_angry = bool(d.get('ChangeItemAnimationWhenAngry'))
        self.item_anim_when_angry = _anim_name(d.get('ItemAnimationWhenAngry'))
        self.use_olga_tricked_flag = False   # Item.UseOlgaTrickedAnimation
        self.use_mother_tricked_flag = False  # Item.UseMotherTrickedAnimation
        # the angry flow (Rottweiler.PlayAngryAnimation)
        self.reuse_after_fix = bool(d.get('ReuseAfterFix'))
        self.angry_without_animations = bool(d.get('AngryWithoutAnimations'))
        self.fix_directly = bool(d.get('FixDirectly'))
        self.rott_extra_angry = d.get('RottweilerExtraAngryAnimation') or []
        self.before_angry = _anim_name(d.get('BeforeAngry'))
        self.sand_castle_flag = bool(d.get('SandCastleBehavior'))
        # TrickItem.RottweilerUse's hide arms (TrickItem.cs:574-593)
        self.hide_during_rott_animation = bool(d.get('HideDuringRottAnimation'))
        self.hide_object_during_animation = ref('HideObjectDuringAnimation')
        self.disable_collider_after_use = bool(d.get('DisableColliderAfterUse'))
        self.give_bowling_when_tricked = bool(d.get('GiveBowlingBallWhenTricked'))
        self.remove_bowling = bool(d.get('RemoveBowlingBall'))
        self.force_fuckedup_when_tricked = bool(d.get('ForceFuckedUpAnimWhenTricked'))
        self.idle_fucked_up = _anim_name(d.get('IdleFuckedUp'))
        self.use_fucked_up = _anim_name(d.get('UseFuckedUp'))
        # the item-side use animations (TrickItem.cs:947-994)
        self.use_normal = _anim_name(d.get('UseNormal'))
        self.use_tricked_single = _anim_name(d.get('UseTricked'))
        self.use_normal_sequence = d.get('UseNormalSequence') or []
        self.play_use_normal_seq = bool(d.get('PlayUseNormalSequence'))
        self.play_use_tricked_seq = bool(d.get('PlayUseTrickedSequence'))
        # the final stand-point shifts (Rottweiler.CheckFinalPosition,
        # cs:1241-1291; ActionManager.cs:180-191)
        self.final_normal = vec2('FinalDeltaLocationNormal')
        self.final_tricked = vec2('FinalDeltaLocationAfterTrick')
        self.final_linked = vec2('FinalDeltaLocationAfterLinkedTrick')
        self.exact_normal = bool(d.get('ExactPositionNormal'))
        self.exact_tricked = bool(d.get('ExactPositionNormalTricked'))
        self.exact_linked = bool(d.get('ExactPositionLinkedTricked'))
        self.use_final_positions_in_beginning = bool(d.get('UseFinalPositionsInBeginning'))
        # UseAtOtherPlace / ShouldReturn (TrickItem.cs:32-38, 599-607)
        self.should_return = bool(d.get('ShouldReturn'))
        self.at_home = True                   # TrickItem.AtHome
        # the exit deltas (RoutineActionUse.StopAction, cs:428-480)
        self.dont_use_on = ref('DontUseOn')
        self.still_use_not_tricked_delta = bool(d.get('StillUseItemNotTrickedExitDeltaAfterTrick'))
        self.rott_prime_exit_delta = vec2('RottweilerPrimeExitDelta')
        self.rott_use_not_tricked_exit_delta = vec2('RottweilerUseItemNotTrickedExitDelta')
        self.exit_delta_aux = False           # RottweilerUseItemExitDeltaAux
        self.exit_delta_not_tricked_aux = False
        # Woody-side hide flows (Item.InternalUse / PreUse, cs:1919-1953,
        # 2225-2235; Woody.cs:237-250, 381-385)
        self.hide_during_woody_anim = bool(d.get('HideDuringWoodyAnim'))
        self.hide_during_woody_use_anim = bool(d.get('HideDuringWoodyUseAnim'))
        self.hide_other_object_woody = ref('HideOtherObjectDuringWoodyAnim')
        self.hide_before_use = bool(d.get('HideBeforeUse'))
        self.hide_after_use = bool(d.get('HideAfterUse'))
        self.show_after_use = bool(d.get('ShowAfterUse'))
        self.pawn_to_change_layer_during_hide = ref('PawnToChangeLayerDuringHide')
        self.layer_depth = d.get('LayerDepth')
        # the tricked overlay object (TrickItem.cs:20, 295-299, 400-410)
        self.tricked_object_go = ref('TrickedObject')
        self.is_ground_trick = bool(d.get('IsGroundTrick'))
        self.dont_show_on_fix = bool(d.get('DontShowOnFix'))
        self.next_action_after_gramaphone = False   # set by FixAll
        self.ignore_woody_when_use = bool(d.get('IgnoreWoodyWhenUse'))
        self.harpoon_aux = False              # Item.harpoonAux
        self.child_renderers = [(c or {}).get('path')
                                for c in (d.get('ChildRenderers') or [])]
        self.object_to_show_before_angry_go = ref('ObjectToShowBeforeAngryAnimation')
        # TrickItem.OnItemAnimationCompleted returns the use pose to idle
        # when AnimateAfterUse (TrickItem.cs:116, 1074-1077)
        self.animate_after_use = bool(d.get('AnimateAfterUse'))
        # the Mother's angry-at-the-neighbour set (Item.cs:1037-1041)
        self.mother_rott_angry = d.get('MotherRottweilerAngryAnimation') or []
        # -- the full TrickItem.PlayAnimation dispatch (cs:791-916) -------
        self.rott_compound_use_tricked = d.get('RottweilerCompoundUseTricked') or []
        self.olga_compound_use_tricked = d.get('OlgaCompoundUseTricked') or []
        self.rott_custom_tricked = d.get('RottweilerCustomTricked') or []
        self.olga_custom_tricked = d.get('OlgaCustomTricked') or []
        self.play_custom_tricked = bool(d.get('PlayCustomTrickedSequence'))
        self.rott_use_fuckedup = d.get('RottweilerUseFuckedUp') or []
        self.olga_use_fuckedup = d.get('OlgaUseFuckedUp') or []
        self.should_play_rott_fuckedup = bool(d.get('ShouldPlayRottweilerFuckedUpAnim'))
        self.depends_nfh2 = ref('DependsOnNFH2')
        self.depends_on_shade_tricked = bool(d.get('DependsOnWhenShadeTricked'))
        self.use_olga_tricked_anim_flag = bool(d.get('UseOlgaTrickedAnim'))
        self.linked_trick_rush_toilet = ref('LinkedTrickRushToilet')
        self.linked_trick_rush_toilet_target = ref('LinkedTrickRushToiletTarget')
        # DoubleRequiredItemsBehavior's swap partners (Item.cs:1734-1758)
        self.second_idle_tricked = _anim_name(d.get('SecondIdleTricked'))
        self.second_already_tricked = False
        self.rott_use_second_tricked = d.get('RottweilerUseSecondTrickedAnimation') or []
        self.use_multiple_times = bool(d.get('UseMultipleTimes'))
        self.hover_anim = _anim_name(d.get('HoverAnim'))
        self.idle_linked_tricked = _anim_name(d.get('IdleLinkedTricked'))
        self.compound_trick_score_v = d.get('CompoundTrickScore') or 0
        # the extra-coin flags (Rottweiler.cs:613-693 Modern; the Classic
        # build pays them through the Extra* calculations)
        self.extra_coin_linked = bool(d.get('ExtraCoinLinkedTrick'))
        self.compound_extra_coin = bool(d.get('CompoundExtraCoin'))
        self.plant_carnivore_extra = bool(d.get('PlantCarnivoreExtraAnger'))
        self.extra_coin_206 = bool(d.get('ExtraCoin206'))
        self.extra_coin_210 = bool(d.get('ExtraCoin210'))
        self.dog_basket_210 = ref('DogBasketBehavior210')
        # AnimationsToControl (Item.cs:2676-2738)
        self.enable_anim_index_control = bool(d.get('EnableAnimIndexControl'))
        self.anims_to_control = d.get('AnimationsToControl') or []
        self.current_sequence = None       # Item.CurrentAnimationSequence
        self.current_seq_index = 0         # Item.CurrentSequenceIndex
        # the dexterity minigame (Item.cs:478-497, 1438-1507)
        self.dexterity = bool(d.get('Dexterity'))
        self.dexterity_trick_item = bool(d.get('DexterityTrickItem'))
        self.dexterity_unlocker = d.get('DexterityUnlocker') or 'IT_NONE'
        self.dexterity_animation = _anim_name(d.get('DexterityAnimation'))
        self.play_dexterity_seq = bool(d.get('PlayDexterityAnimationSequence'))
        self.dexterity_sequence = d.get('DexterityAnimationSequence') or []
        self.dexterity_cannot_lose = bool(d.get('DexterityCannotLose'))
        self.dexterity_keep_item = bool(d.get('DexterityKeepItem'))
        self.dexterity_keep_use_item = bool(d.get('DexterityKeepUseItem'))
        self.take_item_count = d.get('TakeItemCount') or 0
        self.hide_in_dexterity = bool(d.get('HideInDexterity'))
        self.dexterity_run_other = bool(d.get('DexterityRunOtherAnimationWhenFinished'))
        self.activate_trick_if_search = bool(d.get('ActivateTrickItemIfSearchItem'))
        self.dexterity_hide_object = False  # DexterityComponent.HideObjectDuringDexterity
        self.dexterity_alert = ref('DexterityAlert')
        # the remaining name-hack targets
        self.rabbit_206 = ref('Rabbit206')
        self.extra_item_aux = ref('ExtraItemAux')
        self.activate_item_after_using = ref('ActivateItemAfterUsingObject')
        self.delay_activate_after_using = d.get('DelayActivateItemAfterUsingObject') or 0.0
        self.captain_door_1 = ref('CaptainDoor214')
        self.captain_door_2 = ref('SecondCaptainDoor214')
        self.extra_item = ref('ExtraItem')
        self.change_tooltip_when_tricked = bool(d.get('ChangeToolTipWhenTricked'))
        self.name_string = d.get('NameString') or ''
        self.go_next_action = False        # Item.GoNextAction
        self.skip_action = False           # Item.SkipAction (Drawing.Fix)
        # the Mother's alternating DeckChair use (Item.cs:198, 1117-1137)
        self.is_mother_second_use = bool(d.get('IsMotherSecondUseAnimation'))
        self.execute_once_mother = False   # Item.ExecuteOnceAnimationMother206
        self.play_angry_after_toilet = False  # PlayAngryAnimationAfterGoingToiletNFH2
        self.restart_after_tricked = bool(d.get('RestartCurrentActionAfterTricked'))
        self.activate_item_after_fix = ref('ActivateItemAfterFix')
        self.fix_item_trick_linked = ref('FixItemTrickLinked')
        self.block_after_fix = bool(d.get('BlockAfterFix'))
        dwl = d.get('DeltaWoodyLocation') or {}
        self.delta_woody_x = dwl.get('x', 0.0)
        self.delta_woody_y = dwl.get('y', 0.0)
        # the neighbour's use dragging Olga along (TrickItem.cs:911-914,
        # 1227-1238; ActionManager.OlgaExtraAnimations reads them too)
        self.rott_use_olga_seq = d.get('RottweilerUseOlgaAnimationSequence') or []
        self.rott_use_tricked_olga_seq = d.get('RottweilerUseTrickedOlgaAnimationSequence') or []
        # the sleep bar the item's use activates (Item.cs:556-558)
        self.progress_bar_animation = bool(d.get('ProgressBarAnimation'))
        self.progress_bar_object = (d.get('ProgressBarObject') or {}).get('path')
        # the Drawing subclass's cycling smear (Drawing.cs:7-79)
        self.drawing_current = 1           # CurrentDrawingAnimation = Drawing1
        self.drawing_done_cleaning = False
        self.cause_slip = bool(d.get('CauseSlip'))
        sd = d.get('SurpriseDeltaLocation') or {}
        self.surprise_delta = (sd.get('x', 0.0), sd.get('y', 0.0))
        # the facing-matched surprise sets (RoutineActionSurpriseNear and the
        # SameZone yell both read them)
        self.surprise_left = d.get('SurpriseSequenceLeft') or []
        self.surprise_right = d.get('SurpriseSequenceRight') or []

    def cause_rush_to_toilet(self, items):
        """TrickItem.CauseRushToToilet (TrickItem.cs:683-686)"""
        if self.rush_to_toilet:
            return True
        if not self.tricked and self.depends_on is not None:
            dep = items.get(self.depends_on)
            return dep is not None and dep.tricked and dep.rush_to_toilet
        return False

    @property
    def target_x(self):
        """Item.TargetLocation = position + DeltaLocation"""
        return self.x + self.dx

    def move_x(self, role):
        """Item.GetMoveLocation: Olga and Mother stand offset, everyone else
        at TargetLocation itself."""
        if role == 'Olga':
            return self.target_x + self.delta_olga_x
        if role == 'Mother':
            return self.target_x + self.delta_mother_x
        return self.target_x

    def sequence_for(self, role, tricked, items=None):
        """Item.PlayAnimation picks one array and plays it. No fallback: an
        empty array means this character has no business using the item.
        The linked-pair head (TrickItem.cs:804-816) comes first: both halves
        tricked plays RottweilerUseTrickedLinkedAnimation on the neighbour
        (Olga and Mother fall back to their tricked sets there)."""
        if items is not None and self.linked_item_trick is not None \
                and self.tricked and self.use_tricked_linked:
            linked = items.get(self.linked_item_trick)
            if linked is not None and linked.tricked:
                if role == 'Rottweiler':
                    return self.use_tricked_linked
                return self.use_tricked_anim.get(role) or []
        table = self.use_tricked_anim if tricked else self.use_anim
        return table.get(role) or []

    def should_destroy(self):
        """TrickItem.ShouldDestroy (TrickItem.cs:1090-1093)"""
        return self.destroy_after_use_tricked or \
            self.remove_from_routine_after_use_tricked

    def is_tricked(self, items=None):
        """TrickItem.IsTricked (TrickItem.cs:258), including the DependsOn
        chain when the item table is provided."""
        direct = self.tricked and not self.use_at_other_place and not self.neutral
        via = False
        if items is not None and self.depends_on is not None:
            dep = items.get(self.depends_on)
            if dep is not None and dep.tricked and dep.got_tricked and \
                    (not self.use_depends_on_when_tricked or self.tricked):
                via = True
        return (direct or via) and not self.was_priming and not self.fucked_up


class Door:
    """A zone link. Passing one plays an animation on the *door's* controller —
    the sheets contain the walking character, so the pawn hides during transit.
    """
    __slots__ = ('name', 'pid', 'x', 'y', 'zone', 'link_to', 'locked',
                 'door_type', 'enter', 'leave', 'rott_enter', 'rott_leave',
                 'exit_anim', 'idle', 'sprite', 'passing', 'should_walk_up',
                 'use_distance', 'item_use_height', 'delta_use_height',
                 'dx', 'dy', 'rott_exit', 'alternate_idle', 'use_alternate_idle',
                 'complex_move', 'nfh2_stairs', 'pawn_deltas', 'passing_nfh2',
                 'is_transition')

    def __init__(self, name, pid, x, y, zone, link_to, locked, door_type, d):
        self.name = name; self.pid = pid; self.x = x; self.y = y
        self.zone = zone; self.link_to = link_to; self.locked = locked
        self.door_type = door_type
        # enter/leave are ItemAnimationState and play on the door; ExitAnimation
        # is an AnimationState and loops on the pawn once it is through
        self.enter = _anim_name(d.get('WoodyEnterAnimation'))
        self.leave = _anim_name(d.get('WoodyLeaveAnimation'))
        self.rott_enter = _anim_name(d.get('RottweilerEnterAnimation'))
        self.rott_leave = _anim_name(d.get('RottweilerLeaveAnimation'))
        self.exit_anim = _anim_name(d.get('ExitAnimation'))
        self.idle = _anim_name(d.get('IdleAnimation'))
        self.sprite = None
        self.passing = None                 # Door.PassingPawn
        self.should_walk_up = bool(d.get('ShouldWalkUp'))
        self.use_distance = d.get('UseDistance') or 0.01
        self.item_use_height = d.get('ItemUseHeight') or 0.03
        self.delta_use_height = d.get('DeltaUseHeight') or 0.0
        dl = d.get('DeltaLocation') or {}
        self.dx = dl.get('x', 0.0); self.dy = dl.get('y', 0.0)
        # RoutineActionMove.SameZone reads the last door's exit offset
        # (RoutineActionMove.cs:121)
        rel = d.get('RottweilerExitLocation') or {}
        self.rott_exit = (rel.get('x', 0.0), rel.get('y', 0.0))
        # Door.Unlock switches to the alternate idle (Door.cs:198-223)
        self.alternate_idle = _anim_name(d.get('AlternateIdleAnimation'))
        self.use_alternate_idle = False
        # the NFH2 walk-through transitions (Item.ComplexMove, Door.NFH2Stairs)
        self.complex_move = bool(d.get('ComplexMove'))
        self.nfh2_stairs = bool(d.get('NFH2Stairs'))
        # Item.GetTargetLocation's per-pawn door deltas (Item.cs:2010-2050)
        self.pawn_deltas = {}
        for role, key in (('Woody', 'DeltaWoodyDoorLocation'),
                          ('Rottweiler', 'DeltaRottweilerDoorLocation'),
                          ('Olga', 'DeltaOlgaDoorLocation'),
                          ('Mother', 'DeltaMotherDoorLocation')):
            v = d.get(key) or {}
            self.pawn_deltas[role] = (v.get('x', 0.0), v.get('y', 0.0))
        self.passing_nfh2 = None            # Door.PassingPawnTransitionNFH2
        self.is_transition = False          # the component class, set by _build


# every ActorBehavior / RoutineBehavior / SearchBehavior subclass shipped in
# the two seasons' scenes, plus the Kid pawn's helper classes; the exporter
# already wrote their serialized fields
BEHAVIOR_TYPES = (
    'Level101Behavior', 'Level105Behavior', 'Level105RoutineBehavior',
    'Level108Behavior', 'Level109Behavior', 'Level110Behavior',
    'Level113Behavior', 'Level114Behavior', 'Woody114Behavior',
    'VacuumBehavior', 'RollerSkaterBehavior', 'TrickProgressBarBehavior',
    'Level201Behavior', 'Level202Behavior', 'Level204Behavior',
    'Level204OlgaBehavior', 'Level206Behavior', 'Level206MotherBehavior',
    'Level206RoutineBehavior', 'Level207MotherBehavior', 'Level208Behaviors',
    'Level210Behavior', 'Level211Behavior', 'Level211LifeBoatBehavior',
    'Level212Behavior', 'Level213Behavior', 'Level213OlgaBehavior',
    'FifiBehavior', 'SandCastleBehavior', 'SkiBehavior',
    'BirdMovementBehavior', 'BirdPerchBehavior', 'ParrotLedgeBehavior',
    'ParrotLedgeFallBehavior', 'ParrotLedgeJumpBehavior', 'PoolJumpBehavior',
    'IndianPlatformBehavior', 'OlgaBraBehavior', 'OlgaSubmarineBehavior',
    'BraSearchBehavior', 'MugBehavior', 'ToiletBehavior',
    'MotherSleepBehaviour', 'MotherWakeSleepBehavior',
    'RottweilerMotherBehaviour', 'WashbucketBehavior',
)


class Level:
    def __init__(self, path):
        raw = json.load(open(path))
        self.path = path
        self._raw_scene = raw.get('scene')
        self._season2 = '/s2/' in path.replace('\\', '/')
        self._bg_texture = raw.get('background')
        self.scene = raw.get('unity_scene') or raw['scene']
        self.name = os.path.basename(self.scene).replace('.unity', '')
        self.objs = raw['objects']
        self._transform_of = {}
        self._comps = {}
        for pid, o in self.objs.items():
            if o['type'] == 'GameObject' and 'data' in o:
                comps = o['data']['components']
                self._comps[int(pid)] = comps
                for c in comps:
                    if c['type'] == 'Transform':
                        self._transform_of[int(pid)] = c['path']
        self.quads = raw.get('quads') or []          # world-space textured planes
        self.quads_by_go = {q['go']: q for q in self.quads if 'go' in q}
        # the HUD component's resolved textures/rects (tools/export_level.py)
        self.hud = ((raw.get('hud') or {}).get('HUD') or [None])[0]
        self._hud_raw = raw.get('hud') or {}
        # Zone.BubbleIcon textures for MoveOnly think bubbles, keyed by the
        # component pid; the GO pid alias joins after the build
        self.bubble_icons = {int(k): v
                             for k, v in (raw.get('bubble_icons') or {}).items()}
        self.background = None      # (texture name, x, y, w, h) in world units
        self.sprites = []
        self.zones = []
        self.doors = []
        self.graph = {}             # zone pid -> [(neighbour pid, Door)]
        self.pawns = {}             # 'Woody' -> {'sprite','zone','speed'}
        self.items = {}             # component pid -> Item
        self.routines = []          # ActionManager models
        self.game_info = {}         # GameInfo serialized fields
        self.behaviors = []         # serialized *Behavior components
        self.progress_bars = []     # ProgressBar components
        self.dexterity = {}         # DexterityComponent pid -> spec
        self._zone_comp = {}        # Zone component pid -> Zone
        self._build()

    def _level_location_index(self):
        """Actor.Start repositions every actor to LevelLocations[i] where
        i = GetGameWithoutTutorialLevelIndex(). For NFH1 that is
        buildIndex - 5; for NFH2, buildIndex + 12 (GetLevelIndex adds 17)."""
        import re
        m = re.match(r'level(\d+)$', self._raw_scene or '')
        if not m:
            return -1
        build = int(m.group(1))
        name = os.path.basename(self.scene)
        if re.match(r'Level2\d\d', name) or self._season2:
            return build + 12
        return build - 5

    # -- helpers ---------------------------------------------------------
    def _o(self, pid):
        return self.objs.get(str(pid))

    def _go_of(self, comp):
        d = comp.get('data') or {}
        g = d.get('gameObject')
        if g is None:
            g = (d.get('m_GameObject') or {}).get('path')
        return g

    def _transform(self, go):
        tp = self._transform_of.get(go)
        return self._o(tp)['data'] if tp else None

    @staticmethod
    def _pos(tr):
        """world position; the exporter composes the hierarchy for us"""
        return tr.get('world_position') or tr['position']

    def _component(self, go, type_name):
        for c in self._comps.get(go, []):
            if c['type'] == type_name:
                return self._o(c['path'])
        return None

    def _active(self, go):
        o = self._o(go)
        return bool(o and 'data' in o and o['data'].get('active'))

    def _add_progress_bar(self, pid, o):
        """ProgressBar's serialized fields (ProgressBar.cs:5-69); the bar is
        drawn at its own transform's screen position (cs:262-264)"""
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        pos = self._pos(tr) if tr else [0.0, 0.0, 0.0]
        self.progress_bars.append({
            'pid': pid, 'go': go, 'active': self._active(go),
            'item': (d.get('CorrespondingItem') or {}).get('path'),
            'actor': d.get('Actor'),
            'blind': bool(d.get('PlayPawnBlindAnimation')),
            'mother_210': bool(d.get('Mother210')),
            'seqs': d.get('AnimationSequences') or [],
            'rect': d.get('ProgressRect') or {},
            'delta': d.get('DeltaProgressRect') or {},
            'empty': d.get('ProgressBarEmpty'),
            'full': d.get('ProgressBarFull'),
            'rott_hud': d.get('RottweilerHUDProgressFull'),
            'mother_hud': d.get('MotherHUDProgressFull'),
            'x': pos[0], 'y': pos[1]})
        # the exporter's resolved copy carries the texture names
        spec = self.progress_bars[-1]
        for e in (self._hud_raw.get('ProgressBar') or []):
            if (e.get('m_GameObject') or {}).get('path') != go:
                continue
            for k_src, k_dst in (('ProgressBarEmpty', 'empty'),
                                 ('ProgressBarFull', 'full'),
                                 ('RottweilerHUDProgressFull', 'rott_hud'),
                                 ('MotherHUDProgressFull', 'mother_hud')):
                v = e.get(k_src)
                if isinstance(v, dict) and v.get('texture'):
                    spec[k_dst] = v['texture']

    def _add_dexterity(self, pid, o):
        """DexterityComponent's serialized fields (DexterityComponent.cs);
        the exporter's resolved copy carries the texture names"""
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        pos = self._pos(tr) if tr else [0.0, 0.0, 0.0]
        spec = {'pid': pid, 'go': go,
                'item': (d.get('alerter') or {}).get('path'),
                'hide_object': bool(d.get('HideObjectDuringDexterity')),
                'fg_aux': d.get('ForegroundRectAux') or {},
                'bg_aux': d.get('BackgroundRectAux') or {},
                'item_aux': d.get('BackgroundTextureItemRectAux') or {},
                'fg': None, 'bg': None, 'bg_wrong': None,
                'bg_item': None, 'full': None,
                'x': pos[0], 'y': pos[1]}
        for e in (self._hud_raw.get('DexterityComponent') or []):
            if (e.get('m_GameObject') or {}).get('path') != go:
                continue
            for k_src, k_dst in (('ForegroundTexture', 'fg'),
                                 ('BackgroundTexture', 'bg'),
                                 ('BackgroundTextureWrong', 'bg_wrong'),
                                 ('BackgroundTextureItem', 'bg_item'),
                                 ('FieldAlarmFull', 'full')):
                v = e.get(k_src)
                if isinstance(v, dict) and v.get('texture'):
                    spec[k_dst] = v['texture']
        self.dexterity[pid] = spec

    # -- build -----------------------------------------------------------
    def _build(self):
        for pid, o in self.objs.items():
            t = o['type']
            if t == 'Zone' and 'data' in o:
                self._add_zone(int(pid), o)
            elif t in ('Door', 'Transition') and 'data' in o:
                self._add_door(int(pid), o)
            elif t in ('TrickItem', 'SearchItem', 'HideItem', 'GroundItem',
                       'InspectItem', 'Alerter', 'Drawing', 'Rake',
                       'Toilet', 'Television') and 'data' in o:
                self._add_item(int(pid), o)
            elif t in ('ItemAnimationController', 'PawnAnimationController') and 'data' in o:
                self._add_sprite(o)
            elif t in BEHAVIOR_TYPES and 'data' in o:
                go = self._go_of(o)
                self.behaviors.append({'type': t, 'pid': int(pid),
                                       'go': go, 'data': o['data'],
                                       'active': self._active(go)})
            elif t == 'ProgressBar' and 'data' in o:
                self._add_progress_bar(int(pid), o)
            elif t == 'DexterityComponent' and 'data' in o:
                self._add_dexterity(int(pid), o)
        self.sprites.sort(key=lambda s: -s.depth)      # far (high) first
        self._find_background()
        self._build_graph()
        self._find_pawns()
        self._link_item_sprites()
        self._find_routines()
        self._apply_zone_bounds()
        self._apply_level_locations()
        self._find_game_info()
        # CameraMover's level bounds: the viewport corners clamp inside
        # [MinX, MaxX] x [MinY, MaxY] (CameraMover.cs:378-394), which is why
        # the original never shows the void beyond the house
        self.camera_bounds = None
        cm = next((o['data'] for o in self.objs.values()
                   if o['type'] == 'CameraMover' and 'data' in o), None)
        if cm and cm.get('MaxX') is not None:
            self.camera_bounds = (cm.get('MinX') or 0.0, cm.get('MaxX') or 0.0,
                                  cm.get('MinY') or 0.0, cm.get('MaxY') or 0.0)
        # Level.Start computes the entrance and start points from the named
        # zones' transforms plus the serialized offsets (Level.cs:199-208);
        # Woody.Start parks him at StartLocation and he walks to
        # EntranceLocation once the intro lets him (Woody.cs:187-192, 223-229)
        self.entrance_location = None
        self.start_location = None
        self.start_zone = None
        lvl = next((o['data'] for o in self.objs.values()
                    if o['type'] == 'Level' and 'data' in o), None)
        if lvl:
            def _point(zone_name, off_key):
                off = lvl.get(off_key) or {}
                for z in self.zones:
                    if z.name == (zone_name or ''):
                        return (z.tx + off.get('x', 0.0),
                                z.ty + off.get('y', 0.0)), z.pid
                return None, None
            self.entrance_location, _ = _point(lvl.get('EntranceZoneName'),
                                               'EntranceLocationOffset')
            self.start_location, self.start_zone = _point(
                lvl.get('StartZoneName'), 'StartLocationOffset')
        # a MoveOnly action stores the zone's GameObject; alias the zone
        # components' bubble icons onto it
        for pid in list(self.bubble_icons):
            o = self._o(pid)
            go = self._go_of(o) if o else None
            if go is not None:
                self.bubble_icons.setdefault(go, self.bubble_icons[pid])
        # Item.Start ends in SetPrimed(Primed) (Item.cs:697): the primed branch
        # adds DeltaPrimedLocation to DeltaLocation, the unprimed one subtracts
        # it (Item.cs:1201-1210; the WaterPuddle name-hack is not ported)
        for it in self.items.values():
            if it.delta_primed_x or it.delta_primed_y:
                sign = 1.0 if it.primed else -1.0
                it.dx += sign * it.delta_primed_x
                it.dy += sign * it.delta_primed_y

    def _add_zone(self, pid, o):
        go = self._go_of(o)
        tr = self._transform(go)
        box = self._component(go, 'BoxCollider')
        if not tr or not box:
            return
        p = self._pos(tr); s = box['data']['size']; c = box['data']['center']
        z = Zone(self._o(go)['data']['name'], go,
                 p[0] + c[0], p[1] + c[1], s[0], s[1],
                 bool(o['data'].get('ExitZone')),
                 ty=p[1], tx=p[0],
                 height_delta=o['data'].get('HeightDelta') or 0.0)
        self.zones.append(z)
        self._zone_comp[pid] = z          # behaviors reference the component

    def zone_by_component(self, pid):
        """a serialized Zone reference names the component, not the object"""
        return self._zone_comp.get(pid)

    def _zone_of(self, go):
        """the Zone component on this object's parent, as ZoneController does"""
        tp = self._transform_of.get(go)
        if tp is None:
            return None
        f = self._o(tp)['data'].get('father')
        if not f:
            return None
        pgo = self._o(f)['data'].get('gameObject')
        if pgo is None:
            return None
        for c in self._comps.get(pgo, []):
            if c['type'] == 'Zone':
                return pgo
        return None

    def _add_door(self, pid, o):
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        if not tr:
            return
        p = self._pos(tr)
        link = (d.get('LinkTo') or {}).get('path')
        door = Door(self._o(go)['data']['name'], pid, p[0], p[1],
                    self._zone_of(go), link,
                    bool(d.get('Locked')), d.get('DoorType'), d)
        door.is_transition = o['type'] == 'Transition'
        self.doors.append(door)

    def _add_item(self, pid, o):
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        if not tr:
            return
        p = self._pos(tr)
        dl = d.get('DeltaLocation') or {}
        zc = (d.get('Zone') or {}).get('path')
        zgo = self._go_of(self._o(zc)) if zc and self._o(zc) else None
        it = Item(self._o(go)['data']['name'], pid, o['type'],
                  p[0], p[1], zgo,
                  dl.get('x', 0.0), dl.get('y', 0.0), d)
        it.go = go
        self.items[pid] = it

    def _link_item_sprites(self):
        """Item.Start: AnimController = GetComponentInChildren — the controller
        is on the item's own GameObject or a child, never found by position."""
        by_go = {}
        for s in self.sprites:
            if s.kind == 'ItemAnimationController':
                by_go.setdefault(s.go, s)

        def find(go, depth=0):
            """GetComponentInChildren is recursive"""
            if go in by_go:
                return by_go[go]
            if depth > 6:
                return None
            tp = self._transform_of.get(go)
            for k in ((self._o(tp)['data'].get('children') or []) if tp else ()):
                kgo = self._o(k)['data'].get('gameObject')
                hit = find(kgo, depth + 1)
                if hit is not None:
                    return hit
            return None

        for it in self.items.values():
            go = self._go_of(self._o(it.pid))
            it.sprite = find(go)
            box = self._component(go, 'BoxCollider')
            if box and 'data' in box:
                b = box['data']
                it.collider = (it.x + b['center'][0], it.y + b['center'][1],
                               b['size'][0], b['size'][1])
        for d in self.doors:
            d.sprite = find(self._go_of(self._o(d.pid)))

    def _apply_zone_bounds(self):
        """Level.Start() rebuilds every zone from lists on the Level component,
        indexed by the number in the zone's name. The serialized zone transforms
        are placeholders:

            zone.position = (x, ZonesY[i], z) + zoneController.position
            zone.HeightDelta = ZonesHeightDeltas[i]
            zone.collider.size = ZonesSizes[i]
            zone.SetPlayLeft/Right(ZonesPlayLeft/Right[i])   # around the NEW x
        """
        lvl = None
        for o in self.objs.values():
            if o['type'] == 'Level' and 'data' in o:
                lvl = o['data']
                break
        if not lvl:
            return
        ctrl = (0.0, 0.0)
        for pid, o in self.objs.items():
            if o['type'] == 'ZoneController' and 'data' in o:
                go = self._go_of(o)
                tr = self._transform(go)
                if tr:
                    p = self._pos(tr)
                    ctrl = (p[0], p[1])
                break
        ys = lvl.get('ZonesY') or []
        sizes = lvl.get('ZonesSizes') or []
        left = lvl.get('ZonesPlayLeft') or []
        right = lvl.get('ZonesPlayRight') or []
        hd = lvl.get('ZonesHeightDeltas') or []
        for z in self.zones:
            try:
                i = int(z.name[4:])
            except (ValueError, IndexError):
                continue
            if i < len(ys):
                new_ty = ys[i] + ctrl[1]
                z.y = z.y - z.ty + new_ty       # keep the collider centre offset
                z.ty = new_ty
            z.x = z.x + ctrl[0]
            z.tx = z.tx + ctrl[0]
            if i < len(sizes):
                sz = sizes[i]
                z.w = sz.get('x', z.w)
                z.h = sz.get('y', z.h)
            if i < len(hd):
                z.height_delta = hd[i]
            if i < len(left):
                z.play_left = z.x - left[i]
            if i < len(right):
                z.play_right = z.x + right[i]

    def _find_game_info(self):
        for o in self.objs.values():
            if o['type'] == 'GameInfo' and 'data' in o:
                d = o['data']
                self.game_info = {
                    'total': d.get('TotalTricksCount') or 0,
                    'winning': d.get('WinningTricksCount') or 0,
                    # the HUD clock and the score screen
                    'time_minutes': d.get('TimeMinutes') or 0.0,
                    'compound_trick_score': d.get('CompoundTrickScore') or 0,
                    'is_tutorial': bool(d.get('IsTutorial')),
                    'dont_show_angry_count': bool(d.get('DontShowAngryCount')),
                }
                return

    def _apply_level_locations(self):
        """Actor.Start: transform.position = LevelLocations[idx]. Shift each
        actor and its sprite by the same delta."""
        idx = self._level_location_index()
        if idx < 0:
            return

        def shift(comp_data, obj):
            ll = comp_data.get('LevelLocations') or []
            if idx >= len(ll):
                return None
            t = ll[idx]
            return t.get('x', 0.0), t.get('y', 0.0)

        for it in self.items.values():
            o = self._o(it.pid)
            pos = shift(o['data'], it)
            if pos is None:
                continue
            dx, dy = pos[0] - it.x, pos[1] - it.y
            it.x, it.y = pos
            if it.sprite is not None:
                it.sprite.x += dx
                it.sprite.y += dy
        for d in self.doors:
            o = self._o(d.pid)
            pos = shift(o['data'], d)
            if pos is None:
                continue
            ddx, ddy = pos[0] - d.x, pos[1] - d.y
            d.x, d.y = pos
            if d.sprite is not None:
                d.sprite.x += ddx
                d.sprite.y += ddy
        for role, spec in self.pawns.items():
            for pid, o in self.objs.items():
                if o['type'] == role and 'data' in o:
                    pos = shift(o['data'], None)
                    if pos is not None:
                        s = spec['sprite']
                        # the sprite is a child; move it with its actor root
                        go = self._go_of(o)
                        tr = self._transform(go)
                        base = self._pos(tr) if tr else (s.x, s.y)
                        s.x += pos[0] - base[0]
                        s.y += pos[1] - base[1]
                    break

    def _find_routines(self):
        for pid, o in self.objs.items():
            if o['type'] != 'ActionManager' or 'data' not in o:
                continue
            d = o['data']
            def parse_action(a):
                ml = a.get('MoveLocation') or {}
                mz = (a.get('MoveZone') or {}).get('path')
                pa = bool(a.get('PostponeAlarm'))
                def ref(field):
                    return (a.get(field) or {}).get('path')
                return {'item': ref('Item'),
                             'duration': a.get('Duration') or 0.0,
                             'max_distance': a.get('MaximumPawnDistanceToAction') or 0.03,
                             'hide_object': bool(a.get('HideObjectDuringUse')),
                             'hide_owner': bool(a.get('HideOwnerDuringUse')),
                             'move_only': bool(a.get('MoveOnly')),
                             'move_x': ml.get('x', 0.0),
                             'move_zone': self._go_of(self._o(mz)) if mz and self._o(mz) else None,
                             'mutex': bool(a.get('MutexAction')),
                             'postpone_alarm': pa,
                             'mutex_anim': a.get('MutexLoopingAnimation'),
                             # RoutineActionUse.OnActionStarted/Stopped release
                             # infinite loops on these referenced targets
                             'stop_inf_item': ref('ItemToStopInfiniteAnimation'),
                             'stop_inf_pawn': ref('PawnToStopInfiniteAnimation'),
                             'stop_inf_pawn_tricked': ref('PawnToStopInfiniteAnimationWhenTricked'),
                             'once_pawn': ref('PawnToIgnoreInfiniteAnimationOnce'),
                             'once_pawn_not_tricked': ref('PawnToIgnoreInfiniteAnimationOnceWhenNotTricked'),
                             'once_pawn_on_end': ref('PawnToIgnoreInfiniteAnimationOnceOnEnd'),
                             'abort_mutex_pawn': ref('PawnToAbortMutexOnFinish'),
                             # OnActionStarted's prime/trick-after-use tail
                             'prime_after_use': ref('GameObjectToPrimeAfterUse'),
                             'prime_after_use_tricked': ref('GameObjectToPrimeAfterUseTricked'),
                             'prime_delay': a.get('PrimeDelay') or 0.0,
                             'prime_tricked_delay': a.get('PrimeTrickedDelay') or 0.0,
                             'trick_after_use': ref('GameObjectToTrickAfterUse'),
                             # walking-prop toggles + the Level105 phone chain
                             # (RoutineActionUse.cs:43-57, 181-200, 256-263)
                             'cake': bool(a.get('CakeAction')),
                             'give_fifi': bool(a.get('GiveFifi')),
                             'remove_fifi': bool(a.get('RemoveFifi')),
                             'give_skates': bool(a.get('GiveSkates')),
                             'remove_skates': bool(a.get('RemoveSkates')),
                             'alert_next': bool(a.get('AlertNext')),
                             # the use side-effect set
                             # (RoutineActionUse.cs:7-101, 201-307, 386-535)
                             'is_toilet': bool(a.get('IsToiletAction')),
                             # an Urgent routine action is approached at a
                             # run (RoutineActionMove.OnActionStarted,
                             # cs:68-75); ContinueToNextAfterFinished then
                             # advances normally (ActionManager.cs:530-538)
                             'urgent': bool(a.get('Urgent')),
                             'freeze_after_completion':
                                 bool(a.get('FreezeAfterCompletion')),
                             'hide_object_tricked': bool(a.get('HideObjectDuringUseTricked')),
                             'hide_object_tricked_delayed': ref('HideObjectDuringUseTrickedWithDelay'),
                             'hide_object_tricked_delay': a.get('HideObjectDuringUseTrickedDelay') or 0.0,
                             'hide_child': bool(a.get('HideChildRendererDuringUse')),
                             'object_to_hide': ref('ObjectToHideDuringUse'),
                             'object_to_hide_tricked': ref('ObjectToHideDuringUseTricked'),
                             'object_to_activate': ref('ObjectToActivateDuringUse'),
                             'pawn_to_hide': ref('PawnToHideDuringUse'),
                             'go_hide_after_use': ref('GameObjectToHideAfterUse'),
                             'go_hide_after_use_tricked': ref('GameObjectToHideAfterUseTricked'),
                             'go_show_after_use': ref('GameObjectToShowAfterUse'),
                             'remove_action_after_use': bool(a.get('RemoveActionAfterUse')),
                             'change_layer_linked': bool(a.get('ChangeLayerInLinkedTricked')),
                             'layer_to_change': a.get('LayerToChange'),
                             'pawn_to_change_layer': ref('PawnToChangeLayer'),
                             'item_to_change_layer': ref('ItemToChangeLayer'),
                             'doors_to_unlock': [(x or {}).get('path')
                                                 for x in (a.get('DoorsToUnlock') or [])],
                             'items_to_unlock': [(x or {}).get('path')
                                                 for x in (a.get('ItemsToUnlock') or [])],
                             'items_to_unlock_tricked': [(x or {}).get('path')
                                                         for x in (a.get('ItemsToUnlockWhenTricked') or [])]}
            acts = [parse_action(a) for a in (d.get('Actions') or [])]
            # ActionManager.ActionsToAddInGame, injected by the tricked
            # Fifi's Mother use (ActionManager.cs:814-842)
            to_add = [parse_action(a)
                      for a in (d.get('ActionsToAddInGame') or [])]
            # Owner names the GameObject, which Season 2 calls "Rottweiler2";
            # the component type is the stable key
            ow = d.get('Owner') or {}
            self.routines.append({'owner': ow.get('type') or ow.get('name'),
                                  'owner_name': ow.get('name'),
                                  'actions': acts,
                                  'actions_to_add': to_add,
                                  'start_index': d.get('ActionStartIndex') or 0,
                                  'loop_from_start': bool(d.get('LoopFromStartIndex')),
                                  'selected_index': d.get('ActionSelectedIndex') or 0,
                                  'frozen': bool(d.get('Frozen'))})

    def _build_graph(self):
        """Exactly ZoneController.Start(): a door links its own zone to the zone
        of whatever it points at."""
        by_pid = {d.pid: d for d in self.doors}
        self.graph = {z.pid: [] for z in self.zones}
        for d in self.doors:
            if d.zone is None or d.link_to is None or d.locked:
                continue
            other = by_pid.get(d.link_to)
            if other is None or other.zone is None:
                continue
            self.graph.setdefault(d.zone, []).append((other.zone, d))

    def find_path(self, start_pid, end_pid):
        """Zone pids from start to end, each with the door to walk through.
        Uniform edge cost, so BFS — Helpers.GetShortestPath adds 1.0 per hop."""
        import collections
        if start_pid == end_pid:
            return []
        prev = {start_pid: None}
        q = collections.deque([start_pid])
        while q:
            cur = q.popleft()
            for nb, door in self.graph.get(cur, ()):
                if nb in prev:
                    continue
                prev[nb] = (cur, door)
                if nb == end_pid:
                    out = []
                    n = nb
                    while prev[n]:
                        c, dr = prev[n]
                        out.append((n, dr))
                        n = c
                    out.reverse()
                    return out
                q.append(nb)
        return None

    def zone_at(self, x, y):
        for z in self.zones:
            if abs(x - z.x) <= z.w * 0.5 and abs(y - z.y) <= z.h * 0.5:
                return z
        return None

    def zone_by_pid(self, pid):
        for z in self.zones:
            if z.pid == pid:
                return z
        return None

    def door_by_pid(self, pid):
        for d in self.doors:
            if d.pid == pid:
                return d
        return None

    def _add_sprite(self, o):
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        if not tr or not self._active(go):
            return
        base = d.get('BaseAnimationPath') or ''
        anims = [Anim(a, base) for a in (d.get('Animations') or [])]
        # keep the serialized index: Level206MotherBehavior patches
        # Animations[23]/[33] by position (Level206MotherBehavior.cs:26-28)
        for i, a in enumerate(anims):
            a.src_index = i
        anims = [a for a in anims if a.sheet]
        if not anims:
            return
        depth = GUI_DEPTH.get(d.get('AnimationGUIDepth'), 32)
        dl = d.get('DeltaLocation') or {}
        # pick the resting pose: an item's IdleNormal, a pawn's DefaultAnimation
        want = None
        # Door keeps its resting pose in IdleAnimation; every other Item uses
        # IdleNormal. 'NONE' means the object is a static quad, not a sprite.
        for owner_type, field in (('Door', 'IdleAnimation'),
                                  ('Transition', 'IdleAnimation'),
                                  ('TrickItem', 'IdleNormal'),
                                  ('SearchItem', 'IdleNormal'),
                                  ('HideItem', 'IdleAnim'),
                                  ('GroundItem', 'IdleNormal'),
                                  ('Alerter', 'IdleNormal'),
                                  ('InspectItem', 'IdleNormal')):
            item = self._component(go, owner_type)
            if item and 'data' in item:
                want = item['data'].get(field)
                # ReturnToIdleAnimation plays the tricked idle when IsTricked
                if field == 'IdleNormal' and item['data'].get('Tricked'):
                    want = item['data'].get('IdleTricked') or want
                # Item.Start ends in SetPrimed(Primed); for a primed TrickItem
                # that plays PlayPrimedAnimation over the idle
                # (Item.cs:697, TrickItem.cs:996-1010, 483-491)
                if field == 'IdleNormal' and item['data'].get('Primed'):
                    prim = item['data'].get('PrimedTricked') \
                        if item['data'].get('Tricked') else None
                    prim = prim if prim and prim != 'NONE' \
                        else item['data'].get('PrimedNormal')
                    if prim and prim != 'NONE':
                        want = prim
                # Alerter.Start plays the SleepSequence instead of an idle
                if owner_type == 'Alerter':
                    seq = item['data'].get('SleepSequence') or []
                    if seq:
                        want = seq[0]
                break
        if want is None:
            for pawn_type in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
                pawn = self._component(go, pawn_type)
                if pawn and 'data' in pawn:
                    want = pawn['data'].get('DefaultAnimation')
                    break
        cur = None
        for i, a in enumerate(anims):
            if a.name == want:
                cur = i; break
        if cur is None:
            # no resting animation: either a pawn (first entry is its idle) or a
            # static object drawn as a quad instead
            if want in (None, 'NONE') and o['type'] == 'ItemAnimationController':
                return
            cur = 0
        p = self._pos(tr)
        self.sprites.append(Sprite(self._o(go)['data']['name'], p[0], p[1],
                                   depth, anims, cur,
                                   dl.get('x', 0.0), dl.get('y', 0.0),
                                   o['type'], go))

    def _find_pawns(self):
        """A pawn's sprite lives on a child object named AnimController, so map
        each pawn component to the sprite underneath it."""
        for pid, o in self.objs.items():
            if o['type'] not in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
                continue
            if 'data' not in o:
                continue
            go = self._go_of(o)
            tp = self._transform_of.get(go)
            if tp is None:
                continue
            kids = self._o(tp)['data'].get('children') or []
            sprite = None
            for k in kids:
                kgo = self._o(k)['data'].get('gameObject')
                for s in self.sprites:
                    if s.kind == 'PawnAnimationController' and \
                            self._go_of_sprite(s) == kgo:
                        sprite = s
                        break
                if sprite:
                    break
            if sprite is None:
                continue
            # Zone is a pointer to the *component*; zones are keyed by their
            # GameObject, so hop across
            zc = (o['data'].get('Zone') or {}).get('path')
            zgo = self._go_of(self._o(zc)) if zc and self._o(zc) else None
            pd = o['data']
            # actions reference pawns by component pid
            # (e.g. PawnToStopInfiniteAnimation, PawnToAbortMutexOnFinish);
            # objs keys are JSON strings, the refs are ints
            pawn_pid = int(pid)
            ctrl = None
            for c in self._comps.get(self._go_of_sprite(sprite) if False else sprite.go, []):
                if c['type'] == 'PawnAnimationController':
                    ctrl = self._o(c['path'])
            cd = (ctrl or {}).get('data') or {}
            self.pawns[o['type']] = {
                'pid': pawn_pid,
                'stand': {'Left': _anim_name(cd.get('StandLeftAnimation')) or 'Stand_Left',
                          'Right': _anim_name(cd.get('StandRightAnimation')) or 'Stand_Right',
                          'Up': _anim_name(cd.get('StandUpAnimation')) or 'Stand_Up',
                          'Down': _anim_name(cd.get('StandDownAnimation')) or 'Stand_Down'},
                'sprite': sprite,
                'zone': zgo,
                # ProcessMovement: position += Velocity * dt * Speed, and
                # WalkOnPath sets Velocity = direction * ForceMagnitude, so a
                # horizontal walk covers Speed * ForceMagnitude per second
                'speed': pd.get('Speed') or 0.0,
                'speed_sneaking': pd.get('SpeedSneaking') or 0.0,
                'force': pd.get('ForceMagnitude') or 0.0,
                'door_force': pd.get('DoorForceMagnitude') or 0.0,
                'run_force': pd.get('RunningForceMagnitude') or 0.0,
                'run_door_force': pd.get('RunningDoorForceMagnitude') or 0.0,
                'door_delta': ((pd.get('DoorDistanceDelta') or {}).get('x', 0.0),
                               (pd.get('DoorDistanceDelta') or {}).get('y', 0.0)),
                'player_height_delta': pd.get('PlayerHeightDelta') or 0.0,
                'zone_level_threshold': pd.get('ZoneLevelThreshold') or 0.0,
                'item_use_height_threshold': pd.get('ItemUseHeightThreshold') or 0.0,
                'portal_up': _anim_name(pd.get('PortalUpAnimation')),
                'portal_down': _anim_name(pd.get('PortalDownAnimation')),
                'angry_decay': pd.get('AngryMeterDecay') or 0.0,
                'notice_near_distance': pd.get('NoticeWhenNearTrickedDistance')
                    if pd.get('NoticeWhenNearTrickedDistance') is not None
                    else 0.03,
                'angry_max': pd.get('AngryMeterMaximum') or 100.0,
                'fear_left': _anim_name(pd.get('FearAnimationLeft')) or 'FearLeft',
                'fear_right': _anim_name(pd.get('FearAnimationRight')) or 'FearRight',
                'win_animation': _anim_name(pd.get('WinAnimation')),
                'is_sleeping': bool(pd.get('IsSleeping')),
                'ignore_woody': bool(pd.get('IgnoreWoody')),
                'animal_tutorial': bool(pd.get('AnimalTutorial')),
                'nfh2': bool(pd.get('NFH2Path')),
                'adjacent_zones': bool(pd.get('AdjacentZonesEnabled')),
                # Woody.Start localizes these keys (Woody.cs:197-205)
                'use_string': pd.get('UseString') or '',
                'with_string': pd.get('WithString') or '',
                'empty_use_string': pd.get('EmptyUseString') or '',
                'look_at_string': pd.get('LookAtString') or '',
                # the fixing-tool chain, serialized inline on the Rottweiler
                # (RoutineActionGrab / RoutineActionUseFixingItem / Return)
                'grab_action': {
                    'sequence': (pd.get('GrabFixingItemAction') or {}).get(
                        'GrabSequence') or [],
                    'postpone_alarm': bool((pd.get('GrabFixingItemAction')
                                            or {}).get('PostponeAlarm')),
                },
                'use_fixing_action': {
                    'sequence': (pd.get('UseFixingItemAction') or {}).get(
                        'UseFixingItemSequence') or [],
                    'should_return': bool((pd.get('UseFixingItemAction')
                                           or {}).get('ShouldReturnFixingItem')),
                    'return_sequence': ((pd.get('UseFixingItemAction') or {}).get(
                        'ReturnFixingItemAction') or {}).get('ReturnSequence') or [],
                },
                # RoutineActionHitWoody is serialized inline on the Rottweiler
                'hit_action': {
                    'sequences': [q for q in (
                        (pd.get('HitWoodyAction') or {}).get('Sequence1') or [],
                        (pd.get('HitWoodyAction') or {}).get('Sequence2') or [],
                        (pd.get('HitWoodyAction') or {}).get('Sequence3') or [],
                        (pd.get('HitWoodyAction') or {}).get('Sequence4') or []) if q],
                    'max_distance': (pd.get('HitWoodyAction') or {}).get(
                        'MaximumPawnDistanceToAction') or 0.03,
                },
                'default': pd.get('DefaultAnimation'),
                # Actor.Behavior / SecondaryBehaviors, Pawn.RoutineBehavior,
                # Woody.SearchBehavior — the level-behavior wiring
                'behavior': (pd.get('Behavior') or {}).get('path'),
                'secondary_behaviors': [
                    (b or {}).get('path')
                    for b in (pd.get('SecondaryBehaviors') or [])
                    if (b or {}).get('path')],
                'routine_behavior': (pd.get('RoutineBehavior') or {}).get('path'),
                'search_behavior': (pd.get('SearchBehavior') or {}).get('path'),
                # the Kid pawn's own animation set (Kid.cs:3-16)
                'kid_crying': _anim_name(pd.get('Crying')),
                'kid_use_crying_sequence': bool(pd.get('UseCryingSequence')),
                'kid_crying_sequence': pd.get('CryingSequence') or [],
                'kid_remote_sequence': _anim_name(pd.get('RemoteSequence')),
                'kid_olga': (pd.get('olga') or {}).get('path'),
                # the toilet run (Rottweiler.ToiletAction, cs:32; MoveToToilet
                # cs:863-867) and the hit-pawn pair (Pawn.cs:123-125)
                'toilet_action': {
                    'item': ((pd.get('ToiletAction') or {}).get('Item')
                             or {}).get('path'),
                    'is_toilet': bool((pd.get('ToiletAction') or {}).get(
                        'IsToiletAction')),
                },
                'wait_in_fear_anim': _anim_name(
                    (pd.get('WaitInFearAction') or {}).get('FearAnimation')),
                'hit_pawn_action': {
                    'sequence': (pd.get('HitPawnAction') or {}).get(
                        'HitPawnSequence') or [],
                    'max_distance': (pd.get('HitPawnAction') or {}).get(
                        'MaximumPawnDistanceToAction') or 0.03,
                },
            }

    def _go_of_sprite(self, sprite):
        return getattr(sprite, 'go', None)

    def _find_background(self):
        """The backdrop is the quad carrying the Level component."""
        for q in self.quads:
            if q.get('is_level'):
                self.background = (q['texture'], q['x'], q['y'], q['w'], q['h'])
                return

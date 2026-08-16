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
    __slots__ = ('name', 'sheet', 'sheet_path', 'cols', 'rows', 'start',
                 'end', 'fps',
                 'ow', 'oh', 'dx', 'dy', 'loop', 'hold', 'pattern',
                 'infinite', 'type_looping', 'sounds', 'blocking',
                 'hide_owner_on_end', 'show_child_on_end',
                 'src_index', 'empty_pattern')

    def __init__(self, d, base_path=''):
        self.name = d.get('Name')
        # AnimationInstance.LoadTexture (AnimationInstance.cs:130-143) does
        # SheetTexture = Resources.Load(BaseAnimationPath + TextureFileName),
        # so an empty TextureFileName means the base path is itself the asset.
        # The exporter resolves that Resources path through the ResourceManager
        # container into the extraction's collision-numbered PNG name
        # (tools/export_level.py resolve_sheet_textures) and stores it as
        # SheetTexture; None means Load found nothing — the animation still
        # runs, DrawAnimation just has no texture (cs:179-186). Older exports
        # without the field fall back to the last path component.
        self.sheet_path = (base_path or '') + (d.get('TextureFileName') or '')
        if 'SheetTexture' in d:
            self.sheet = d['SheetTexture']
        else:
            self.sheet = os.path.basename(self.sheet_path)
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
        # StopSingleAnimation's end-flags (AnimationControllerBase.cs:226-233):
        # Hide_In/BedIn/LorryEnter... hide their owner when they finish, and
        # CarnivorPlantSprayTricked re-shows the acting item's child renderers
        self.hide_owner_on_end = bool(d.get('HideOwnerOnAnimationEnd'))
        self.show_child_on_end = bool(d.get('ShowChildRenderersOnEnd'))
        # AnimationInstance.UsePattern gates the pattern (CurrentIndex,
        # SetStartFrame, AdvanceFrame, ReachedEndFrame — AnimationInstance.cs:
        # 66-76, 186-234): a Pattern serialized next to UsePattern=false is
        # stale data the original never reads (262 instances differ from
        # StartFrame..EndFrame, e.g. L113 LadderTestTransition 15-16 vs a
        # 40-frame pattern). UsePattern with an empty Pattern (36 instances:
        # 14 x Woody's PutEel, whose PatternFile is a GUID stub the build
        # never shipped so SetupPattern loads nothing, and L214's
        # OlgaStandDownInfinite) is a live rule of its own — empty_pattern:
        # ReachedEndFrame is true at once (0 >= 0) and UpdateCurrentFrame
        # never writes, so CurrentFrame stays the instance default 0
        # (AnimationInstance.cs:66-76, 186-234); world.AnimPlayer honours it.
        self.pattern = (d.get('Pattern') or None) if d.get('UsePattern') \
            else None
        self.empty_pattern = bool(d.get('UsePattern')) and not d.get('Pattern')
        self.sounds = [(sd.get('Frame'), sd.get('FileName'))
                       for sd in (d.get('Sounds') or []) if sd.get('FileName')]

    def frame_at(self, t):
        """port scaffolding, not a game rule: a free-running frame index for
        elapsed time t, honouring Pattern when present — only render.draw_sprite
        falls back to it for a sprite nothing is ticking; a live sprite's
        frame is owned by world.AnimPlayer (AnimationControllerBase.Refresh)"""
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
    """one drawable: a world position, a depth, and an animation to play.
    current is the index of the controller's CurrentAnimation, None while
    it has none (AnimationControllerBase.cs:13 — a controller before its
    first SetAnimation draws and refreshes nothing, cs:172-189); hidden is
    AnimationControllerBase.Hidden (cs:55, 177), a separate switch."""
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
                 'play_left', 'play_right', 'ty', 'height_delta', 'tx',
                 'name_string', 'end_string')

    def __init__(self, name, pid, x, y, w, h, is_exit, ty=0.0, height_delta=0.0,
                 tx=0.0):
        self.name = name; self.pid = pid
        self.x = x; self.y = y
        self.w = w; self.h = h; self.exit = is_exit
        self.ty = ty                        # transform y, floor reference
        self.tx = tx                        # transform x (Entrance/StartLocation)
        self.height_delta = height_delta    # Zone.HeightDelta
        self.name_string = ''               # Zone.NameString
        self.end_string = ''                # Zone.EndString
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
                 'woody_delta_use_height', 'use_woody_extra', 'passable',
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
                 'special_bubble_for_mother', 'bubble_mother_icon',
                 'destroy_after_use_tricked',
                 'remove_from_routine_after_use_tricked',
                 'remove_after_first_use', 'main_valve_open',
                 'take_off_iron_primed', 'fix_all', 'use_item_multiple_times',
                 'keep_full', 'trick_after_woody_use', 'depends_pig_keys',
                 'pig_keys', 'pig_milk', 'cow_flowers', 'inventory_to_add',
                 'change_iron_routine',
                 'change_iron_routine_last_path', 'item_removed', 'clickable',
                 'prime_item_aux', 'double_priming_item',
                 'compound', 'compound_required', 'compound_tricked',
                 'compound_tricked_anim', 'compound_double_anim',
                 'inventory_items', 'dont_remove_inventory',
                 'assign_first_inventory_only',
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
                 'required_inventory', 'trick_score', 'sprite',
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
                 'anger_amount', 'extra_coin_anger', 'extra_coin_toilet_211',
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
                 'name_tricked_string', 'name_primed_string',
                 'with_string', 'with_tricked_string', 'with_primed_string',
                 'hide_string_key', 'dont_change_tooltip_when_tricked',
                 'description_string', 'description_tricked',
                 'description_primed', 'description_linked',
                 'description_fixed', 'name_fixed_string',
                 'with_fixed_string', 'use_fixed_strings',
                 'name_fuckedup_string', 'with_fuckedup_string',
                 'delta_desc', 'long_description', 'not_primed_tooltip',
                 'multiple_items_string', 'item_in_use_string',
                 'take_multiple', 'do_nothing_while_used',
                 'block_when_item_pick', 'open_object',
                 'open_render_object', 'leave_toolbox_open', 'close_time',
                 'inventory_tooltips', 'ignore_required_for_desc',
                 'description_fuckedup', 'name_compound', 'with_compound',
                 'description_compound', 'name_compound_tricked',
                 'with_compound_tricked', 'description_compound_tricked',
                 'check_depends_on_tricked', 'empty_drawing_string',
                 'item_that_changes_tooltip', 'is_floor', 'searching_item',
                 'mouse_over_icon', 'mouse_over_after_trick',
                 'change_mouse_over_after_trick', 'primed_mouse_over',
                 'primed_material', 'disable_collider_when_primed',
                 'enable_collider_after_prime', 'disable_mesh',
                 'play_idle_normal_seq', 'idle_normal_sequence',
                 'play_idle_tricked_seq', 'idle_tricked_sequence',
                 'dont_play_idle_on_start', 'ignore_depends_when_fixed',
                 'block_valve_after_fix', 'animate_dependant',
                 'pick_up_without_go',
                 'tip_icon', 'tip_icon_depth', 'tip_delta', 'tip_dimensions',
                 'always_show_tip',
                 'go_next_action', 'skip_action', 'is_mother_second_use',
                 'execute_once_mother', 'play_angry_after_toilet',
                 'restart_after_tricked', 'activate_item_after_fix',
                 'fix_item_trick_linked', 'block_after_fix',
                 'delta_woody_x', 'delta_woody_y',
                 'rott_use_olga_seq', 'rott_use_tricked_olga_seq',
                 'drawing_current', 'drawing_done_cleaning',
                 'progress_bar_animation', 'progress_bar_object',
                 # SearchItem.AcquiredInventoryCount (SearchItem.cs:7) and
                 # Item.ElephantBehaviorAux (Item.cs:564)
                 'acquired_inventory_count', 'elephant_behavior_aux',
                 # TrickItem.OnlyOnceWaterPuddle (TrickItem.cs:170)
                 'only_once_water_puddle')

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
        # the walk-arrival radii, taken as serialized (Item.cs:246 UseDistance
        # = 0.03f, cs:220 ItemUseHeight = 0.01f); MinDistToNextMove reads
        # ItemUseHeight as-is on a walk-up step (Pawn.cs:1112-1119) — 532
        # items serialize 0.0 there and an `or` would have made it 0.03
        self.use_distance = d.get('UseDistance', 0.03)
        self.should_walk_up = bool(d.get('ShouldWalkUp'))
        self.should_walk_down = bool(d.get('ShouldWalkDown'))
        self.item_use_height = d.get('ItemUseHeight', 0.01)
        self.delta_use_height = d.get('DeltaUseHeight') or 0.0
        # Woody's own widening of the climb-arrival window (Pawn.cs:1702;
        # 77 items carry it), and the ExtraDeltaHeight variant (Woody.cs:750)
        self.woody_delta_use_height = d.get('WoodyDeltaUseHeight') or 0.0
        self.use_woody_extra = bool(d.get('UseWoodyExtraDeltaHeight'))
        # Pawn.CanPassTarget (Pawn.cs:1032-1035) gates the end-of-step snap
        self.passable = d.get('Passable', True)
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
        # the Mother's own bubble icon (RoutineAction.BubbleMotherIcon,
        # RoutineAction.cs:59-70; one carrier — L210's CallRTMother shows
        # the neighbour's face in her thoughts)
        self.special_bubble_for_mother = bool(d.get('SpecialBubbleForMother'))
        self.bubble_mother_icon = d.get('BubbleMotherIconPath') or None
        # RoutineActionUse.StopAction removes routine actions once the
        # tricked use lands (RoutineActionUse.cs:415-427)
        self.destroy_after_use_tricked = bool(d.get('DestroyAfterUseTricked'))
        self.remove_from_routine_after_use_tricked = \
            bool(d.get('RemoveFromRoutineAfterUseTricked'))
        self.remove_after_first_use = bool(d.get('RemoveFromRoutineAfterFirstUse'))
        # Item.MainValveOpen: L113's ValveMain serializes it TRUE — the water
        # runs at load, the neighbour's first prime closes it (Item.cs:1352)
        # and only then does Woody's click arm the trick (Item.cs:1714-1726)
        self.main_valve_open = bool(d.get('MainValveOpen'))
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
        # Item.InventoryToAdd (Item.cs:562): the SearchItem that
        # AddInventoryToObject refills (Item.cs:1791-1810) — L208's Mouse
        # points at itself, so the emptied Mouse gets a fresh rat at each
        # priming round (cs:1559, 1582)
        self.inventory_to_add = (d.get('InventoryToAdd') or {}).get('path')
        self.change_iron_routine = False       # set by TrickItem.Fix
        self.change_iron_routine_last_path = False
        self.item_removed = False              # Item.ItemRemoved (PigKeys)
        # SearchItem.AcquiredInventoryCount: the last take's hand-over size,
        # picking the 1 s re-close (SearchItem.cs:141-154, 191, 210)
        self.acquired_inventory_count = 0
        # Item.ElephantBehaviorAux, the one-shot latch of Pawn.ElephantAnimations
        # (Pawn.cs:1539-1555; re-armed at Item.cs:1581)
        self.elephant_behavior_aux = False
        # TrickItem.OnlyOnceWaterPuddle: the L210 Valve's one-shot hand-over
        # to its puddle (TrickItem.cs:1240-1251)
        self.only_once_water_puddle = False
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
             'desc': v.get('DescriptionString') or '',
             # PlayWontGoAnimation speaks this at Woody (Woody.cs:878-882)
             'wrong_zone': v.get('WrongZoneTooltip') or '',
             # the big bubble for long descriptions (HUD.cs:995-1008)
             'long': bool(v.get('LongDescription'))}
            for v in (d.get('InventoryItems') or [])]
        self.dont_remove_inventory = bool(d.get('DontRemoveInventoryItem'))
        # SearchItem.AssignFirstInventoryOnly (SearchItem.cs:37, 173-176): only
        # the first hand-over entry carries its source item (L112's SportsBag,
        # L114's DeskDrawer) — the door click reads that stamp (Pawn.cs:633)
        self.assign_first_inventory_only = bool(d.get('AssignFirstInventoryOnly'))
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
        # the NFH2 anger ladder (Rottweiler.cs:613-693)
        self.anger_amount = d.get('AngerAmount', 20) or 0
        self.extra_coin_anger = d.get('ExtraCoinAngerAmount') or 0.0
        self.extra_coin_toilet_211 = False  # Item.Toilet211Behavior's latch
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
        # the hover tooltip strings (MouseCursor.UpdateMouseOver,
        # Item.GetNameString / GetWithString)
        self.name_tricked_string = d.get('NameTrickedString') or ''
        self.name_primed_string = d.get('NamePrimedString') or ''
        self.with_string = d.get('WithString') or ''
        self.with_tricked_string = d.get('WithTrickedString') or ''
        self.with_primed_string = d.get('WithPrimedString') or ''
        self.hide_string_key = d.get('HideString') or ''
        # the description bubble (Item.ShowItemTooltip, Item.cs:1844-1853;
        # GetDescriptionString picks the state variant, Item.cs:2329-2344)
        self.description_string = d.get('DescriptionString') or ''
        self.description_tricked = d.get('DescriptionTrickedString') or ''
        self.description_primed = d.get('DescriptionPrimedString') or ''
        self.description_linked = d.get('DescriptionLinkedTrickString') or ''
        self.description_fixed = d.get('DescriptionFixedString') or ''
        self.name_fixed_string = d.get('NameFixedString') or ''
        self.with_fixed_string = d.get('WithFixedString') or ''
        self.use_fixed_strings = bool(d.get('UseFixedStrings'))
        self.name_fuckedup_string = d.get('NameFuckedupString') or ''
        self.with_fuckedup_string = d.get('WithFuckedupString') or ''
        self.description_fuckedup = d.get('DescriptionFuckedupString') or ''
        # the compound-state names (TrickItem.Get*String, TrickItem.cs:1164-1225)
        self.name_compound = d.get('NameCompoundString') or ''
        self.with_compound = d.get('WithCompoundString') or ''
        self.description_compound = d.get('DescriptionCompoundString') or ''
        self.name_compound_tricked = d.get('NameCompoundTrickedString') or ''
        self.with_compound_tricked = d.get('WithCompoundTrickedString') or ''
        self.description_compound_tricked = \
            d.get('DescriptionCompoundTrickedString') or ''
        self.check_depends_on_tricked = bool(d.get('CheckDependsOnTricked'))
        self.empty_drawing_string = d.get('EmptyDrawingString') or ''
        ddl = d.get('DeltaDescriptionLocation') or {}
        self.delta_desc = (ddl.get('x', 0.0), ddl.get('y', 0.0))
        self.long_description = bool(d.get('LongDescription'))
        self.not_primed_tooltip = d.get('NotPrimedTooltip') or ''
        self.multiple_items_string = d.get('MultipleItemsString') or ''
        self.item_in_use_string = d.get('ItemInUseString') or ''
        self.take_multiple = bool(d.get('TakeItemMultipleTimes'))
        self.do_nothing_while_used = bool(d.get('DoNothingWhileBeeingUsed'))
        # the pick animation locks the input outright (Woody.cs:534-538)
        self.block_when_item_pick = bool(d.get('BlockWhenItemPick'))
        # the furniture visibly opens for the search (SearchItem.PreUse,
        # SearchItem.cs:125-152; closed again 1.5s/1s later, cs:250-268)
        self.open_object = ref('OpenObject')
        self.open_render_object = ref('OpenRenderObject')
        self.leave_toolbox_open = bool(d.get('LeaveToolBoxOpen'))
        self.close_time = 0.0
        # InventoryTooltips: per-held-type refusal bubbles
        # (Item.ShowWrongInventoryTooltip, Item.cs:1832-1842)
        self.inventory_tooltips = [
            {'type': (v.get('Type') or ''),
             'desc': (v.get('DescriptionString') or '')}
            for v in (d.get('InventoryTooltips') or [])]
        self.ignore_required_for_desc = \
            bool(d.get('IgnoreRequiredInventoryForDescription'))
        self.dont_change_tooltip_when_tricked = \
            bool(d.get('DontChangeTextTooltipWhenTricked'))
        self.item_that_changes_tooltip = ref('ItemThatChangesTooltip')
        self.is_floor = bool(d.get('IsFloor'))
        self.searching_item = bool(d.get('SearchingItem'))
        # the hover cursor (MouseCursor.UpdateCursor; Item.MouseOverIconName
        # loads from Textures/GUI/cursor/ and UpdateMouseOver swaps in the
        # after-trick icon)
        n = d.get('MouseOverIconName') or ''
        self.mouse_over_icon = ('Textures/GUI/cursor/' + n) if n else None
        self.mouse_over_after_trick = d.get('MouseOverAfterTrickIconName') or ''
        self.change_mouse_over_after_trick = \
            bool(d.get('ChangeMouseOverAfterTrick'))
        # SetPrimed swaps the cursor icon in while primed (Item.cs:1215-1218);
        # two items carry it (L108's poison shelf, L111's paint can)
        self.primed_mouse_over = d.get('PrimedMouseOverIconName') or ''
        # SetPrimed's material swap on the item's own quad (Item.cs:1236-1239;
        # one carrier — L108's first-aid kit opens to 'firstaid_open')
        pm = d.get('PrimedMaterial')
        self.primed_material = pm.get('texture') if isinstance(pm, dict) \
            else None
        # the collider/mesh prime toggles (WoodyPrime Item.cs:1253-1261,
        # RottweilerPrime cs:1326-1329): the tatter and L104's shelf pair
        self.disable_collider_when_primed = \
            bool(d.get('DisableColliderWhenPrimed'))
        self.enable_collider_after_prime = \
            bool(d.get('EnableColliderAfterPrime'))
        self.disable_mesh = bool(d.get('DisableMesh'))
        # the idle sequences (TrickItem.PlayIdleTrickedAnim cs:723-731,
        # ReturnToIdleAnimation cs:698-721) and the start-idle skip (cs:214)
        self.play_idle_normal_seq = bool(d.get('PlayIdleNormalSequence'))
        self.idle_normal_sequence = d.get('IdleNormalSequence') or []
        self.play_idle_tricked_seq = bool(d.get('PlayIdleTrickedSequence'))
        self.idle_tricked_sequence = d.get('IdleTrickedSequence') or []
        self.dont_play_idle_on_start = bool(d.get('DontPlayIdleOnStart'))
        self.ignore_depends_when_fixed = \
            bool(d.get('IgnoreDependsOnWhenFixed'))
        # TrickItem.Fix's valve block (cs:421-425)
        self.block_valve_after_fix = bool(d.get('BlockValveAfterFix'))
        # PlayItemAnimation echoes onto the Dependant (cs:1046-1049)
        self.animate_dependant = bool(d.get('AnimateDependant'))
        # the Flowers knife-pick hack (Item.cs:1421-1426)
        self.pick_up_without_go = bool(d.get('PickUpObjectWithoutGameObject'))
        # the interaction-icon tip drawn while the HUD info button is held
        # (Item.OnGUI, Item.cs:2740-2760; the exporter resolves the PPtr)
        tip = d.get('ItemTipIcon')
        self.tip_icon = tip.get('texture') if isinstance(tip, dict) else None
        self.tip_icon_depth = GUI_DEPTH.get(d.get('ItemTipIconDepth'), 24)
        td = d.get('ItemTipDeltaPosition') or {}
        self.tip_delta = (td.get('x', 0.0), td.get('y', 0.0))
        self.tip_dimensions = d.get('TipIconDimentions', 0.7)  # Item.cs:236
        self.always_show_tip = bool(d.get('AlwaysShowTipIcon'))
        # Item.GoNextAction: serialized true on L113's two valves — the
        # urgent resume advances instead of redoing (ActionManager.cs:620-626)
        self.go_next_action = bool(d.get('GoNextAction'))
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
        # the Coal name-hack (GetRottweilerUseAnimation, Item.cs:988-1002):
        # the walk-in element switches with the linked furnace's state
        if role == 'Rottweiler' and self.name == 'Coal' \
                and items is not None and self.linked_item_trick is not None:
            linked = items.get(self.linked_item_trick)
            seq = self.use_anim.get(role) or []
            if linked is not None and seq:
                seq[0] = 'CoalFuelWalk' if linked.tricked else 'CoalWalk'
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
                 'mother_enter', 'mother_leave', 'olga_enter', 'olga_leave',
                 'exit_anim', 'idle', 'sprite', 'passing', 'should_walk_up',
                 'use_distance', 'item_use_height', 'delta_use_height',
                 'dx', 'dy', 'rott_exit', 'alternate_idle', 'use_alternate_idle',
                 'complex_move', 'nfh2_stairs', 'pawn_deltas', 'passing_nfh2',
                 'is_transition', 'collider', 'mouse_over_icon', 'locked_name',
                 'delta_exit', 'delta_mother_exit', 'passable', 'ignore_idle',
                 'disabled', 'description_string', 'walk_deltas',
                 'exit_door', 'woody_delta_use_height', 'use_woody_extra',
                 'can_use', 'dont_use_on', 'with_string')

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
        # the Mother's and Olga's own pairs (Door.cs:18-24; Mother.cs:63-73,
        # Olga.cs:94-104 play them) — 98 doors carry MotherDoorBack*, Olga's
        # ship NONE everywhere
        self.mother_enter = _anim_name(d.get('MotherEnterAnimation'))
        self.mother_leave = _anim_name(d.get('MotherLeaveAnimation'))
        self.olga_enter = _anim_name(d.get('OlgaEnterAnimation'))
        self.olga_leave = _anim_name(d.get('OlgaLeaveAnimation'))
        self.exit_anim = _anim_name(d.get('ExitAnimation'))
        self.idle = _anim_name(d.get('IdleAnimation'))
        self.sprite = None
        self.passing = None                 # Door.PassingPawn
        self.should_walk_up = bool(d.get('ShouldWalkUp'))
        # Door : Item — the same arrival radii as Item, as serialized
        # (Item.cs:246 UseDistance = 0.03f, cs:220 ItemUseHeight = 0.01f;
        # Pawn.cs:1112-1119 reads them raw on the door step)
        self.use_distance = d.get('UseDistance', 0.03)
        self.item_use_height = d.get('ItemUseHeight', 0.01)
        self.delta_use_height = d.get('DeltaUseHeight') or 0.0
        # the climb-arrival widenings IsAtUseLocation reads on a door step
        # too (Pawn.cs:1330, 1412 -> cs:1690-1705, Woody.cs:744-755): six
        # walk-up DoorBacks (L212-L214) serialize WoodyDeltaUseHeight 0.2-0.4
        self.woody_delta_use_height = d.get('WoodyDeltaUseHeight') or 0.0
        self.use_woody_extra = bool(d.get('UseWoodyExtraDeltaHeight'))
        # Item.CanUse (Item.cs:314, = true) gates the hover cursor on a door
        # as well (MouseCursor.cs:374); Item.DontUseOn (IsAtUseRange's y-arm
        # skip, Item.cs:2270-2293) — every door serializes both defaults
        self.can_use = d.get('CanUse') if d.get('CanUse') is not None else True
        self.dont_use_on = (d.get('DontUseOn') or {}).get('path')
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
        self.collider = None                # BoxCollider (x, y, w, h)
        n = d.get('MouseOverIconName') or ''
        self.mouse_over_icon = ('Textures/GUI/cursor/' + n) if n else None
        self.locked_name = d.get('NameString') or ''
        # Item.GetWithString on a Door (Item.cs:2316-2327): the held-inventory
        # hover line's tail (MouseCursor.cs:193)
        self.with_string = d.get('WithString') or ''
        # Door.CanWoodyUse's locked bubble reads the description
        # (Door.cs:230-240)
        self.description_string = d.get('DescriptionString') or ''
        # CheckMoveLocationY adds the transition's own per-pawn delta on a
        # ComplexMove step (Woody.cs:939-950, Mother.cs:28-39, Olga.cs:124-135)
        self.walk_deltas = {}
        for role, key in (('Woody', 'DeltaWoodyLocation'),
                          ('Mother', 'DeltaMotherLocation'),
                          ('Olga', 'DeltaOlgaLocation')):
            v = d.get(key) or {}
            self.walk_deltas[role] = (v.get('x', 0.0), v.get('y', 0.0))
        # Woody / the Mother land at their own exit offsets, overriding the
        # base DoorDistanceDelta warp (Woody.cs:476, Mother.cs:60)
        v = d.get('DeltaExitLocation') or {}
        self.delta_exit = (v.get('x', 0.0), v.get('y', 0.0))
        v = d.get('DeltaMotherExitLocation') or {}
        self.delta_mother_exit = (v.get('x', 0.0), v.get('y', 0.0))
        # Pawn.CanPassTarget (Pawn.cs:1032): an impassable door blocks the
        # end-of-step x-snap
        self.passable = d.get('Passable', True)
        # Door.Start skips the idle when asked (Door.cs:211)
        self.ignore_idle = bool(d.get('IgnoreIdleAnimation'))
        # a Woody pass through an ExitDoor ends the level
        # (Pawn.OnDoorEnterAnimationFinished, Pawn.cs:1662-1665)
        self.exit_door = bool(d.get('ExitDoor'))
        # Door.Start deactivates the object outright (Door.cs:63-66);
        # L214's captain-door pair only wakes through the unported
        # CaptainDoor214 hack
        self.disabled = bool(d.get('DisableOnStart'))


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
        # InventoryManager.InventoryItems (InventoryManager.cs:5), the
        # serialized starting inventory of Woody's InvManager (Woody.cs:8),
        # in the port's entry shape; FirstInventoryItem (cs:7) is the flag
        # HUD.OnGUI's first draw initializes the first entry on (HUD.cs:
        # 972-978). Level209 ships the pen knife; every other scene an
        # empty list.
        self.inventory_items = []
        self.first_inventory_item = False
        self.behaviors = []         # serialized *Behavior components
        self.progress_bars = []     # ProgressBar components
        self.dexterity = {}         # DexterityComponent pid -> spec
        self.mouse_cursor = None    # MouseCursor component spec
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

    # -- helpers: accessors over the export format (tools/export_level.py —
    #    objects by path id, GameObject/Transform/component tables); they
    #    stand in for Unity's GetComponent / transform lookups, no game rule
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
            # the percentage label's style (ProgressBar.cs:39, 79, 269):
            # its face resolves like the HUD styles', its size is
            # CalculateFontSize(0)+3 at draw time
            spec['data_style'] = e.get('DataStyle') or {}

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

    def _add_mouse_cursor(self, pid, o):
        """MouseCursor's serialized cursors (MouseCursor.cs:5-31); the
        resolved names live under Textures/GUI/cursor/"""
        d = o['data']
        go = self._go_of(o)
        spec = {'default': None, 'default_hud': None, 'use_inv': None,
                'cancel_inv': None, 'walking': None,
                'size': d.get('cursorSize') or {},
                'min_mouse_y': d.get('MinMouseY') or 100}
        resolved = {}
        for e in (self._hud_raw.get('MouseCursor') or []):
            if (e.get('m_GameObject') or {}).get('path') == go:
                resolved = e
        for k_src, k_dst in (('Default', 'default'),
                             ('DefaultHUDIcon', 'default_hud'),
                             ('UseInventoryIcon', 'use_inv'),
                             ('CancelInventoryIcon', 'cancel_inv'),
                             ('WalkingTexture', 'walking')):
            v = resolved.get(k_src)
            if isinstance(v, dict) and v.get('texture'):
                spec[k_dst] = 'Textures/GUI/cursor/' + v['texture']
        self.mouse_cursor = spec

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
            elif t == 'MouseCursor' and 'data' in o:
                self._add_mouse_cursor(int(pid), o)
        self.sprites.sort(key=lambda s: -s.depth)      # far (high) first
        self._find_background()
        self._build_graph()
        self._find_pawns()
        self._find_inventory()
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
            # CameraMover.cs:21-27 initializers; every scene serializes them
            self.camera_bounds = (cm.get('MinX', -7.0), cm.get('MaxX', 7.0),
                                  cm.get('MinY', -3.5), cm.get('MaxY', 3.5))
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
            # Level.cs:38-40 initializers "Zone05" / "Zone01"
            self.entrance_location, _ = _point(
                lvl.get('EntranceZoneName', 'Zone01'), 'EntranceLocationOffset')
            self.start_location, self.start_zone = _point(
                lvl.get('StartZoneName', 'Zone05'), 'StartLocationOffset')
        # MusicPlayer (MusicPlayer.cs): the level track and the outcome
        # jingles; the exporter resolves the AudioClip PPtrs into the
        # extraction's WAV/OGG names
        self.music = None
        mp = next((o['data'] for o in self.objs.values()
                   if o['type'] == 'MusicPlayer' and 'data' in o), None)
        ia = next((o['data'] for o in self.objs.values()
                   if o['type'] == 'IntroAnimation' and 'data' in o), None)
        if mp:
            def clip(v):
                return v.get('clip') if isinstance(v, dict) else None
            tracks = mp.get('AlternateLevelSounds') \
                if mp.get('UseAlternateSounds') else mp.get('LevelSounds')
            tracks = tracks or []
            # the serialized LevelMusicSource carries the loop flag (true in
            # every scene); the jingle sources ship loop=false
            lm = (mp.get('LevelMusicSource') or {}).get('path')
            lmd = (self._o(lm) or {}).get('data') or {}
            self.music = {
                # GetLevelMusic returns index 1, the 'normal' track
                'level': clip(tracks[1]) if len(tracks) > 1 else None,
                'loop': bool(lmd.get('loop', True)),
                'clap': clip(mp.get('EntranceClap')),
                'success': clip(mp.get('SuccessNormal')),
                'success_perfect': clip(mp.get('SuccessPerfect')),
                'caught': clip(mp.get('Caught')),
                'failed': clip(mp.get('Failed')),
                # PlayLevelMusic: the first run waits 15 s (OneTime false)
                'delay': 0.0 if mp.get('OneTime') else 15.0,
                # PlayEntranceMusic (MusicPlayer.cs:122-130): the EntranceSound
                # on its own source at IntroAnimation.StartGame (cs:311)
                'entrance': clip(mp.get('EntranceSound')),
                # the title cards run between the scene load (the clap and
                # the 15 s Invoke start there, MusicPlayer.Start / Level.Start
                # -> LoadSettings, Level.cs:217-244, 295-297) and StartGame,
                # the port's t=0: IntroAnimation.StartAnimation's seven
                # WaitForSeconds stages (IntroAnimation.cs:86-112) — 7.79 s on
                # Level101; the reference measures 7.08 s from StartGame to
                # the track (0.14 s of coroutine frame latencies over the
                # seven waits, docs/audit/verified/pass5_video.md F1)
                'intro_total': sum(
                    float(ia.get(k) or 0.0) for k in (
                        'CompanyStaticTime', 'CompanyOutGameInTime',
                        'GameTime', 'GameEpisodeInTime', 'GameEpisodeTime',
                        'GameEpisodeOutTime', 'GameOutTime'))
                    if ia else 0.0,
            }
        # the serialized game camera: orthographic, size 3 in all 31 scenes
        # (the perspective size-100 ones are the menu scenes)
        self.camera_size = None
        for o in self.objs.values():
            if o['type'] == 'Camera' and (o.get('data') or {}).get('orthographic'):
                self.camera_size = o['data']['orthographic_size']
                break
        # Level.OnGUI's fences (Level.cs:322-341): screen-space textures at
        # the world FencePositions, drawn between the pawns and the HUD
        # (GUIDepth.LevelFence). LoadFenceSize (cs:244-252) overrides each
        # rect's width to (H/W)*1.75/0.75 screen fractions unless
        # IgnoreFenceSize; AdjustRectangle scales fractions into pixels.
        self.fences = []
        if lvl and not lvl.get('DisableFences'):
            depth = GUI_DEPTH.get(lvl.get('FenceDepth'),
                                  GUI_DEPTH['LevelFence'])
            for tex, pos, rect in zip(lvl.get('FenceTextures') or [],
                                      lvl.get('FencePositions') or [],
                                      lvl.get('FenceRects') or []):
                name = tex.get('texture') if isinstance(tex, dict) else None
                if not name:
                    continue
                self.fences.append({
                    'texture': name,
                    'x': pos.get('x', 0.0), 'y': pos.get('y', 0.0),
                    'w': rect.get('width', 0.0), 'h': rect.get('height', 0.0),
                    'depth': depth,
                    'ignore_size': bool(lvl.get('IgnoreFenceSize'))})
        # a MoveOnly action stores the zone's GameObject; alias the zone
        # components' bubble icons onto it
        for pid in list(self.bubble_icons):
            o = self._o(pid)
            go = self._go_of(o) if o else None
            if go is not None:
                self.bubble_icons.setdefault(go, self.bubble_icons[pid])
        # Item.Start ends in SetPrimed(Primed) (Item.cs:697): the primed branch
        # adds DeltaPrimedLocation to DeltaLocation, the unprimed one subtracts
        # it (Item.cs:1201-1210). The WaterPuddle name-hack negates its
        # DeltaLocation and FinalDeltaLocationNormal outright and skips both
        # delta arms (Item.cs:1196-1210) — at load too: L201's serialized
        # +0.6 x-delta is -0.6 from the first frame.
        for it in self.items.values():
            if it.name == 'WaterPuddle':
                it.dx = -it.dx
                it.dy = -it.dy
                it.final_normal = (-it.final_normal[0], -it.final_normal[1])
            elif it.delta_primed_x or it.delta_primed_y:
                sign = 1.0 if it.primed else -1.0
                it.dx += sign * it.delta_primed_x
                it.dy += sign * it.delta_primed_y

    def _add_zone(self, pid, o):
        """loader: one serialized Zone component (Zone.cs fields, keyed by
        their C# names) plus its GameObject's transform and BoxCollider"""
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
        z.name_string = o['data'].get('NameString') or ''
        z.end_string = o['data'].get('EndString') or ''
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
        """loader: one serialized Door/Transition component (Door.cs and
        Transition.cs fields, keyed by their C# names)"""
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
        box = self._component(go, 'BoxCollider')
        if box is not None:
            door.collider = self._world_box(go, box['data']['center'],
                                            box['data']['size'], p[0], p[1])
        self.doors.append(door)

    def _add_item(self, pid, o):
        """loader: one serialized Item-family component (Item.cs and the
        subclass fields, keyed by their C# names) into an Item"""
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
                it.collider = self._world_box(go, b['center'], b['size'],
                                              it.x, it.y)
                # Collider.enabled ships off on 221 items (every SlipperyGround
                # strip, L104's ApplePie until its round trip, L105's Football
                # until alerted, L114's Pipe until primed, the S2 fences...) —
                # Physics.Raycast never hits them; the enable sites are the
                # ported ones (Item.cs:1326-1333, TrickItem.cs:599-606, 1154-1157,
                # 2455-2476, the behaviors' collider toggles)
                it.clickable = bool(b.get('enabled', True))
        for d in self.doors:
            d.sprite = find(self._go_of(self._o(d.pid)))

    def _world_box(self, go, center, size, fx, fy):
        """a BoxCollider's world-space XY footprint: Physics.Raycast tests
        the collider under the full transform, so the serialized local size
        goes through the world scale and rotation — the binoculars' box is
        (10, 4, 14.37) local but (0.23 x 4) world (scale 0.023), and most
        items rotate X by 90 so their screen height is the local z."""
        tp = self._transform_of.get(go)
        td = (self._o(tp).get('data') if tp else None) or {}
        wp = td.get('world_position') or [fx, fy, 0.0]
        ws = td.get('world_scale') or [1.0, 1.0, 1.0]
        qx, qy, qz, qw = td.get('world_rotation') or [0.0, 0.0, 0.0, 1.0]

        def rot(v):
            # v + 2*cross(q.xyz, cross(q.xyz, v) + w*v)
            cx1 = qy * v[2] - qz * v[1] + qw * v[0]
            cy1 = qz * v[0] - qx * v[2] + qw * v[1]
            cz1 = qx * v[1] - qy * v[0] + qw * v[2]
            return (v[0] + 2.0 * (qy * cz1 - qz * cy1),
                    v[1] + 2.0 * (qz * cx1 - qx * cz1),
                    v[2] + 2.0 * (qx * cy1 - qy * cx1))
        c = rot((center[0] * ws[0], center[1] * ws[1], center[2] * ws[2]))
        # a box is its half-extents in every direction: a negative serialized
        # size (L106's Pudding height, L210's ElephantCricketBat width) or a
        # negative world scale still yields the same solid for the physics
        # test, so the sign drops here — kept, it made the hit-test empty
        half = [abs(size[j] * ws[j]) * 0.5 for j in range(3)]
        w = h = dz = 0.0
        for j, axis in enumerate(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                                  (0.0, 0.0, 1.0))):
            a = rot(axis)
            w += abs(a[0]) * half[j]
            h += abs(a[1]) * half[j]
            dz += abs(a[2]) * half[j]
        # the z centre and half-depth ride along for the raycast ordering:
        # the click ray starts on the camera plane (ScreenToWorldPoint of the
        # mouse, Woody.cs:708) and runs +z, so Physics.Raycast returns the
        # collider whose NEAR face (z - dz) comes first — the X-90 rotation
        # turns an item's local height into a depth of several units, so
        # the centre alone orders 113 of the 667 XY-overlapping item/door
        # collider pairs wrongly (tests/checks/assets_refs.py holds two)
        return (wp[0] + c[0], wp[1] + c[1], 2.0 * w, 2.0 * h,
                (wp[2] if len(wp) > 2 else 0.0) + c[2], dz)

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
        """loader: the scene's GameInfo component (GameInfo.cs fields, keyed
        by their C# names)"""
        for o in self.objs.values():
            if o['type'] == 'GameInfo' and 'data' in o:
                d = o['data']
                self.game_info = {
                    'total': d.get('TotalTricksCount') or 0,
                    'winning': d.get('WinningTricksCount') or 0,
                    # the HUD clock and the score screen
                    'time_minutes': d.get('TimeMinutes') or 0.0,
                    # GameInfo.cs:43 initializer 4 (2/3/4/5 serialized)
                    'compound_trick_score': d.get('CompoundTrickScore', 4),
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
                             # RoutineAction.cs:25 (= 0.03f), taken raw: 81
                             # actions serialize 0.0 (RoutineActionMove.cs:39
                             # compares against it as-is)
                             'max_distance': a.get('MaximumPawnDistanceToAction', 0.03),
                             'hide_object': bool(a.get('HideObjectDuringUse')),
                             'hide_owner': bool(a.get('HideOwnerDuringUse')),
                             'move_only': bool(a.get('MoveOnly')),
                             'move_x': ml.get('x', 0.0),
                             'move_zone': self._go_of(self._o(mz)) if mz and self._o(mz) else None,
                             'mutex': bool(a.get('MutexAction')),
                             'postpone_alarm': pa,
                             # the second postpone flag of the Use arm of
                             # Rottweiler.IsAlarmPostponed (Rottweiler.cs:1067;
                             # Level105's four actions carry it)
                             'postpone_alarm_during_use_only':
                                 bool(a.get('PostponeAlarmDuringUseOnly')),
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
                                  # AdvanceActionIndex's wrap (ActionManager.
                                  # cs:566-584): start index, else the
                                  # selected index only with this flag, else 0
                                  'loop_from_selected':
                                      bool(d.get('LoopFromSelectedIndex')),
                                  'selected_index': d.get('ActionSelectedIndex') or 0,
                                  'frozen': bool(d.get('Frozen'))})

    def _build_graph(self):
        """ZoneController.Start() (ZoneController.cs:16-27): a door links its
        own zone to the zone of whatever it points at, `(!Locked ||
        TemporalLock) && LinkTo != null`. Two departures, both documented:
        the `|| TemporalLock` arm is not modelled — 22 doors carry it, 20 of
        them Locked, all in s1/Intro101-103 (unported cutscenes); there the
        original keeps the edge but LinkNodes then refuses the Locked door
        (GetDoorBetweenZones wants !Locked, Helpers.cs:194-205, 245-248)
        and returns a null path, while the port drops the edge — the same
        None for every ordered zone pair of the three intros (they hold no
        route made of unlocked doors except Intro103 Zone02<->Zone03, which
        both graphs carry), so the missing arm has no observable effect and
        the 28 playable levels ship no TemporalLock door at all. A
        DisableOnStart door (Door.cs:63-66; only L214's captain DoorBack
        pair, Zone03<->Zone05) KEEPS its edge: the pair ships active, so
        ZoneController.Start sees it unless Door.Start deactivated it first
        — and the level needs the edge (Item.CaptainDoorBehavior, Item.cs:
        2606-2623, re-activates both doors and retargets the neighbour's
        CaptainDoor action at CaptainControls in Zone05: with no edge that
        action and the cabin's two tricks are dead). Zone.Neighbors never
        changes afterwards; while the pair is inactive LinkNodes finds no
        door between the zones (GetDoorBetweenZones, Helpers.cs:194-205,
        245-248) and the path is null — find_path refuses a route through
        a disabled door the same way."""
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
        Uniform edge cost, so BFS — Helpers.GetShortestPath adds 1.0 per hop
        (Helpers.cs:158-192). The LENGTH always agrees; the CHOICE among
        equal-length routes is a documented open question: 720 of the 786
        reachable ordered zone pairs (every Season-1 pair) have a unique
        shortest route, the other 66 (4-6 per Season-2 level, the opposite
        corners of the 4-cycles) have two, and there the original's pick
        depends on ZoneController.Zones order (FindGameObjectsWithTag) and
        Mono's unstable List.Sort at equal Cost — not recoverable from the
        decompile. This BFS takes the first door in scene order (a faithful
        Dijkstra under four plausible tie-breaks — stable/reversed sort x
        scene/reversed zone order — agrees with it on 19 to 47 of those 66
        pairs, never on all; tests/checks/assets_refs.py re-derives the
        length equality over every pair). A route through a door whose
        object is inactive (Door.disabled: L214's captain pair before the
        CaptainDoor trick) is refused: GetShortestPath walks Zone.Neighbors
        blind to door state, then BuildPath -> LinkNodes finds no active
        door between the two zones (GetComponentsInChildren skips inactive
        objects; Helpers.cs:194-205, 243-248) and the path is null."""
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
                    if any(dr.disabled for _, dr in out):
                        return None      # LinkNodes: no door -> null path
                    return out
                q.append(nb)
        return None

    def zone_at(self, x, y):
        """the zone under a click: the port's stand-in for the raycast's
        GetZoneFromCollider (Pawn.MoveToLocation cs:403-404,
        GetMoveDestination cs:698-701) — containment in the zone's box.
        Where zone boxes overlap (10 pairs: L208/L209 Zone05 over Zone03/04
        by 1.7-1.9 units, L210 Zone03/04 by 0.53, L213 by <0.1, the intros)
        the first in scene order wins; every zone box spans the same z, so
        the raycast's own tie-break there is unspecified too."""
        for z in self.zones:
            if abs(x - z.x) <= z.w * 0.5 and abs(y - z.y) <= z.h * 0.5:
                return z
        return None

    def zone_by_pid(self, pid):
        """lookup: a serialized Zone reference (path id) -> the Zone"""
        for z in self.zones:
            if z.pid == pid:
                return z
        return None

    def door_by_pid(self, pid):
        """lookup: a serialized Door reference (path id) -> the Door"""
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
        # an animation with an unloadable sheet stays in the controller's
        # array (LoadTexture only logs, AnimationInstance.cs:137-140): L213's
        # BoatPicnic use strips and S1's mother-door strips name Resources
        # paths that do not exist; keep them, sheet None draws nothing
        anims = [a for a in anims if a.sheet_path]
        if not anims:
            return
        depth = GUI_DEPTH.get(d.get('AnimationGUIDepth'), 32)
        dl = d.get('DeltaLocation') or {}
        # the pose at load. A controller is born with CurrentAnimation ==
        # null (AnimationControllerBase.cs:13) and OnGUI draws / refreshes
        # nothing until the first SetAnimation (cs:172-189, 350-371) —
        # Sprite.current None stands for that, distinct from Sprite.hidden
        # (= AnimationControllerBase.Hidden, cs:55). Two Starts pick a
        # resting pose the loader can name: a pawn's PlayDefaultAnimation
        # (Pawn.cs:224-238: PlayLoopingAnimation(DefaultAnimation)) and a
        # door's ReturnToIdleAnimation (Door.cs:56-63, 209-223:
        # PlayLoopingAnimation(IdleAnimation) unless IgnoreIdleAnimation
        # skips it, cs:211 — the 8 S2 DoorBacks keep only the pass strips
        # Door.PlayAnimation plays, cs:141-153; the sprite still exists).
        # Every other ItemAnimationController stays at None here: the Item
        # family's Start plays — SetPrimed's primed pose, TrickItem's
        # ReturnToIdleAnimation, SearchItem's FullAnimation, HideItem's
        # IdleAnim, Alerter's SleepSequence — run in World.__init__
        # (world.py _start_item_animations) through the runtime's own
        # PlayItemAnimation dispatch, and a controller nothing plays
        # (IdleNormal NONE, Animating false, DontPlayIdleOnStart) keeps
        # drawing nothing, exactly as the original's does.
        want = None
        is_pawn = o['type'] == 'PawnAnimationController'
        if is_pawn:
            for pawn_type in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
                pawn = self._component(go, pawn_type)
                if pawn and 'data' in pawn:
                    want = pawn['data'].get('DefaultAnimation')
                    break
        else:
            for owner_type in ('Door', 'Transition'):
                door = self._component(go, owner_type)
                if door and 'data' in door:
                    if not door['data'].get('IgnoreIdleAnimation'):
                        want = door['data'].get('IdleAnimation')
                    break
        cur = None
        for i, a in enumerate(anims):
            if a.name == want:
                cur = i; break
        if cur is None and is_pawn:
            # a pawn whose DefaultAnimation the sheet lacks: its first entry
            cur = 0
        p = self._pos(tr)
        sp = Sprite(self._o(go)['data']['name'], p[0], p[1],
                    depth, anims, cur,
                    dl.get('x', 0.0), dl.get('y', 0.0),
                    o['type'], go)
        self.sprites.append(sp)

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
                # horizontal walk covers Speed * ForceMagnitude per second;
                # the fallbacks are the Pawn constructor's (Pawn.cs:203-209),
                # every pawn serializes its own values
                'speed': pd.get('Speed', 1.25),
                'speed_sneaking': pd.get('SpeedSneaking', 0.65),
                'force': pd.get('ForceMagnitude', 300.0),
                'door_force': pd.get('DoorForceMagnitude', 80.0),
                'run_force': pd.get('RunningForceMagnitude', 300.0),
                'run_door_force': pd.get('RunningDoorForceMagnitude', 80.0),
                'door_delta': ((pd.get('DoorDistanceDelta') or {}).get('x', 0.0),
                               (pd.get('DoorDistanceDelta') or {}).get('y', -0.3)),
                'player_height_delta': pd.get('PlayerHeightDelta') or 0.0,
                'zone_level_threshold': pd.get('ZoneLevelThreshold') or 0.0,
                'item_use_height_threshold': pd.get('ItemUseHeightThreshold') or 0.0,
                # Woody.IsAtUseLocation's UseWoodyExtraDeltaHeight arm
                # (Woody.cs:750-753)
                'extra_delta_height': pd.get('ExtraDeltaHeight') or 0.0,
                'portal_up': _anim_name(pd.get('PortalUpAnimation')),
                'portal_down': _anim_name(pd.get('PortalDownAnimation')),
                # the neighbour's urgent-run climb set (Rottweiler.cs:406, 423)
                'portal_run_up': _anim_name(pd.get('PortalRunUpAnimation')),
                'portal_run_down': _anim_name(pd.get('PortalRunDownAnimation')),
                'angry_decay': pd.get('AngryMeterDecay') or 0.0,
                'notice_near_distance': pd.get('NoticeWhenNearTrickedDistance')
                    if pd.get('NoticeWhenNearTrickedDistance') is not None
                    else 0.03,
                'angry_max': pd.get('AngryMeterMaximum') or 100.0,
                'fear_left': _anim_name(pd.get('FearAnimationLeft')) or 'FearLeft',
                'fear_right': _anim_name(pd.get('FearAnimationRight')) or 'FearRight',
                # PlayAudienceLaugh's clip pools (Rottweiler.cs:805-818)
                'medium_laughs': [v.get('clip') for v in
                                  (pd.get('MediumLaughs') or [])
                                  if isinstance(v, dict) and v.get('clip')],
                'big_laughs': [v.get('clip') for v in
                               (pd.get('BigLaughs') or [])
                               if isinstance(v, dict) and v.get('clip')],
                'win_animation': _anim_name(pd.get('WinAnimation')),
                # PlayFinishAnimation's losing arm (Woody.cs:1120-1127)
                'lose_animation': _anim_name(pd.get('LoseAnimation')),
                # the end-of-entrance greeting (Pawn.cs:1064-1067)
                'hello_animation': _anim_name(pd.get('HelloAnimation')),
                # Pawn.HelloAnimationNFH2 (Pawn.cs:111, initializer
                # Entrance at cs:213): IntroAnimation.StartGame plays it on
                # the NFH2Path Woody with the input locked (IntroAnimation.
                # cs:300-304); its single end unlocks (Woody.cs:372-375)
                'hello_animation_nfh2': _anim_name(pd.get('HelloAnimationNFH2')),
                # Pawn.FinishedEntrance (Pawn.cs:119) is a serialized public
                # field: every Season-2 level (and the S1 intros) ships it
                # TRUE — Woody.Start leaves the input unlocked (Woody.cs:191),
                # Woody.Update never starts the entrance walk (cs:223-231),
                # TakeNextStep never plays HelloAnimation (Pawn.cs:1064-1067;
                # the S2 sheet has no Hello); the 14 S1 levels ship FALSE
                'finished_entrance': bool(pd.get('FinishedEntrance')),
                # Woody.ExitConfirmMessage: the localization key the exit
                # door's dialog shows (Woody.cs:552-556)
                'exit_confirm_message': pd.get('ExitConfirmMessage') or '',
                # the 30-second boredom poses (Woody.FindInput, cs:612-623)
                'idle_animations': [a for a in (pd.get('IdleAnimations') or [])
                                    if a and a != 'NONE'],
                'idle_threshold': pd.get('IdleThreshold') or 30.0,
                # the Kid's reaction sets (TrickItem.KidActions, cs:632-653)
                'kid_use_normal_seq': pd.get('UseNormalSequence') or [],
                'kid_use_tricked_seq': pd.get('UseTrickedSequence') or [],
                'kid_use_linked_seq': pd.get('UseLinkedTrickSequence') or [],
                'is_sleeping': bool(pd.get('IsSleeping')),
                'ignore_woody': bool(pd.get('IgnoreWoody')),
                'animal_tutorial': bool(pd.get('AnimalTutorial')),
                'nfh2': bool(pd.get('NFH2Path')),
                'adjacent_zones': bool(pd.get('AdjacentZonesEnabled')),
                'min_door_distance': pd.get('MinDistanceToNearestDoor') or 0.0,
                # Woody.Start localizes these keys (Woody.cs:197-205)
                'use_string': pd.get('UseString') or '',
                'with_string': pd.get('WithString') or '',
                'empty_use_string': pd.get('EmptyUseString') or '',
                'look_at_string': pd.get('LookAtString') or '',
                'open_string': pd.get('OpenString') or '',
                'examine_string': pd.get('ExamineString') or '',
                'hide_string': pd.get('HideString') or '',
                'end_string': pd.get('EndString') or '',
                # the fixing-tool chain, serialized inline on the Rottweiler
                # (RoutineActionGrab / RoutineActionUseFixingItem / Return)
                'grab_action': {
                    'sequence': (pd.get('GrabFixingItemAction') or {}).get(
                        'GrabSequence') or [],
                    'postpone_alarm': bool((pd.get('GrabFixingItemAction')
                                            or {}).get('PostponeAlarm')),
                    # RoutineAction.Urgent picks the run for the interposed
                    # move (RoutineActionMove.cs:68-75) — the fetch runs on
                    # L110/L113 only, walks on L111
                    'urgent': bool((pd.get('GrabFixingItemAction')
                                    or {}).get('Urgent')),
                    # ForceUseOriginalAction: an urgent interrupting this
                    # step resumes the step's own original instead of the
                    # step (ActionManager.cs:711-714; L110's UseFixingItem)
                    'force_use_original': bool((pd.get('GrabFixingItemAction')
                                                or {}).get('ForceUseOriginalAction')),
                },
                'use_fixing_action': {
                    'sequence': (pd.get('UseFixingItemAction') or {}).get(
                        'UseFixingItemSequence') or [],
                    'should_return': bool((pd.get('UseFixingItemAction')
                                           or {}).get('ShouldReturnFixingItem')),
                    'return_sequence': ((pd.get('UseFixingItemAction') or {}).get(
                        'ReturnFixingItemAction') or {}).get('ReturnSequence') or [],
                    'postpone_alarm': bool((pd.get('UseFixingItemAction')
                                            or {}).get('PostponeAlarm')),
                    'urgent': bool((pd.get('UseFixingItemAction')
                                    or {}).get('Urgent')),
                    'force_use_original': bool((pd.get('UseFixingItemAction')
                                                or {}).get('ForceUseOriginalAction')),
                    # the ReturnFixingItemAction never serializes Urgent
                    'return_urgent': bool((((pd.get('UseFixingItemAction')
                                             or {}).get('ReturnFixingItemAction')
                                            or {}).get('Urgent'))),
                },
                # Rottweiler.SurpriseActionFar (cs:26) and AlarmAction (cs:62):
                # the alerter/notice run and the phone answer, with the flags
                # RoutineActionMove.OnActionStarted (Urgent) and Rottweiler.
                # IsAlarmPostponed (cs:1053, 1065-1068) read off them
                'surprise_far_action': {
                    'urgent': bool((pd.get('SurpriseActionFar') or {}).get('Urgent')),
                    'postpone_alarm': bool((pd.get('SurpriseActionFar')
                                            or {}).get('PostponeAlarm')),
                },
                'alarm_action': {
                    'urgent': bool((pd.get('AlarmAction') or {}).get('Urgent')),
                    'postpone_alarm': bool((pd.get('AlarmAction')
                                            or {}).get('PostponeAlarm')),
                    'postpone_alarm_during_use_only': bool(
                        (pd.get('AlarmAction') or {}).get(
                            'PostponeAlarmDuringUseOnly')),
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
                # Woody.ItemBehavior (Woody.cs), the AngryElephant that
                # Pawn.ElephantAnimations watches on every zone change
                # (Pawn.cs:1536-1558; L208 only)
                'item_behavior': (pd.get('ItemBehavior') or {}).get('path'),
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
                    # Urgent (true in every scene) makes the interposed move
                    # a run; PostponeAlarm feeds IsAlarmPostponed's Use arm;
                    # ContinueToNextAfterFinished (Level102 only) makes the
                    # end a plain advance instead of StopUrgentAction
                    # (ActionManager.cs:530-538)
                    'urgent': bool((pd.get('ToiletAction') or {}).get('Urgent')),
                    'postpone_alarm': bool((pd.get('ToiletAction')
                                            or {}).get('PostponeAlarm')),
                    'postpone_alarm_during_use_only': bool(
                        (pd.get('ToiletAction') or {}).get(
                            'PostponeAlarmDuringUseOnly')),
                    'continue_to_next': bool((pd.get('ToiletAction') or {}).get(
                        'ContinueToNextAfterFinished')),
                },
                'wait_in_fear_anim': _anim_name(
                    (pd.get('WaitInFearAction') or {}).get('FearAnimation')),
                'hit_pawn_action': {
                    'sequence': (pd.get('HitPawnAction') or {}).get(
                        'HitPawnSequence') or [],
                    'max_distance': (pd.get('HitPawnAction') or {}).get(
                        'MaximumPawnDistanceToAction') or 0.03,
                    # Olga runs to the hit everywhere; the Mother walks except
                    # on Level210 (RoutineActionMove.cs:68-75 over the pawn)
                    'urgent': bool((pd.get('HitPawnAction') or {}).get('Urgent')),
                },
            }

    def _find_inventory(self):
        """loader: Woody.InvManager's serialized InventoryManager component
        (Woody.cs:8; InventoryManager.cs:5-7) — its InventoryItems list is
        Woody's starting inventory (Unity deserializes it before Start; the
        entries carry no source Item, that field is internal), in the same
        entry shape SearchItem.InventoryItems is read into (Inventory.cs:
        23-57)"""
        wd = next((o['data'] for o in self.objs.values()
                   if o['type'] == 'Woody' and 'data' in o), None)
        ref = ((wd or {}).get('InvManager') or {}).get('path')
        im = self._o(ref) if ref else None
        if im is None or im.get('type') != 'InventoryManager':
            im = next((o for o in self.objs.values()
                       if o['type'] == 'InventoryManager' and 'data' in o),
                      None)
        d = (im or {}).get('data') or {}
        self.inventory_items = [
            {'type': v.get('Type'), 'use_count': v.get('UseCount') or 0,
             'name': v.get('NameString') or '',
             'desc': v.get('DescriptionString') or '',
             'wrong_zone': v.get('WrongZoneTooltip') or '',
             'long': bool(v.get('LongDescription'))}
            for v in (d.get('InventoryItems') or [])]
        self.first_inventory_item = bool(d.get('FirstInventoryItem'))

    def _go_of_sprite(self, sprite):
        """lookup: the GameObject id a sprite was built from"""
        return getattr(sprite, 'go', None)

    def _find_background(self):
        """The backdrop is the quad carrying the Level component."""
        for q in self.quads:
            if q.get('is_level'):
                self.background = (q['texture'], q['x'], q['y'], q['w'], q['h'])
                return

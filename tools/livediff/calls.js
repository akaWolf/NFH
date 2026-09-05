'use strict';
// the neighbours' ActionManager, call by call: StartAction / MoveToAction /
// StartUrgentAction / StopUrgentAction / AdvanceToNextAction /
// AdvanceActionIndex / StartNextAction / StopCurrentAction with the owner,
// ActiveActionIndex, the action's class, its Item and its OriginalAction's
// Item — plus Item.Fix, Item.StopOlgaInfiniteLoop, Pawn.RunToHitPawn,
// Olga.OnItemAnimationSequenceEnded and the ROLE pawn's AnimState changes.
// Frames count GameInfo.Update like state.js. run it through
// run.py --extra=calls.js --role=<Pawn class>
const m = Process.getModuleByName('libmono.so');
const f = (n, r, a) => new NativeFunction(m.findExportByName(n), r, a);
const S = s => Memory.allocUtf8String(s);
const root = f('mono_get_root_domain', 'pointer', []);
const attach = f('mono_thread_attach', 'pointer', ['pointer']);
const imgLoaded = f('mono_image_loaded', 'pointer', ['pointer']);
const classFrom = f('mono_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']);
const methodFrom = f('mono_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);
const fieldFrom = f('mono_class_get_field_from_name', 'pointer', ['pointer', 'pointer']);
const fieldOff = f('mono_field_get_offset', 'int', ['pointer']);
const compile = f('mono_compile_method', 'pointer', ['pointer']);
const parentOf = f('mono_class_get_parent', 'pointer', ['pointer']);
const classOf = f('mono_object_get_class', 'pointer', ['pointer']);
const className = f('mono_class_get_name', 'pointer', ['pointer']);
const toUtf8 = f('mono_string_to_utf8', 'pointer', ['pointer']);
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const AM = classFrom(game, S(''), S('ActionManager'));
const RA = classFrom(game, S(''), S('RoutineAction'));
const Item = classFrom(game, S(''), S('Item'));
const Pawn = classFrom(game, S(''), S('Pawn'));
const Olga = classFrom(game, S(''), S('Olga'));
const PAC = classFrom(game, S(''), S('PawnAnimationController'));
const UObject = classFrom(unity, S('UnityEngine'), S('Object'));
const BOX = Process.pointerSize * 2;
function offOf(klass, name) {
    let k = klass;
    while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); }
    return -1;
}
function methodUp(klass, name, argc) {
    let k = klass;
    while (!k.isNull()) { const mm = methodFrom(k, S(name), argc); if (!mm.isNull()) return mm; k = parentOf(k); }
    return NULL;
}
const getName = methodUp(UObject, 'get_name', 0);
const getAnimState = methodUp(PAC, 'get_AnimState', 0);
const O = { idx: offOf(AM, 'ActiveActionIndex'), owner: offOf(AM, 'Owner'), active: offOf(AM, 'ActiveAction'),
            urgent: offOf(AM, 'UrgentAction'), item: offOf(RA, 'Item'), orig: offOf(RA, 'OriginalAction'),
            ctrl: offOf(Pawn, 'AnimController') };
const who = (typeof ROLE === 'undefined') ? 'Olga' : ROLE;
const pawnOff = offOf(GameInfo, who);
send({ actions: 'offsets', O: O, role: who, pawnOff: pawnOff });
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function cls(o) { return (o === undefined || o.isNull()) ? null : className(classOf(o)).readUtf8String(); }
function uname(o) {                      // UnityEngine.Object.name
    if (o === undefined || o.isNull()) return null;
    const ms = call0(getName, o);
    return ms.isNull() ? null : toUtf8(ms).readUtf8String();
}
const ptr = (o, off) => off >= 0 && !o.isNull() ? o.add(off).readPointer() : NULL;
function act(a) {                         // a RoutineAction's summary
    if (a === undefined || a.isNull()) return null;
    const orig = ptr(a, O.orig);
    return { cls: cls(a), item: uname(ptr(a, O.item)), orig: orig.isNull() ? null : uname(ptr(orig, O.item)) };
}
let frame = 0;
function row(am, name, extra) {
    const r = { f: frame, m: name, owner: cls(ptr(am, O.owner)), idx: O.idx >= 0 ? am.add(O.idx).readS32() : null,
                active: act(ptr(am, O.active)) };
    if (extra) Object.assign(r, extra);
    send(r);
}
function hook(klass, name, argc, fn) {
    const mm = methodUp(klass, name, argc);
    if (mm.isNull()) { send({ actions: 'missing', method: name, argc: argc }); return; }
    Interceptor.attach(compile(mm), fn);
}
hook(AM, 'StartAction', 1, { onEnter: function (a) { row(a[0], 'StartAction', { arg: act(a[1]) }); } });
hook(AM, 'MoveToAction', 1, { onEnter: function (a) { row(a[0], 'MoveToAction', { arg: act(a[1]) }); } });
hook(AM, 'StartUrgentAction', 2, { onEnter: function (a) { row(a[0], 'StartUrgentAction', { arg: act(a[1]), next: act(a[2]) }); } });
hook(AM, 'StopUrgentAction', 0, { onEnter: function (a) { row(a[0], 'StopUrgentAction', { urgent: act(ptr(a[0], O.urgent)) }); } });
hook(AM, 'AdvanceToNextAction', 0, { onEnter: function (a) { row(a[0], 'AdvanceToNextAction'); } });
hook(AM, 'StartNextAction', 0, { onEnter: function (a) { row(a[0], 'StartNextAction'); } });
hook(AM, 'StopCurrentAction', 1, { onEnter: function (a) { row(a[0], 'StopCurrentAction', { postpone: a[1].toInt32() & 0xff }); } });
hook(AM, 'AdvanceActionIndex', 1, {
    onEnter: function (a) { this.am = a[0]; },
    onLeave: function () { row(this.am, 'AdvanceActionIndex'); }
});
hook(Item, 'Fix', 0, { onEnter: function (a) { send({ f: frame, m: 'Item.Fix', item: uname(a[0]) }); } });
hook(Pawn, 'PlayAngryAnimation', 1, { onEnter: function (a) { send({ f: frame, m: 'PlayAngryAnimation', owner: cls(a[0]), item: uname(a[1]) }); } });
hook(GameInfo, 'TrickDone', 1, { onEnter: function (a) { send({ f: frame, m: 'TrickDone', score: a[1].toInt32() }); } });
const RAU = classFrom(game, S(''), S('RoutineActionUse'));
hook(RAU, 'StopAction', 1, { onEnter: function (a) { send({ f: frame, m: 'RoutineActionUse.StopAction', item: uname(ptr(a[0], O.item)), postpone: a[1].toInt32() & 0xff }); } });
const Rott = classFrom(game, S(''), S('Rottweiler'));
['OnAnimationSequenceEnded', 'OnItemAnimationSequenceEnded', 'OnUseEnded'].forEach(n => {
    hook(Rott, n, 0, { onEnter: function (a) { send({ f: frame, m: 'Rottweiler.' + n }); } });
});
hook(Item, 'StopOlgaInfiniteLoop', 0, { onEnter: function (a) { send({ f: frame, m: 'StopOlgaInfiniteLoop', item: uname(a[0]) }); } });
hook(Pawn, 'RunToHitPawn', 1, { onEnter: function (a) { send({ f: frame, m: 'RunToHitPawn', owner: cls(a[0]), target: cls(a[1]) }); } });
hook(Olga, 'OnItemAnimationSequenceEnded', 0, { onEnter: function (a) { send({ f: frame, m: 'Olga.OnItemAnimationSequenceEnded' }); } });
// GameObject.SetActive(true) on the level's gated items: when the original
// brings them out (the wheel after the mug, the bucket, the cloth, the bird)
const GOK = classFrom(unity, S('UnityEngine'), S('GameObject'));
const WATCH = ['CaptainWheel', 'Washbucket', 'Cloth', 'BirdDead', 'HatchFish', 'Captain', 'DoorBack'];
hook(GOK, 'SetActive', 1, { onEnter: function (a) {
    const on = a[1].toInt32() & 0xff;
    const n = uname(a[0]);
    if (n !== null && WATCH.indexOf(n) >= 0) send({ f: frame, m: 'SetActive', go: n, active: on });
} });
// the pathing at a click: Pawn.MoveToLocation's answer, Woody's abort,
// GetDoorBetweenZones' door and LinkNodes with Helpers' statics
const Helpers = classFrom(game, S(''), S('Helpers'));
const staticGet = f('mono_field_static_get_value', 'void', ['pointer', 'pointer', 'pointer']);
const classVtable = f('mono_class_vtable', 'pointer', ['pointer', 'pointer']);
function statics() {
    const out = {};
    if (Helpers.isNull()) return out;
    const vt = classVtable(dom, Helpers);
    ['StepIndex', 'FirstStepIndex', 'Aux'].forEach(n => {
        const fl = fieldFrom(Helpers, S(n)); if (fl.isNull()) return;
        const o = Memory.alloc(8); staticGet(vt, fl, o); out[n] = o.readS32();
    });
    ['DonePassingHelper'].forEach(n => {
        const fl = fieldFrom(Helpers, S(n)); if (fl.isNull()) return;
        const o = Memory.alloc(8); staticGet(vt, fl, o); out[n] = o.readU8();
    });
    ['OriginalStartZone'].forEach(n => {
        const fl = fieldFrom(Helpers, S(n)); if (fl.isNull()) return;
        const o = Memory.alloc(8); staticGet(vt, fl, o); out[n] = uname(o.readPointer());
    });
    return out;
}
hook(Pawn, 'MoveToLocation', 0, {
    onEnter: function (a) { this.who = cls(a[0]); },
    onLeave: function (r) { send({ f: frame, m: 'MoveToLocation', owner: this.who, ret: r.toInt32() & 0xff }); }
});
const WoodyK2 = classFrom(game, S(''), S('Woody'));
hook(WoodyK2, 'ShouldAbortMove', 5, {
    onEnter: function (a) { this.item = uname(a[1].readPointer()); },
    onLeave: function (r) { send({ f: frame, m: 'ShouldAbortMove', item: this.item, ret: r.toInt32() & 0xff }); }
});
if (!Helpers.isNull()) {
    hook(Helpers, 'GetDoorBetweenZones', 2, {
        onEnter: function (a) { this.z = [uname(a[0]), uname(a[1])]; },
        onLeave: function (r) { send({ f: frame, m: 'GetDoorBetweenZones', zones: this.z, door: uname(r) }); }
    });
    hook(Helpers, 'LinkNodes', 4, {
        onEnter: function (a) { this.z = [uname(a[1]), uname(a[2])]; this.st = statics(); },
        onLeave: function (r) { send({ f: frame, m: 'LinkNodes', zones: this.z, statics: this.st, ret: r.toInt32() & 0xff }); }
    });
}
// the click's raycast: the collider Helpers.GetItemFromCollider is given
// (its GameObject's name) and the Item it answers, with that item's CanUse
const Comp = classFrom(unity, S('UnityEngine'), S('Component'));
const getGO = methodUp(Comp, 'get_gameObject', 0);
const iCanUse = offOf(Item, 'CanUse');
if (!Helpers.isNull()) {
    hook(Helpers, 'GetItemFromCollider', 1, {
        onEnter: function (a) { const go = getGO.isNull() ? NULL : call0(getGO, a[0]); this.go = uname(go); },
        onLeave: function (r) { send({ f: frame, m: 'GetItemFromCollider', collider: this.go, item: uname(r), canUse: (r.isNull() || iCanUse < 0) ? null : r.add(iCanUse).readU8() }); }
    });
}
// Collider.enabled on the mug: MugBehavior's frames 25-57 of the captain's idle
const ColK = classFrom(unity, S('UnityEngine'), S('Collider'));
hook(ColK, 'set_enabled', 1, { onEnter: function (a) {
    const n = uname(a[0]);
    if (n === 'CaptainMug') send({ f: frame, m: 'Collider.enabled', go: n, on: a[1].toInt32() & 0xff });
} });
let lastAnim = null;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function (a) {
        frame++;
        if (pawnOff < 0 || getAnimState.isNull()) return;
        const p = a[0].add(pawnOff).readPointer(); if (p.isNull()) return;
        const ctrl = ptr(p, O.ctrl); if (ctrl.isNull()) return;
        const st = call0(getAnimState, ctrl); if (st.isNull()) return;
        const v = st.add(BOX).readS32();
        if (v !== lastAnim) { lastAnim = v; send({ f: frame, m: 'anim', who: who, anim: v }); }
    }
});
send('armed');

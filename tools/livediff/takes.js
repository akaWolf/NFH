'use strict';
// the take, call by call: Woody.TryUseItem (InputLocked before/after),
// Item.InternalUse (the unlock), the animation switches on Woody's controller
// (SetAnimation's state id) and Pawn.OnPathFinished — with the frame counter
// of GameInfo.Update. run.py --extra=takes.js
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
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const toUtf8 = f('mono_string_to_utf8', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const WoodyK = classFrom(game, S(''), S('Woody'));
const PawnK = classFrom(game, S(''), S('Pawn'));
const ItemK = classFrom(game, S(''), S('Item'));
const PACK = classFrom(game, S(''), S('PawnAnimationController'));
const UObject = classFrom(unity, S('UnityEngine'), S('Object'));
function offOf(k0, n) { let k = k0; while (!k.isNull()) { const fl = fieldFrom(k, S(n)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); } return -1; }
function methodUp(k0, n, c) { let k = k0; while (!k.isNull()) { const mm = methodFrom(k, S(n), c); if (!mm.isNull()) return mm; k = parentOf(k); } return NULL; }
const getName = methodUp(UObject, 'get_name', 0);
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function uname(o) { if (o.isNull()) return null; const ms = call0(getName, o); return ms.isNull() ? null : toUtf8(ms).readUtf8String(); }
const wLocked = offOf(WoodyK, 'InputLocked'), wItemMove = offOf(WoodyK, 'ItemMove'), wMovingUp = offOf(WoodyK, 'MovingUp');
const wCtrl = offOf(PawnK, 'AnimController');
const gWoody = offOf(GameInfo, 'Woody');
let frame = 0, woody = NULL;
function st() { if (woody.isNull()) return {}; return { locked: woody.add(wLocked).readU8(), itemMove: woody.add(wItemMove).readU8(), up: woody.add(wMovingUp).readU8() }; }
function hook(k, n, c, fn) { const mm = methodUp(k, n, c); if (mm.isNull()) { send({ takes: 'missing', method: n }); return; } Interceptor.attach(compile(mm), fn); }
hook(WoodyK, 'TryUseItem', 0, { onEnter: function () { tryFrame = frame; send({ f: frame, m: 'TryUseItem.enter', st: st() }); }, onLeave: function () { send({ f: frame, m: 'TryUseItem.leave', st: st() }); } });
hook(ItemK, 'InternalUse', 0, { onEnter: function (a) { send({ f: frame, m: 'Item.InternalUse', item: uname(a[0]), st: st() }); } });
hook(PawnK, 'OnPathFinished', 0, { onEnter: function (a) { if (a[0].equals(woody)) send({ f: frame, m: 'OnPathFinished', st: st() }); } });
// SetAnimation(T) on Woody's controller: the boxed enum arg
hook(PACK, 'SetAnimation', 1, { onEnter: function (a) {
    if (woody.isNull() || wCtrl < 0 || !a[0].equals(woody.add(wCtrl).readPointer())) return;
    send({ f: frame, m: 'SetAnimation', anim: a[1].toInt32(), st: st() });
} });
hook(PACK, 'SetAnimation', 2, { onEnter: function (a) {
    if (woody.isNull() || wCtrl < 0 || !a[0].equals(woody.add(wCtrl).readPointer())) return;
    send({ f: frame, m: 'SetAnimation2', anim: a[1].toInt32(), type: a[2].toInt32(), st: st() });
} });
const getAnimState = methodUp(PACK, 'get_AnimState', 0);
// Refresh, per frame, on Woody's controller: CurrentAnimation's name and
// index and the accumulator, after the step (the tick accounting itself)
const ACB = parentOf(PACK);                       // AnimationControllerBase<AnimationState>, inflated
const cCur = offOf(ACB, 'CurrentAnimation'), cTime = offOf(ACB, 'animationTime'), cSeqIdx = offOf(ACB, 'SequenceIndex');
let AIoff = null;
hook(ACB, 'Refresh', 0, {
    onEnter: function (a) { this.ctrl = a[0]; },
    onLeave: function () {
        if (woody.isNull() || wCtrl < 0 || !this.ctrl.equals(woody.add(wCtrl).readPointer())) return;
        if ((frame - tryFrame) > 140 || (frame - tryFrame) < -2) return;
        const cur = this.ctrl.add(cCur).readPointer(); if (cur.isNull()) return;
        if (AIoff === null) { const k = classOf(cur); AIoff = { name: offOf(k, 'Name'), idx: offOf(k, 'CurrentFrameIndex'), fr: offOf(k, 'CurrentFrame'), fps: offOf(k, 'FrameRate') }; }
        send({ f: frame, m: 'refresh', anim: cur.add(AIoff.name).readS32(), idx: cur.add(AIoff.idx).readS32(), fr: cur.add(AIoff.fr).readS32(),
               fps: cur.add(AIoff.fps).readFloat(), t: this.ctrl.add(cTime).readFloat(), seq: this.ctrl.add(cSeqIdx).readS32() });
    }
});
let lastAnim = null, tryFrame = -100;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), { onEnter: function (a) {
    frame++; if (gWoody >= 0) woody = a[0].add(gWoody).readPointer();
    if (woody.isNull() || wCtrl < 0 || getAnimState.isNull()) return;
    const ctrl = woody.add(wCtrl).readPointer(); if (ctrl.isNull()) return;
    const st2 = call0(getAnimState, ctrl); if (st2.isNull()) return;
    const v = st2.add(Process.pointerSize * 2).readS32();
    // every frame around a TryUseItem, else on change
    if (v !== lastAnim || (frame - tryFrame) < 8) { lastAnim = v; send({ f: frame, m: 'anim', anim: v, st: st() }); }
} });
send('armed');

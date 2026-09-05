'use strict';
// the pawns' animation-controller ends and their managers' stops, per
// frame: StopSingleAnimation / PlayNextSequenceAnimation on the
// AnimationControllerBase<AnimationState> instantiation (the owner's name,
// Hidden, ShouldStopAction, SequenceIndex), Pawn.SetHidden, and
// ActionManager.StopCurrentAction / AdvanceToNextAction / StartAction with
// the owner's name — run.py --extra=olga.js
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
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const strChars = f('mono_string_to_utf8', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const Pawn = classFrom(game, S(''), S('Pawn'));
const AM = classFrom(game, S(''), S('ActionManager'));
const PACK = classFrom(game, S(''), S('PawnAnimationController'));
const ACB = parentOf(PACK);
const UObject = classFrom(unity, S('UnityEngine'), S('Object'));
const getName = methodFrom(UObject, S('get_name'), 0);
function offOf(klass, name) {
    let k = klass;
    while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); }
    return -1;
}
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function nameOf(obj) { if (obj.isNull()) return null; const s = call0(getName, obj); if (s.isNull()) return null; return strChars(s).readUtf8String(); }
const O = { owner: offOf(ACB, 'Owner'), hidden: offOf(ACB, 'Hidden'), should: offOf(ACB, 'ShouldStopAction'), seqIdx: offOf(ACB, 'SequenceIndex'), seq: offOf(ACB, 'AnimationSequence') };
const A = { owner: offOf(AM, 'Owner'), idx: offOf(AM, 'ActiveActionIndex') };
send({ off: { acb: O, am: A } });
let frame = 0;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), { onEnter() { frame++; } });
function acbRow(self, what) {
    const owner = O.owner >= 0 ? self.add(O.owner).readPointer() : NULL;
    return { f: frame, m: what, owner: nameOf(owner),
             hidden: O.hidden >= 0 ? self.add(O.hidden).readU8() : -1,
             should: O.should >= 0 ? self.add(O.should).readU8() : -1,
             seqIdx: O.seqIdx >= 0 ? self.add(O.seqIdx).readS32() : -1,
             seq: O.seq >= 0 ? !self.add(O.seq).readPointer().isNull() : null };
}
function hookACB(name) {
    const meth = methodFrom(ACB, S(name), -1);
    if (meth.isNull()) { send({ warn: 'no ' + name }); return; }
    Interceptor.attach(compile(meth), { onEnter(a) { send(acbRow(a[0], name)); } });
}
hookACB('StopSingleAnimation');
hookACB('PlayNextSequenceAnimation');
function amRow(self, what, extra) {
    const owner = A.owner >= 0 ? self.add(A.owner).readPointer() : NULL;
    const r = { f: frame, m: what, owner: nameOf(owner), idx: A.idx >= 0 ? self.add(A.idx).readS32() : null };
    if (extra !== undefined) r.arg = extra;
    return r;
}
function hookAM(name, nargs, withArg) {
    const meth = methodFrom(AM, S(name), nargs);
    if (meth.isNull()) { send({ warn: 'no AM.' + name }); return; }
    Interceptor.attach(compile(meth), { onEnter(a) { send(amRow(a[0], name, withArg ? a[1].toInt32() & 0xff : undefined)); } });
}
hookAM('StopCurrentAction', 1, true);
hookAM('AdvanceToNextAction', 0, false);
hookAM('StartAction', 1, false);
const setHidden = methodFrom(Pawn, S('SetHidden'), 1);
if (!setHidden.isNull()) {
    Interceptor.attach(compile(setHidden), { onEnter(a) { send({ f: frame, m: 'SetHidden', owner: nameOf(a[0]), arg: a[1].toInt32() & 0xff }); } });
}
send('armed');

'use strict';
// the Rottweiler's animation clock, per frame: animationTime and the
// current sheet frame, to see exactly when a sequence element advances
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
const dom = root(); attach(dom);
const game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const Pawn = classFrom(game, S(''), S('Pawn'));
const PAC = classFrom(game, S(''), S('PawnAnimationController'));
function offOf(klass, name) {
    let k = klass;
    while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); }
    return -1;
}
const rottOff = offOf(GameInfo, 'Rottweiler'), ctrlOff = offOf(Pawn, 'AnimController');
const timeOff = offOf(PAC, 'animationTime'), curOff = offOf(PAC, 'CurrentAnimation');
send({ off: { rott: rottOff, ctrl: ctrlOff, animationTime: timeOff, CurrentAnimation: curOff } });
let AnimInstance = NULL, frameOff = -1, idxOff = -1;
let n = 0;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function (a) {
        n++;
        if (n > 400) return;
        const r = a[0].add(rottOff).readPointer(); if (r.isNull()) return;
        const c = r.add(ctrlOff).readPointer(); if (c.isNull()) return;
        const cur = curOff >= 0 ? c.add(curOff).readPointer() : NULL;
        if (frameOff < 0 && !cur.isNull()) {
            const classGet = f('mono_object_get_class', 'pointer', ['pointer']);
            const k = classGet(cur);
            frameOff = offOf(k, 'CurrentFrame'); idxOff = offOf(k, 'CurrentIndex');
            send({ instance: '' + k, CurrentFrame: frameOff, CurrentIndex: idxOff });
        }
        send({ f: n, t: timeOff >= 0 ? c.add(timeOff).readFloat() : null,
               fr: (!cur.isNull() && frameOff >= 0) ? cur.add(frameOff).readS32() : null });
    }
});
send('armed');

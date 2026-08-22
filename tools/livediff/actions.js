'use strict';
// the neighbour's ActionManager every frame — the active action's class and
// item, the urgent action, the move action's Active flag, Frozen — sent only
// when something changes; run it through run.py --extra=actions.js
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
const classGet = f('mono_object_get_class', 'pointer', ['pointer']);
const className = f('mono_class_get_name', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const Pawn = classFrom(game, S(''), S('Pawn'));
const AM = classFrom(game, S(''), S('ActionManager'));
const RA = classFrom(game, S(''), S('RoutineAction'));
const UObject = classFrom(unity, S('UnityEngine'), S('Object'));
const getName = methodFrom(UObject, S('get_name'), 0);
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const strChars = f('mono_string_to_utf8', 'pointer', ['pointer']);
function offOf(klass, name) {
    let k = klass;
    while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); }
    return -1;
}
const who = (typeof ROLE === 'undefined') ? 'Rottweiler' : ROLE;
const pawnOff = offOf(GameInfo, who);
const Owner = classFrom(game, S(''), S(who));
const amOff = offOf(Owner.isNull() ? Pawn : Owner, 'ActionManager');   // a Rottweiler field, not Pawn's
const A = {}; ['ActiveAction', 'UrgentAction', 'MoveAction', 'Frozen', 'ActiveActionIndex', 'SameZone'].forEach(n => { A[n] = offOf(AM, n); });
const R = {}; ['Active', 'Item', 'ForceFinished', 'Urgent', 'MoveOnly'].forEach(n => { R[n] = offOf(RA, n); });
send({ off: { am: amOff, A: A, R: R }, role: who });
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function nameOf(obj) { if (obj.isNull()) return null; const s = call0(getName, obj); if (s.isNull()) return null; return strChars(s).readUtf8String(); }
function describe(act) {
    if (act.isNull()) return null;
    const cls = className(classGet(act)).readCString();
    const item = R.Item >= 0 ? act.add(R.Item).readPointer() : NULL;
    return { cls: cls, item: nameOf(item), active: R.Active >= 0 ? act.add(R.Active).readU8() : -1,
             forced: R.ForceFinished >= 0 ? act.add(R.ForceFinished).readU8() : -1 };
}
let frame = 0, last = '';
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function (a) {
        frame++;
        if (pawnOff < 0 || amOff < 0) return;
        const p = a[0].add(pawnOff).readPointer(); if (p.isNull()) return;
        const am = p.add(amOff).readPointer(); if (am.isNull()) return;
        const row = { f: frame,
                      active: describe(am.add(A.ActiveAction).readPointer()),
                      urgent: describe(am.add(A.UrgentAction).readPointer()),
                      move: describe(am.add(A.MoveAction).readPointer()),
                      frozen: A.Frozen >= 0 ? am.add(A.Frozen).readU8() : -1,
                      idx: A.ActiveActionIndex >= 0 ? am.add(A.ActiveActionIndex).readS32() : null };
        const key = JSON.stringify([row.active, row.urgent, row.move, row.frozen, row.idx]);
        if (key !== last) { last = key; send(row); }
    }
});
send('armed');

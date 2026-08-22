'use strict';
// one pawn's movement fields every frame, read at the top of
// GameInfo.Update (before the frame's logic): the position, Velocity,
// MoveLocation / MinDistToNextMove / MoveIndex, the portal and item flags,
// MovementPaused, the animation state — to see which branch of
// ProcessMovement / MoveToDoor the original took on a given frame.
// ROLE ('Woody' | 'Rottweiler') names the GameInfo field; run it through
// run.py --extra=pawn.js --role=<ROLE>
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
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const Pawn = classFrom(game, S(''), S('Pawn'));
const PAC = classFrom(game, S(''), S('PawnAnimationController'));
const Component = classFrom(unity, S('UnityEngine'), S('Component'));
const Transform = classFrom(unity, S('UnityEngine'), S('Transform'));
const getTransform = methodFrom(Component, S('get_transform'), 0);
const getPosition = methodFrom(Transform, S('get_position'), 0);
const BOX = Process.pointerSize * 2;
function offOf(klass, name) {
    let k = klass;
    while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); }
    return -1;
}
const who = (typeof ROLE === 'undefined') ? 'Rottweiler' : ROLE;
const pawnOff = offOf(GameInfo, who);
const F = {};
['Velocity', 'MoveLocation', 'MinDistToNextMove', 'MoveIndex', 'PortalMove', 'ItemMove',
 'MovingUp', 'MovingDown', 'IsWarping', 'MovementPaused', 'TransitionMove', 'ExitingDoor',
 'UseDoorAtOnce', 'AtDoorLocation', 'InUrgentMove', 'MoveLocationChanged', 'WasMovingLeft',
 'Speed', 'SneakFlag', 'AnimController'].forEach(n => { F[n] = offOf(Pawn, n); });
const animOff = offOf(PAC, 'AnimState');
send({ off: F, anim: animOff, role: who, pawnOff: pawnOff });
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function pos(c) { const t = call0(getTransform, c); if (t.isNull()) return null; const b = call0(getPosition, t); return b.isNull() ? null : [b.add(BOX).readFloat(), b.add(BOX + 4).readFloat()]; }
const b8 = (p, n) => F[n] >= 0 ? p.add(F[n]).readU8() : -1;
let frame = 0;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function (a) {
        frame++;
        if (pawnOff < 0) return;
        const p = a[0].add(pawnOff).readPointer(); if (p.isNull()) return;
        const ctrl = F.AnimController >= 0 ? p.add(F.AnimController).readPointer() : NULL;
        send({ f: frame, p: pos(p),
               v: F.Velocity >= 0 ? [p.add(F.Velocity).readFloat(), p.add(F.Velocity + 4).readFloat()] : null,
               ml: F.MoveLocation >= 0 ? [p.add(F.MoveLocation).readFloat(), p.add(F.MoveLocation + 4).readFloat()] : null,
               min: F.MinDistToNextMove >= 0 ? p.add(F.MinDistToNextMove).readFloat() : null,
               idx: F.MoveIndex >= 0 ? p.add(F.MoveIndex).readS32() : null,
               spd: F.Speed >= 0 ? p.add(F.Speed).readFloat() : null,
               anim: (!ctrl.isNull() && animOff >= 0) ? ctrl.add(animOff).readS32() : null,
               fl: { portal: b8(p, 'PortalMove'), item: b8(p, 'ItemMove'), up: b8(p, 'MovingUp'),
                     down: b8(p, 'MovingDown'), warp: b8(p, 'IsWarping'), paused: b8(p, 'MovementPaused'),
                     trans: b8(p, 'TransitionMove'), exiting: b8(p, 'ExitingDoor'), atonce: b8(p, 'UseDoorAtOnce'),
                     atdoor: b8(p, 'AtDoorLocation'), urgent: b8(p, 'InUrgentMove'), mlc: b8(p, 'MoveLocationChanged'),
                     left: b8(p, 'WasMovingLeft'), sneak: b8(p, 'SneakFlag') } });
    }
});
send('armed');

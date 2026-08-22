'use strict';
// every TakeNextStep the Rottweiler takes: the new MoveLocation and the
// MinDistToNextMove that goes with it — the step list, as the original
// builds it
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
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const classGet = f('mono_object_get_class', 'pointer', ['pointer']);
const className = f('mono_class_get_name', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const Pawn = classFrom(game, S(''), S('Pawn'));
const Component = classFrom(unity, S('UnityEngine'), S('Component'));
const Transform = classFrom(unity, S('UnityEngine'), S('Transform'));
const getTransform = methodFrom(Component, S('get_transform'), 0);
const getPosition = methodFrom(Transform, S('get_position'), 0);
const BOX = Process.pointerSize * 2;
const off = {};
['MoveLocation', 'MinDistToNextMove', 'MoveIndex', 'ItemMove', 'MovingUp', 'PortalMove'].forEach(n => {
    const fl = fieldFrom(Pawn, S(n));
    off[n] = fl.isNull() ? -1 : fieldOff(fl);
});
send({ off: off });
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function pos(c) { const t = call0(getTransform, c); if (t.isNull()) return null; const b = call0(getPosition, t); return b.isNull() ? null : [b.add(BOX).readFloat(), b.add(BOX + 4).readFloat()]; }
let frame = 0;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), { onEnter: function () { frame++; } });
const tns = methodFrom(Pawn, S('TakeNextStep'), 0);
Interceptor.attach(compile(tns), {
    onEnter: function (args) {
        this.self = args[0];
        this.rott = className(classGet(args[0])).readCString() === 'Rottweiler';
        if (this.rott) this.at = pos(args[0]);
    },
    onLeave: function () {
        if (!this.rott) return;
        const w = this.self;
        const ml = w.add(off.MoveLocation);
        send({ f: frame, at: this.at,
               to: [ml.readFloat(), ml.add(4).readFloat()],
               min: w.add(off.MinDistToNextMove).readFloat(),
               idx: w.add(off.MoveIndex).readS32(),
               item: w.add(off.ItemMove).readU8(), up: w.add(off.MovingUp).readU8() });
    }
});
send('armed');

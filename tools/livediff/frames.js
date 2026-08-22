'use strict';
// What runs when, inside one frame of the original: ActionManager.Update,
// Pawn.ProcessMovement, TakeNextStep and the RoutineAction stops, stamped
// with the GameInfo.Update frame counter, plus whether the Rottweiler's
// position actually changed. This is how the port's own tick order was
// checked against Unity's (World.tick ticks pawns before routines, which
// is what the original does too).
//
//   python3 - <<'PY'
//   import frida, time
//   dev = frida.get_device_manager().add_remote_device('localhost:27042')
//   app = [a for a in dev.enumerate_applications()
//          if a.identifier == 'com.nordigames.nfh2' and a.pid][0]
//   s = dev.attach(app.pid).create_script(open('tools/livediff/frames.js').read())
//   s.on('message', lambda m, d: print(m.get('payload')))
//   s.load(); time.sleep(60)
//   PY
const m = Process.getModuleByName('libmono.so');
const f = (n, r, a) => new NativeFunction(m.findExportByName(n), r, a);
const S = s => Memory.allocUtf8String(s);
const root = f('mono_get_root_domain', 'pointer', []);
const attach = f('mono_thread_attach', 'pointer', ['pointer']);
const imgLoaded = f('mono_image_loaded', 'pointer', ['pointer']);
const classFrom = f('mono_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']);
const methodFrom = f('mono_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);
const compile = f('mono_compile_method', 'pointer', ['pointer']);
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const classGet = f('mono_object_get_class', 'pointer', ['pointer']);
const className = f('mono_class_get_name', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const K = (img, ns, n) => classFrom(img, S(ns), S(n));
const GameInfo = K(game, '', 'GameInfo'), Pawn = K(game, '', 'Pawn');
const AM = K(game, '', 'ActionManager'), RAU = K(game, '', 'RoutineActionUse'), RA = K(game, '', 'RoutineAction');
const Component = K(unity, 'UnityEngine', 'Component'), Transform = K(unity, 'UnityEngine', 'Transform');
const getTransform = methodFrom(Component, S('get_transform'), 0), getPosition = methodFrom(Transform, S('get_position'), 0);
const BOX = Process.pointerSize * 2;
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function pos(c) { const t = call0(getTransform, c); if (t.isNull()) return null; const b = call0(getPosition, t); return b.isNull() ? null : [b.add(BOX).readFloat(), b.add(BOX + 4).readFloat()]; }
const isRott = self => className(classGet(self)).readCString() === 'Rottweiler';
let frame = 0;
const lines = [];
function hook(klass, name, argc, label, opts) {
    const mm = methodFrom(klass, S(name), argc);
    if (mm.isNull()) { send('no method ' + label); return; }
    Interceptor.attach(compile(mm), {
        onEnter: function (args) {
            this.self = args[0];
            if (opts && opts.rottOnly && !isRott(this.self)) { this.skip = true; return; }
            if (opts && opts.pos) { const p = pos(this.self); this.before = p; }
            if (!(opts && opts.pos)) lines.push([frame, label, 'enter']);
        },
        onLeave: function () {
            if (this.skip) return;
            if (opts && opts.pos) {
                const p = pos(this.self);
                const moved = this.before && p && (Math.abs(p[0]-this.before[0]) + Math.abs(p[1]-this.before[1]) > 1e-4);
                lines.push([frame, label, moved ? 'moved ' + p[0].toFixed(3) + ',' + p[1].toFixed(3) : 'still']);
            }
        }
    });
}
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), { onEnter: function () { frame++; } });
hook(AM, 'Update', 0, 'ActionManager.Update');
hook(AM, 'StartAction', 1, 'ActionManager.StartAction');
hook(AM, 'AdvanceToNextAction', 0, 'AdvanceToNextAction');
hook(Pawn, 'ProcessMovement', 0, 'Rott.ProcessMovement', { rottOnly: true, pos: true });
hook(Pawn, 'TakeNextStep', 0, 'Rott.TakeNextStep', { rottOnly: true });
hook(RA, 'StopAction', 1, 'RoutineAction.StopAction');
hook(RAU, 'StopAction', 1, 'RoutineActionUse.StopAction');
setInterval(function () { if (lines.length) { send(lines.splice(0)); } }, 500);
send('armed');

'use strict';
// the frame each of a list of methods runs: the intro's StartGame, the
// entrance, the door animations' starts and ends, the alerter's flinch,
// the routine's action boundaries — one row per call, with the class of
// `this` and the door / item / action name where there is one; through
// run.py --extra=events.js (frames convert to level frames as tap.json's)
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
const strChars = f('mono_string_to_utf8', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const UObject = classFrom(unity, S('UnityEngine'), S('Object'));
const getName = methodFrom(UObject, S('get_name'), 0);
const GameInfo = classFrom(game, S(''), S('GameInfo'));
function call0(meth, self) { const e = Memory.alloc(4); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
function nameOf(obj) { if (obj.isNull()) return null; try { const s = call0(getName, obj); return s.isNull() ? null : strChars(s).readUtf8String(); } catch (e) { return null; } }
let frame = 0;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), { onEnter: function () { frame++; } });
// [class, method, argc, which argument names the object (0 = this, 1 = first arg), or -1]
const HOOKS = [
    ['IntroAnimation', 'StartGame', 0, -1], ['IntroAnimation', 'StopIntroAnimation', 0, -1],
    ['Woody', 'StartMoveToLocation', 1, -1], ['Woody', 'ProcessMoveInput', 2, -1],
    ['Pawn', 'PlayDoorLeaveAnimation', 1, 1], ['Pawn', 'PlayDoorEnterAnimation', 1, 1],
    ['Pawn', 'OnDoorLeaveAnimationFinished', 1, 1], ['Pawn', 'OnDoorEnterAnimationFinished', 1, 1],
    ['Pawn', 'EndPortalMove', 1, -1], ['Pawn', 'TakeNextStep', 0, -1],
    ['Door', 'PlayAnimation', 1, 0], ['Door', 'OnAnimationEnded', 1, 0],
    ['Woody', 'SeeAlerter', 1, 1], ['Woody', 'PlayShortFearAnimation', 1, 1],
    ['Alerter', 'CoRoutineWoodySeeAlerter', 0, 0], ['Alerter', 'OnWoodyEnter', 0, 0],
    ['ActionManager', 'StartAction', 1, -1], ['ActionManager', 'StopCurrentAction', 1, -1],
    ['RoutineAction', 'StartAction', 2, 0], ['Item', 'Use', 1, 0],
];
const hooked = [];
HOOKS.forEach(function (h) {
    const k = classFrom(game, S(''), S(h[0])); if (k.isNull()) { hooked.push(h[0] + ':missing'); return; }
    const meth = methodFrom(k, S(h[1]), h[2]); if (meth.isNull()) { hooked.push(h[0] + '.' + h[1] + ':missing'); return; }
    const label = h[0] + '.' + h[1], which = h[3];
    try { Interceptor.attach(compile(meth), {
        onEnter: function (args) {
            let who = null;
            try {
                if (which >= 0) { const o = args[which]; who = o.isNull() ? null : nameOf(o) || className(classGet(o)).readCString(); }
                else { who = className(classGet(args[0])).readCString(); }
            } catch (e) { who = '?'; }
            send({ f: frame, ev: label, who: who });
        }
    }); hooked.push(label); } catch (e) { hooked.push(label + ':' + e); }
});
// every WaitForSeconds a coroutine yields: its seconds and the frame — the
// next one's frame is the frame the previous wait let the coroutine go on
const WFS = classFrom(unity, S('UnityEngine'), S('WaitForSeconds'));
const wfsCtor = WFS.isNull() ? NULL : methodFrom(WFS, S('.ctor'), 1);
if (!wfsCtor.isNull()) {
    Interceptor.attach(compile(wfsCtor), {
        onEnter: function (args) {
            // x86 cdecl: the float rides a 4-byte stack slot
            const bits = Memory.alloc(4); bits.writeU32(args[1].toUInt32());
            send({ f: frame, ev: 'WaitForSeconds', who: bits.readFloat().toFixed(3) });
        }
    });
    hooked.push('WaitForSeconds..ctor');
}
send({ hooked: hooked });
send('armed');

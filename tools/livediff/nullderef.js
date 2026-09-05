'use strict';
// a managed null dereference on the game's thread, on purpose: on frame 600
// GameInfo.Update runs with `this` = null (the JIT's field reads fault on
// the null page). ROLE='nofix' first puts the thread back on an 8 KB
// alternate signal stack — Mono's size — so the run shows the bench's frida
// death; ROLE='fix' keeps state.js's 1 MB stack, and the game should log
// the NullReferenceException and go on. run.py --extra=nullderef.js --role=…
const m = Process.getModuleByName('libmono.so');
const f = (n, r, a) => new NativeFunction(m.findExportByName(n), r, a);
const S = s => Memory.allocUtf8String(s);
const root = f('mono_get_root_domain', 'pointer', []);
const attach = f('mono_thread_attach', 'pointer', ['pointer']);
const imgLoaded = f('mono_image_loaded', 'pointer', ['pointer']);
const classFrom = f('mono_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']);
const methodFrom = f('mono_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);
const compile = f('mono_compile_method', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const libc = Process.getModuleByName('libc.so');
const sigaltstack = new NativeFunction(libc.findExportByName('sigaltstack'), 'int', ['pointer', 'pointer']);
const mode = (typeof ROLE === 'undefined') ? 'fix' : ROLE;
const small = Memory.alloc(8192);
let n = 0, fired = false;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function (args) {
        n++;
        if (fired || n < 600) return;
        fired = true;
        const old = Memory.alloc(12); sigaltstack(NULL, old);
        let set = null;
        if (mode === 'nofix') {
            const ss = Memory.alloc(12);
            ss.writePointer(small); ss.add(4).writeS32(0); ss.add(8).writeU32(8192);
            set = sigaltstack(ss, NULL);
        }
        send({ nullderef: 'firing', mode: mode, frame: n, altstack_before: old.add(8).readU32(), set: set });
        args[0] = NULL;                       // GameInfo.Update on a null this
    }
});
send('armed');

// Read the running original's state, frame by frame, in the shape
// runtime/record.py writes — so the two traces diff directly.
//
// Everything goes through Mono's own C API out of libmono.so: classes
// and fields are resolved by the names the port already cites, and
// Unity's value-returning properties (Transform.position) are called
// through mono_runtime_invoke, which boxes the result so the floats can
// be read straight out of the returned object.
'use strict';

// libmono only appears once the player starts, several seconds after
// spawn, so the whole probe waits for it
const boot = setInterval(function () {
    const m = Process.findModuleByName('libmono.so');
    if (m === null) return;
    // the module is mapped well before the runtime is up: wait for a
    // root domain and for the game's own image to be loaded
    const dom = m.findExportByName('mono_get_root_domain');
    const img = m.findExportByName('mono_image_loaded');
    if (!dom || !img) return;
    if (new NativeFunction(dom, 'pointer', [])().isNull()) return;
    const probe = new NativeFunction(img, 'pointer', ['pointer'])(
        Memory.allocUtf8String('Assembly-CSharp'));
    if (probe.isNull()) return;
    clearInterval(boot);
    try { start(); } catch (e) { send({ type: 'error', message: '' + e }); }
}, 50);

function start() {
const mono = Process.getModuleByName('libmono.so');
const fn = (n, r, a) => {
    const p = mono.findExportByName(n);
    if (!p) throw new Error('libmono lacks ' + n);
    return new NativeFunction(p, r, a);
};
const str = s => Memory.allocUtf8String(s);

const mono_get_root_domain = fn('mono_get_root_domain', 'pointer', []);
const mono_thread_attach = fn('mono_thread_attach', 'pointer', ['pointer']);
const mono_domain_assembly_open = fn('mono_domain_assembly_open', 'pointer', ['pointer', 'pointer']);
const mono_assembly_get_image = fn('mono_assembly_get_image', 'pointer', ['pointer']);
const mono_class_from_name = fn('mono_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']);
const mono_class_get_method_from_name = fn('mono_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);
const mono_class_get_field_from_name = fn('mono_class_get_field_from_name', 'pointer', ['pointer', 'pointer']);
const mono_field_get_offset = fn('mono_field_get_offset', 'int', ['pointer']);
const mono_compile_method = fn('mono_compile_method', 'pointer', ['pointer']);
const mono_runtime_invoke = fn('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);

const domain = mono_get_root_domain();
mono_thread_attach(domain);

const mono_image_loaded = fn('mono_image_loaded', 'pointer', ['pointer']);

function image(name) {
    // only ever ask for images the runtime already has: opening an
    // assembly by path from here crashes the player
    const img = mono_image_loaded(str(name));
    if (img.isNull()) throw new Error('image not loaded: ' + name);
    return img;
}
const asmGame = image('Assembly-CSharp');
const asmUnity = image('UnityEngine');

const klass = (img, ns, n) => mono_class_from_name(img, str(ns), str(n));
const method = (k, n, argc) => mono_class_get_method_from_name(k, str(n), argc);

function offsets(k, names) {
    const out = {};
    names.forEach(function (n) {
        const f = mono_class_get_field_from_name(k, str(n));
        out[n] = f.isNull() ? -1 : mono_field_get_offset(f);
    });
    return out;
}

// --- the pinned clock ------------------------------------------------
// The port steps a fixed 1/60 s (runtime/record.py); pinning the
// original's dt to the same quantum makes the two advance in identical
// steps, so a slow emulator changes nothing about the trace. The
// property is an internal call, but its JIT-compiled wrapper is an
// ordinary function and can be replaced outright.
const DT = 1.0 / 60.0;
const Time = klass(asmUnity, 'UnityEngine', 'Time');
const pinned = [];
['get_deltaTime', 'get_fixedDeltaTime', 'get_unscaledDeltaTime',
 'get_smoothDeltaTime'].forEach(function (name) {
    const m = method(Time, name, 0);
    if (m.isNull()) return;
    Interceptor.replace(mono_compile_method(m),
        new NativeCallback(function () { return DT; }, 'float', []));
    pinned.push(name);
});

// Random.InitState: one seed, so the original's die rolls repeat
const Random = klass(asmUnity, 'UnityEngine', 'Random');
const initState = method(Random, 'InitState', 1);
if (!initState.isNull()) {
    const seed = Memory.alloc(4); seed.writeS32(0);
    const args = Memory.alloc(Process.pointerSize); args.writePointer(seed);
    const exc = Memory.alloc(Process.pointerSize); exc.writePointer(NULL);
    mono_runtime_invoke(initState, NULL, args, exc);
    pinned.push('Random.InitState(0)');
}

const GameInfo = klass(asmGame, '', 'GameInfo');
const Component = klass(asmUnity, 'UnityEngine', 'Component');
const Transform = klass(asmUnity, 'UnityEngine', 'Transform');
const getTransform = method(Component, 'get_transform', 0);
const getPosition = method(Transform, 'get_position', 0);

// MonoObject on 32-bit: vtable pointer + sync block, then the data
const BOX_DATA = Process.pointerSize * 2;

function invoke(m, self) {
    const exc = Memory.alloc(Process.pointerSize);
    exc.writePointer(NULL);
    const r = mono_runtime_invoke(m, self, NULL, exc);
    return exc.readPointer().isNull() ? r : NULL;
}

function position(component) {
    if (component.isNull()) return null;
    const t = invoke(getTransform, component);
    if (t.isNull()) return null;
    const boxed = invoke(getPosition, t);
    if (boxed.isNull()) return null;
    return [boxed.add(BOX_DATA).readFloat(),
            boxed.add(BOX_DATA + 4).readFloat(),
            boxed.add(BOX_DATA + 8).readFloat()];
}

// the counters GameState mirrors (runtime/world.py) plus the actors the
// score depends on
const GI = offsets(GameInfo, ['CompletedTricksCount', 'TotalTricksCount',
                              'WinningTricksCount', 'FinalTrickScore',
                              'FinalViewerRating', 'Won', 'GameEnding',
                              'gotCaught', 'Woody', 'Rottweiler']);
send({ type: 'ready', offsets: GI, pinned: pinned });

const bool8 = (p, o) => p.add(o).readU8() !== 0;
const i32 = (p, o) => p.add(o).readS32();

let frame = 0;
Interceptor.attach(mono_compile_method(method(GameInfo, 'Update', 0)), {
    onEnter: function (args) {
        const gi = args[0];
        frame++;
        const woody = GI.Woody >= 0 ? gi.add(GI.Woody).readPointer() : NULL;
        const rott = GI.Rottweiler >= 0 ? gi.add(GI.Rottweiler).readPointer() : NULL;
        send({
            type: 'frame',
            n: frame,
            game: {
                tricks: i32(gi, GI.CompletedTricksCount),
                total: i32(gi, GI.TotalTricksCount),
                score: i32(gi, GI.FinalTrickScore),
                rating: i32(gi, GI.FinalViewerRating),
                won: bool8(gi, GI.Won),
                ending: bool8(gi, GI.GameEnding),
                caught: bool8(gi, GI.gotCaught),
            },
            woody: position(woody),
            rott: position(rott),
        });
    }
});
send({ type: 'armed' });
}

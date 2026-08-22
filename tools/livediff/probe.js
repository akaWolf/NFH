// Track A, probe: prove the original game's managed code can be hooked
// and read while it runs.
//
// The build is Mono (lib/x86/libmono.so ships next to libunity.so), so
// Assembly-CSharp's methods are reachable by name — no address reversing.
// This script resolves the runtime's own API out of libmono, walks to
// GameInfo, hooks its per-frame Update and prints the counters the port
// keeps in GameState (runtime/world.py) — the first side-by-side pair.
'use strict';

const mono = Process.findModuleByName('libmono.so');
if (!mono) { console.log('!! libmono.so not loaded yet'); }

function api(name, ret, args) {
    const p = mono.findExportByName(name);
    if (!p) { console.log('!! missing export ' + name); return null; }
    return new NativeFunction(p, ret, args);
}

const mono_get_root_domain = api('mono_get_root_domain', 'pointer', []);
const mono_thread_attach = api('mono_thread_attach', 'pointer', ['pointer']);
const mono_domain_assembly_open = api('mono_domain_assembly_open', 'pointer', ['pointer', 'pointer']);
const mono_assembly_get_image = api('mono_assembly_get_image', 'pointer', ['pointer']);
const mono_class_from_name = api('mono_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']);
const mono_class_get_method_from_name = api('mono_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);
const mono_compile_method = api('mono_compile_method', 'pointer', ['pointer']);
const mono_class_get_field_from_name = api('mono_class_get_field_from_name', 'pointer', ['pointer', 'pointer']);
const mono_field_get_offset = api('mono_field_get_offset', 'int', ['pointer']);

const domain = mono_get_root_domain();
mono_thread_attach(domain);

const asm = mono_domain_assembly_open(domain, Memory.allocUtf8String('Assembly-CSharp'));
const image = mono_assembly_get_image(asm);
console.log('[probe] image=' + image);

function klass(ns, name) {
    return mono_class_from_name(image, Memory.allocUtf8String(ns), Memory.allocUtf8String(name));
}

function fieldOffset(k, name) {
    const f = mono_class_get_field_from_name(k, Memory.allocUtf8String(name));
    return f.isNull() ? -1 : mono_field_get_offset(f);
}

const GameInfo = klass('', 'GameInfo');
console.log('[probe] GameInfo=' + GameInfo);

// the counters the port mirrors in GameState.__init__
const FIELDS = ['CompletedTricksCount', 'TotalTricksCount', 'FinalTrickScore',
                'FinalViewerRating', 'Won', 'GameEnding', 'gotCaught'];
const off = {};
FIELDS.forEach(function (n) { off[n] = fieldOffset(GameInfo, n); });
console.log('[probe] offsets ' + JSON.stringify(off));

const update = mono_class_get_method_from_name(GameInfo, Memory.allocUtf8String('Update'), 0);
const code = mono_compile_method(update);
console.log('[probe] GameInfo.Update jit=' + code);

let frame = 0;
Interceptor.attach(code, {
    onEnter: function (args) {
        frame++;
        if (frame % 60 !== 1 || frame > 600) return;
        const self = args[0];
        const st = {};
        FIELDS.forEach(function (n) {
            if (off[n] < 0) return;
            const p = self.add(off[n]);
            st[n] = (n === 'Won' || n === 'GameEnding' || n === 'gotCaught')
                ? p.readU8() : p.readS32();
        });
        console.log('[frame ' + frame + '] ' + JSON.stringify(st));
    }
});
console.log('[probe] armed');

'use strict';
// the dexterity round, played for the bench: every frame after
// DexterityComponent.FixedUpdate (cs:183-262) the pick (ForegroundRect) is put
// on the field's centre (BackgroundRect), so the sway term reads MaxSway
// and PercentageDone climbs 20 -> 85 at 25/s — the round is won in 2.6 s
// as a steady hand wins it. A tap script cannot move a finger; this can.
// run it through run.py --extra=dexterity.js (ROLE is unused here)
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
const Dex = classFrom(game, S(''), S('DexterityComponent'));
function offOf(klass, name) {
    let k = klass;
    while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); }
    return -1;
}
const F = {};
['ForegroundRect', 'BackgroundRect', 'initialized', 'PercentageDone', 'FirstTimeOnly'].forEach(n => { F[n] = offOf(Dex, n); });
send({ dexterity: 'offsets', F: F });
// a Unity Rect is four floats: x, y, width, height
const rect = p => [p.readFloat(), p.add(4).readFloat(), p.add(8).readFloat(), p.add(12).readFloat()];
let rounds = 0, held = 0, lastPct = null;
const wasInit = new Map();           // per component: the round's start is initialized 0 -> 1
const fixedUpdate = methodFrom(Dex, S('FixedUpdate'), 0);
if (fixedUpdate.isNull()) throw new Error('no DexterityComponent.FixedUpdate');
Interceptor.attach(compile(fixedUpdate), {
    onEnter: function (a) { this.self = a[0]; },
    onLeave: function () {
        const self = this.self;
        const init = F.initialized >= 0 && self.add(F.initialized).readU8() !== 0;
        const key = self.toString();
        if (init && !wasInit.get(key)) { held = 0; lastPct = null; }
        wasInit.set(key, init);
        if (!init) return;
        const bg = rect(self.add(F.BackgroundRect)), fg = rect(self.add(F.ForegroundRect));
        const cx = bg[0] + (bg[2] - fg[2]) / 2, cy = bg[1] + (bg[3] - fg[3]) / 2;
        self.add(F.ForegroundRect).writeFloat(cx);
        self.add(F.ForegroundRect).add(4).writeFloat(cy);
        held++;
        const pct = F.PercentageDone >= 0 ? self.add(F.PercentageDone).readFloat() : null;
        if (held === 1) { rounds++; send({ dexterity: 'round', n: rounds, pct: pct, bg: bg, fg: fg }); }
        if (pct !== null && lastPct !== null && Math.floor(pct / 10) !== Math.floor(lastPct / 10)) send({ dexterity: 'fill', n: rounds, pct: pct, held: held });
        lastPct = pct;
    }
});
// the round's end: initialized drops (Initialize runs again on the next
// round) — count the frames held per round for the log
send('armed');

'use strict';
// the score the original computes: GameInfo.CalculateScore on leave
// (CompletedTricksCount, TotalTricksCount, FinalTrickScore,
// CompoundTrickScore, FinalCompoundTrickScore, FinalViewerRating, Won,
// Perfect) and, per frame on change, the Rottweiler's AngryMeter (to the
// unit) and AngryCountTicks — run.py --extra=score.js
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
const Rott = classFrom(game, S(''), S('Rottweiler'));
function offOf(klass, name) {
    let k = klass;
    while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); }
    return -1;
}
const G = {};
['CompletedTricksCount', 'TotalTricksCount', 'FinalTrickScore', 'CompoundTrickScore', 'FinalCompoundTrickScore', 'FinalViewerRating', 'Won', 'Perfect', 'Rottweiler', 'TimeUp'].forEach(n => { G[n] = offOf(GameInfo, n); });
const R = {};
['AngryMeter', 'AngryCountTicks', 'CanDecreaseAngryMeter'].forEach(n => { R[n] = offOf(Rott, n); });
send({ score: 'offsets', G: G, R: R });
let frame = 0, last = '';
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter(a) {
        frame++;
        const self = a[0];
        const rp = G.Rottweiler >= 0 ? self.add(G.Rottweiler).readPointer() : NULL;
        if (rp.isNull()) return;
        const meter = R.AngryMeter >= 0 ? rp.add(R.AngryMeter).readFloat() : -1;
        const ticks = R.AngryCountTicks >= 0 ? rp.add(R.AngryCountTicks).readS32() : -1;
        const dec = R.CanDecreaseAngryMeter >= 0 ? rp.add(R.CanDecreaseAngryMeter).readU8() : -1;
        const done = G.CompletedTricksCount >= 0 ? self.add(G.CompletedTricksCount).readS32() : -1;
        const key = [Math.round(meter), ticks, dec, done].join(',');
        if (key !== last) { last = key; send({ f: frame, m: 'meter', meter: Math.round(meter * 10) / 10, ticks: ticks, decaying: dec, done: done }); }
    }
});
Interceptor.attach(compile(methodFrom(GameInfo, S('CalculateScore'), 0)), {
    onEnter(a) { this.self = a[0]; },
    onLeave() {
        const s = this.self; const r = { f: frame, m: 'score' };
        ['CompletedTricksCount', 'TotalTricksCount', 'FinalTrickScore', 'CompoundTrickScore', 'FinalCompoundTrickScore', 'FinalViewerRating'].forEach(n => { if (G[n] >= 0) r[n] = s.add(G[n]).readS32(); });
        ['Won', 'Perfect', 'TimeUp'].forEach(n => { if (G[n] >= 0) r[n] = s.add(G[n]).readU8(); });
        send(r);
    }
});
send('armed');

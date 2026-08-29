'use strict';
// the original's zone graph as it stands at runtime: ZoneController.Zones
// in its order (FindGameObjectsWithTag, ZoneController.cs:10 — the order
// Helpers.GetShortestPath's Dijkstra seeds its list with) and each zone's
// Neighbors in theirs (Zone.AddNeighbor, Zone.cs:132) — the tie-break
// between two equal routes lives in these orders. Sent once, on the first
// GameInfo.Update after the level is up: { zones: [name...], neighbors:
// {name: [name...]} }. Run through run.py --extra=zones.js
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
const classVtable = f('mono_class_vtable', 'pointer', ['pointer', 'pointer']);
const staticGet = f('mono_field_static_get_value', 'void', ['pointer', 'pointer', 'pointer']);
const objClass = f('mono_object_get_class', 'pointer', ['pointer']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const ZC = classFrom(game, S(''), S('ZoneController'));
const ZoneK = classFrom(game, S(''), S('Zone'));
const UObject = classFrom(unity, S('UnityEngine'), S('Object'));
const getName = methodFrom(UObject, S('get_name'), 0);
function call0(meth, self) { const e = Memory.alloc(Process.pointerSize); e.writePointer(NULL); const r = invoke(meth, self, NULL, e); return e.readPointer().isNull() ? r : NULL; }
// MonoString: the object header, then int32 length, then UTF-16 chars
const BOX = Process.pointerSize * 2;
function jsString(ms) { if (ms.isNull()) return null; const n = ms.add(BOX).readS32(); return n > 0 ? ms.add(BOX + 4).readUtf16String(n) : ''; }
function nameOf(o) { return o.isNull() ? null : jsString(call0(getName, o)); }
function listItems(list) {
    if (list.isNull()) return [];
    const k = objClass(list);
    const items = list.add(fieldOff(fieldFrom(k, S('_items')))).readPointer();
    const size = list.add(fieldOff(fieldFrom(k, S('_size')))).readS32();
    const out = [];
    for (let i = 0; i < size; i++) out.push(items.add(4 * Process.pointerSize + i * Process.pointerSize).readPointer());
    return out;
}
const fZones = fieldFrom(ZC, S('Zones'));
const fNeighbors = fieldFrom(ZoneK, S('Neighbors'));
// one dump per GameInfo instance: the first Update after the script loads
// still belongs to the level the game was in, the level run.py loads next
// brings a new GameInfo — the last row is the level asked for
let lastGi = null;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function (a) {
        const gi = a[0].toString();
        if (gi === lastGi) return;
        try {
            const out = Memory.alloc(Process.pointerSize); staticGet(classVtable(dom, ZC), fZones, out);
            const zones = listItems(out.readPointer());
            if (zones.length === 0) return;
            const names = zones.map(nameOf);
            const nb = {};
            zones.forEach(function (z, i) { nb[names[i]] = listItems(z.add(fieldOff(fNeighbors)).readPointer()).map(nameOf); });
            lastGi = gi;
            send({ zones: names, neighbors: nb, gameinfo: gi });
        } catch (e) { send({ error: '' + e }); lastGi = gi; }
    }
});
send('armed');

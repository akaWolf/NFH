'use strict';
// a click on the original at an exact level frame, from inside the
// process: what Woody.CheckMouseClick does with a touch (Woody.cs:635-672)
// once HUD.CheckClick has let it through as a world click (HUD.cs:
// 1318-1322) — no adb tap, no camera in between, so the frame is the one
// asked for. ROWS: [{f: frames from StartGame, w: [x, y] world, t:
// InventoryType id or -1}]; StartGame is Rottweiler.CanStart turning true
// (IntroAnimation.cs:282-285), counted in GameInfo.Update calls as run.py
// counts its level frames. Each click reports {injected: {...}}.
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
const parentOf = f('mono_class_get_parent', 'pointer', ['pointer']);
const compile = f('mono_compile_method', 'pointer', ['pointer']);
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const objClass = f('mono_object_get_class', 'pointer', ['pointer']);
const isSubclassPtr = m.findExportByName('mono_class_is_subclass_of');
const isSubclass = isSubclassPtr === null ? null : new NativeFunction(isSubclassPtr, 'int', ['pointer', 'pointer', 'int']);
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const K = (img, ns, n) => classFrom(img, S(ns), S(n));
const GameInfo = K(game, '', 'GameInfo'), WoodyK = K(game, '', 'Woody'), PawnK = K(game, '', 'Pawn');
const PAC = K(game, '', 'PawnAnimationController'), DoorK = K(game, '', 'Door'), HUDK = K(game, '', 'HUD');
const InvMgrK = K(game, '', 'InventoryManager'), InvK = K(game, '', 'Inventory'), Helpers = K(game, '', 'Helpers');
const Camera = K(unity, 'UnityEngine', 'Camera'), Time = K(unity, 'UnityEngine', 'Time');
const BOX = Process.pointerSize * 2;
function offOf(k0, name) { let k = k0; while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); } return -1; }
function methOf(k0, name, n) { let k = k0; while (!k.isNull()) { const mm = methodFrom(k, S(name), n); if (!mm.isNull()) return mm; k = parentOf(k); } return NULL; }
function call(meth, self, args) {
    const arr = Memory.alloc(Process.pointerSize * Math.max(1, args.length));
    args.forEach((p, i) => arr.add(i * Process.pointerSize).writePointer(p));
    const exc = Memory.alloc(Process.pointerSize); exc.writePointer(NULL);
    const r = invoke(meth, self, arr, exc);
    if (!exc.readPointer().isNull()) throw new Error('managed exception in ' + meth);
    return r;
}
const F = {
    Woody: offOf(GameInfo, 'Woody'), Rottweiler: offOf(GameInfo, 'Rottweiler'), GameCamera: offOf(GameInfo, 'GameCamera'),
    CanStart: offOf(PawnK, 'CanStart'), InputLocked: offOf(WoodyK, 'InputLocked'), Frozen: offOf(WoodyK, 'Frozen'),
    Hiding: offOf(WoodyK, 'Hiding'), HidingItem: offOf(WoodyK, 'HidingItem'), NFH2Path: offOf(WoodyK, 'NFH2Path'),
    itemAux: offOf(WoodyK, 'itemAux'), LastInputTime: offOf(WoodyK, 'LastInputTime'), HUD: offOf(WoodyK, 'HUD'),
    InvManager: offOf(WoodyK, 'InvManager'), AnimController: offOf(PawnK, 'AnimController'),
    DonePassingToOtherZone: offOf(PawnK, 'DonePassingToOtherZone'),
    MainBackgroundRect: offOf(HUDK, 'MainBackgroundRect'), InventoryItems: offOf(InvMgrK, 'InventoryItems'),
    MouseCursor: offOf(WoodyK, 'MouseCursor'), MinMouseY: offOf(K(game, '', 'MouseCursor'), 'MinMouseY'),
    CurrentInventory: offOf(InvMgrK, '_CurrentInventory'), Type: offOf(InvK, 'Type'),
};
const M = {
    setCurrent: methOf(WoodyK, 'SetCurrentInventory', 1), setUsed: methOf(WoodyK, 'SetUsedInventory', 1),
    processMove: methOf(WoodyK, 'ProcessMoveInput', 2), store: methOf(WoodyK, 'StoreBlockedInput', 2),
    unhide: methOf(WoodyK, 'Unhide', 0), scriptCam: methOf(WoodyK, 'IsScriptCameraEnabled', 0),
    scriptCam3: methOf(WoodyK, 'IsCriptCamera3Enabled', 0), clickCanceled: methOf(PawnK, 'get_ClickCanceled', 0),
    blocking: methOf(PAC, 'IsPlayingBlockingAnimation', 0), pointInRect: methOf(Helpers, 'PointInRect', 2),
    animState: methOf(PAC, 'get_AnimState', 0),          // a property of AnimationControllerBase<T>
    camMain: methOf(Camera, 'get_main', 0), w2s: methOf(Camera, 'WorldToScreenPoint', 1),
    setFinal: methOf(K(game, '', 'CameraMover'), 'SetFinalPosition', 2),
    timeScale: methOf(Time, 'get_timeScale', 0), time: methOf(Time, 'get_time', 0),
};
send({ inject: 'offsets', F: F, missing: Object.keys(M).filter(k => M[k].isNull()) });
const ROWS = ROWS_JSON;                    // sorted by f
const RUN_UP = ANIM_RUN_UP, WALK_UP = ANIM_WALK_UP, HIDE_IN = ANIM_HIDE_IN;
let frame = 0, start = null, next = 0;
function listItems(list) {
    const k = objClass(list);
    const items = list.add(fieldOff(fieldFrom(k, S('_items')))).readPointer();
    const size = list.add(fieldOff(fieldFrom(k, S('_size')))).readS32();
    const out = [];
    for (let i = 0; i < size; i++) out.push(items.add(4 * Process.pointerSize + i * Process.pointerSize).readPointer());
    return out;
}
function boxedFloat(p) { return p.isNull() ? 0 : p.add(BOX).readFloat(); }
function boxedBool(p) { return !p.isNull() && p.add(BOX).readU8() !== 0; }
function clickAt(gi, row) {
    const woody = gi.add(F.Woody).readPointer(); if (woody.isNull()) return 'no Woody';
    // the icon click (HUD.cs:1311-1314): the port's entry in hand
    let sel = 'none';
    if (row.t >= 0) {
        const mgr = woody.add(F.InvManager).readPointer();
        const entry = listItems(mgr.add(F.InventoryItems).readPointer()).find(e => e.add(F.Type).readS32() === row.t);
        if (entry === undefined) sel = 'type ' + row.t + ' not held';
        else { const a = Memory.alloc(Process.pointerSize); a.writePointer(entry); call(M.setCurrent, woody, [a]); sel = 'selected'; }
    }
    // the player pans the camera onto what he taps (the port's runner
    // frames the item before its click): CameraMover.SetFinalPosition on
    // this frame — CameraMover.cs:178, what SnapToWoodyImmediate calls —
    // then the touch's screen point under that camera, z = 0 as a touch's
    if (!M.setFinal.isNull() && F.GameCamera >= 0) {
        const mover = gi.add(F.GameCamera).readPointer();
        if (!mover.isNull()) {
            const fx = Memory.alloc(4), fy = Memory.alloc(4); fx.writeFloat(row.w[0]); fy.writeFloat(row.w[1]);
            call(M.setFinal, mover, [fx, fy]);
        }
    }
    const cam = call(M.camMain, NULL, []); if (cam.isNull()) return 'no camera';
    const wp = Memory.alloc(12); wp.writeFloat(row.w[0]); wp.add(4).writeFloat(row.w[1]); wp.add(8).writeFloat(0);
    const sp = call(M.w2s, cam, [wp]);
    const pos = Memory.alloc(12); pos.writeFloat(sp.add(BOX).readFloat()); pos.add(4).writeFloat(sp.add(BOX + 4).readFloat()); pos.add(8).writeFloat(0);
    const btn = Memory.alloc(4); btn.writeS32(0);
    // HUD.CheckClick's world-click tail (HUD.cs:1320-1322)
    const mgr = woody.add(F.InvManager).readPointer();
    const cur = Memory.alloc(Process.pointerSize); cur.writePointer(mgr.add(F.CurrentInventory).readPointer());
    call(M.setUsed, woody, [cur]);
    const nul = Memory.alloc(Process.pointerSize); nul.writePointer(NULL);
    call(M.setCurrent, woody, [nul]);
    // CheckMouseClick's gates (Woody.cs:637): MouseOverHUD is the touch
    // below MouseCursor.MinMouseY (MouseCursor.cs:119)
    const mc = F.MouseCursor >= 0 ? woody.add(F.MouseCursor).readPointer() : NULL;
    if (!mc.isNull() && F.MinMouseY >= 0) {
        const minY = mc.add(F.MinMouseY).readS32();
        if (pos.add(4).readFloat() < minY) return sel + '; hud-strip';
    }
    if (!(boxedFloat(call(M.timeScale, NULL, [])) > 0)) return sel + '; paused';
    if (boxedBool(call(M.scriptCam, woody, [])) || boxedBool(call(M.scriptCam3, woody, []))) return sel + '; script camera';
    if (boxedBool(call(M.clickCanceled, woody, []))) return sel + '; click cancelled';
    if (woody.add(F.Frozen).readU8() !== 0) return sel + '; frozen';
    // cs:641-671
    woody.add(F.LastInputTime).writeFloat(boxedFloat(call(M.time, NULL, [])));
    const ctrl = woody.add(F.AnimController).readPointer();
    const anim = (ctrl.isNull() || M.animState.isNull()) ? -1 : call(M.animState, ctrl, []).add(BOX).readS32();
    if (woody.add(F.Hiding).readU8() !== 0 && !woody.add(F.HidingItem).readPointer().isNull()) {
        if (anim !== HIDE_IN) { call(M.unhide, woody, []); woody.add(F.InputLocked).writeU8(0); call(M.store, woody, [pos, btn]); return sel + '; unhide'; }
        return sel + '; hide-in';
    }
    if (woody.add(F.InputLocked).readU8() !== 0 || (!ctrl.isNull() && boxedBool(call(M.blocking, ctrl, [])))) { call(M.store, woody, [pos, btn]); return sel + '; stored'; }
    let r = sel;
    if (anim !== RUN_UP && anim !== WALK_UP) {
        if (woody.add(F.DonePassingToOtherZone).readU8() === 0) { call(M.processMove, woody, [pos, btn]); r += '; world'; } else r += '; passing';
    } else { woody.add(F.InputLocked).writeU8(0); r += '; on stairs'; }
    if (woody.add(F.NFH2Path).readU8() === 0 && F.itemAux >= 0) {
        const aux = woody.add(F.itemAux).readPointer();
        if (!aux.isNull() && isSubclass !== null && isSubclass(objClass(aux), DoorK, 0) !== 0) { call(M.processMove, woody, [pos, btn]); r += '; door again'; }
    }
    return r;
}
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function (a) {
        frame++;
        const gi = a[0];
        if (start === null) {
            const rott = F.Rottweiler >= 0 ? gi.add(F.Rottweiler).readPointer() : NULL;
            if (!rott.isNull() && F.CanStart >= 0 && rott.add(F.CanStart).readU8() !== 0) { start = frame; send({ inject: 'start', frame: frame }); }
            else return;
        }
        while (next < ROWS.length && start + ROWS[next].f <= frame) {
            const row = ROWS[next++];
            let result;
            try { result = clickAt(gi, row); } catch (e) { result = 'error: ' + e; }
            send({ injected: { f: row.f, want: start + row.f, at: frame, world: row.w, type: row.t, item: row.item || null, typeName: row.typeName || null, result: result } });
        }
    }
});
send('armed');

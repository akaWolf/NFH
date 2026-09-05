"""Tap an item of the running original by name — the click side of a
scripted scenario, so a `clickitem X` in the port's script has the same
meaning on the emulator.

    python3 tools/livediff/tap.py <ItemName> [--host=localhost:27042] [--adb=<ssh host>] [--dry]

Frida resolves the item's GameObject, asks the main camera for its
screen point (on the player's thread — engine calls are main-thread
only), and the tap goes through adb; Unity's screen y grows upwards,
adb's downwards, so it is flipped against Screen.height.
"""
import os, subprocess, sys, time

JS = r'''
'use strict';
const m = Process.getModuleByName('libmono.so');
const f = (n, r, a) => new NativeFunction(m.findExportByName(n), r, a);
const S = s => Memory.allocUtf8String(s);
const root = f('mono_get_root_domain', 'pointer', []);
const attach = f('mono_thread_attach', 'pointer', ['pointer']);
const imgLoaded = f('mono_image_loaded', 'pointer', ['pointer']);
const classFrom = f('mono_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']);
const methodFrom = f('mono_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);
const invoke = f('mono_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
const newStr = f('mono_string_new', 'pointer', ['pointer', 'pointer']);
const compile = f('mono_compile_method', 'pointer', ['pointer']);
// touching the runtime before Unity has started it takes the game down:
// wait for the root domain and the game's own image, as state.js does
const boot = setInterval(function () {
    if (root().isNull()) return;
    if (imgLoaded(S('Assembly-CSharp')).isNull()) return;
    clearInterval(boot);
    try { start(); } catch (e) { send({ error: '' + e }); }
}, 50);
function start() {
const dom = root(); attach(dom);
const unity = imgLoaded(S('UnityEngine')), game = imgLoaded(S('Assembly-CSharp'));
const GO = classFrom(unity, S('UnityEngine'), S('GameObject'));
const Camera = classFrom(unity, S('UnityEngine'), S('Camera'));
const Component = classFrom(unity, S('UnityEngine'), S('Component'));
const Transform = classFrom(unity, S('UnityEngine'), S('Transform'));
const Screen = classFrom(unity, S('UnityEngine'), S('Screen'));
const GameInfo = classFrom(game, S(''), S('GameInfo'));
const find = methodFrom(GO, S('Find'), 1);
// Camera.main is null in this game (no MainCamera tag): take the first
// of Camera.allCameras instead — a plain static icall returning a managed
// array (MonoArray on 32-bit: vtable, sync, bounds, length, then the
// elements at +16)
const UObject = classFrom(unity, S('UnityEngine'), S('Object'));
const allCameras = methodFrom(Camera, S('get_allCameras'), 0);
const w2s = methodFrom(Camera, S('WorldToScreenPoint'), 1);
// GameObject.Find hands back a GameObject, so its own get_transform —
// Component.get_transform on it reads a Component field that is not
// there and takes the process down (the 0x76 fault)
const getTransform = methodFrom(GO, S('get_transform'), 0);
const getPosition = methodFrom(Transform, S('get_position'), 0);
const getHeight = methodFrom(Screen, S('get_height'), 0);
// the original's camera follows touches, not pawns: an item off screen is
// unreachable by a tap, so the camera is put on the item first —
// GameInfo.Instance.GameCamera.SetFinalPosition(x, y) (CameraMover.cs:178),
// the same call SnapToWoodyImmediate makes
const fieldFrom = f('mono_class_get_field_from_name', 'pointer', ['pointer', 'pointer']);
const fieldOff = f('mono_field_get_offset', 'int', ['pointer']);
const classVtable = f('mono_class_vtable', 'pointer', ['pointer', 'pointer']);
const staticGet = f('mono_field_static_get_value', 'void', ['pointer', 'pointer', 'pointer']);
const CameraMover = classFrom(game, S(''), S('CameraMover'));
const setFinal = CameraMover.isNull() ? NULL : methodFrom(CameraMover, S('SetFinalPosition'), 2);
function frameOn(x, y) {
    const fInst = fieldFrom(GameInfo, S('Instance')); if (fInst.isNull()) return 'no Instance field';
    const out = Memory.alloc(Process.pointerSize); staticGet(classVtable(dom, GameInfo), fInst, out);
    const gi = out.readPointer(); if (gi.isNull()) return 'no GameInfo.Instance';
    const fCam = fieldFrom(GameInfo, S('GameCamera')); if (fCam.isNull()) return 'no GameCamera field';
    const cam = gi.add(fieldOff(fCam)).readPointer(); if (cam.isNull()) return 'no GameCamera';
    if (setFinal.isNull()) return 'no SetFinalPosition';
    const fx = Memory.alloc(4), fy = Memory.alloc(4); fx.writeFloat(x); fy.writeFloat(y);
    const args = Memory.alloc(Process.pointerSize * 2); args.writePointer(fx); args.add(Process.pointerSize).writePointer(fy);
    const exc = Memory.alloc(Process.pointerSize); exc.writePointer(NULL);
    invoke(setFinal, cam, args, exc);
    return exc.readPointer().isNull() ? 'framed' : 'SetFinalPosition threw';
}
[['GameObject', GO], ['Camera', Camera], ['Component', Component], ['Transform', Transform],
 ['Screen', Screen], ['GameInfo', GameInfo], ['Object', UObject]].forEach(function (kv) {
    if (kv[1].isNull()) throw new Error('class not found: ' + kv[0]);
});
[['Find', find], ['get_allCameras', allCameras], ['WorldToScreenPoint', w2s],
 ['get_transform', getTransform], ['get_position', getPosition], ['get_height', getHeight]
].forEach(function (kv) { if (kv[1].isNull()) throw new Error('method not found: ' + kv[0]); });
const BOX = Process.pointerSize * 2;
function call(meth, self, args) {
    const arr = Memory.alloc(Process.pointerSize * Math.max(1, args.length));
    args.forEach((p, i) => arr.add(i * Process.pointerSize).writePointer(p));
    const exc = Memory.alloc(Process.pointerSize); exc.writePointer(NULL);
    const r = invoke(meth, self, arr, exc);
    if (!exc.readPointer().isNull()) throw new Error('managed exception');
    return r;
}
// the inventory in hand, the way the HUD's icon click does it: the click
// on an icon calls Woody.SetCurrentInventory(entry) (HUD.cs:1311-1314,
// Woody.cs:1046: Action = UseWith) and the world click that follows
// promotes it — SetUsedInventory(CurrentInventory), SetCurrentInventory(
// null) (HUD.cs:1320-1322). A second click on the selected icon clears it
// (HUD.cs:942-958). Calling SetUsedInventory straight left Woody in a
// state the taps did not act on (Level206's Pillows, Level113's Drawer).
const parentOf = f('mono_class_get_parent', 'pointer', ['pointer']);
function offOf(k0, name) { let k = k0; while (!k.isNull()) { const fl = fieldFrom(k, S(name)); if (!fl.isNull()) return fieldOff(fl); k = parentOf(k); } return -1; }
const WoodyK = classFrom(game, S(''), S('Woody'));
const InvMgrK = classFrom(game, S(''), S('InventoryManager'));
const InvK = classFrom(game, S(''), S('Inventory'));
function selectInventory(typeId) {
    const fInst = fieldFrom(GameInfo, S('Instance')); if (fInst.isNull()) return 'no Instance';
    const out = Memory.alloc(Process.pointerSize); staticGet(classVtable(dom, GameInfo), fInst, out);
    const gi = out.readPointer(); if (gi.isNull()) return 'no GameInfo';
    const woody = gi.add(offOf(GameInfo, 'Woody')).readPointer(); if (woody.isNull()) return 'no Woody';
    const setCurrent = methodFrom(WoodyK, S('SetCurrentInventory'), 1); if (setCurrent.isNull()) return 'no SetCurrentInventory';
    const args = Memory.alloc(Process.pointerSize); const exc = Memory.alloc(Process.pointerSize); exc.writePointer(NULL);
    const mgr = woody.add(offOf(WoodyK, 'InvManager')).readPointer(); if (mgr.isNull()) return 'no InvManager';
    if (typeId < 0) {
        // nothing selected on the port's side: clear a selection left
        // over (the second icon click), else leave Woody alone
        const curOff = offOf(InvMgrK, '_CurrentInventory');
        if (curOff >= 0 && !mgr.add(curOff).readPointer().isNull()) { args.writePointer(NULL); invoke(setCurrent, woody, args, exc); return 'cleared'; }
        return 'nothing selected';
    }
    const list = mgr.add(offOf(InvMgrK, 'InventoryItems')).readPointer(); if (list.isNull()) return 'no list';
    const listK = f('mono_object_get_class', 'pointer', ['pointer'])(list);
    const items = list.add(offOf(listK, '_items')).readPointer(); const size = list.add(offOf(listK, '_size')).readS32();
    const typeOff = offOf(InvK, 'Type');
    for (let i = 0; i < size; i++) {
        // MonoArray: the object header, the bounds pointer, the length, then the data
        const inv = items.add(4 * Process.pointerSize + i * Process.pointerSize).readPointer();
        if (inv.isNull()) continue;
        if (inv.add(typeOff).readS32() === typeId) { args.writePointer(inv); invoke(setCurrent, woody, args, exc); return exc.readPointer().isNull() ? 'selected' : 'threw'; }
    }
    return 'type ' + typeId + ' not in the inventory (' + size + ' entries)';
}
let done = false;
// GameObject.GetComponent(string) — the String overload among the
// one-argument GetComponents — and the Item's IsHidden behind it
const ItemK = classFrom(game, S(''), S('Item'));
const iHidden = ItemK.isNull() ? -1 : offOf(ItemK, 'IsHidden');
const getMethods = f('mono_class_get_methods', 'pointer', ['pointer', 'pointer']);
const methName = f('mono_method_get_name', 'pointer', ['pointer']);
const methSig = f('mono_method_signature', 'pointer', ['pointer']);
const sigParams = f('mono_signature_get_params', 'pointer', ['pointer', 'pointer']);
const sigCount = f('mono_signature_get_param_count', 'uint32', ['pointer']);
const typeName = f('mono_type_get_name', 'pointer', ['pointer']);
function getComponentByString() {
    const iter = Memory.alloc(Process.pointerSize); iter.writePointer(NULL);
    while (true) {
        const m = getMethods(GO, iter); if (m.isNull()) return NULL;
        if (methName(m).readUtf8String() !== 'GetComponent') continue;
        const sig = methSig(m); if (sigCount(sig) !== 1) continue;
        const it2 = Memory.alloc(Process.pointerSize); it2.writePointer(NULL);
        const pt = sigParams(sig, it2); if (pt.isNull()) continue;
        if (typeName(pt).readUtf8String() === 'System.String') return m;
    }
}
const getCompStr = getComponentByString();
function itemHidden(go) {
    if (getCompStr.isNull() || iHidden < 0) return false;
    const it = call(getCompStr, go, [newStr(dom, S('Item'))]);
    return !it.isNull() && it.add(iHidden).readU8() !== 0;
}
let lastCam = null, still = 0;
// CameraMover's own interpolation (cs:355-365): while Interpolating, every
// Update lerps the transform back toward TargetPosition, so a framing set
// on the transform is undone the next frame — Level208's Balloons tap at
// frame 604 landed on the floor under the intro's still-running snap to
// Woody, though the camera had looked still for a hundred frames
const cmInterp = CameraMover.isNull() ? -1 : offOf(CameraMover, 'Interpolating');
function cameraInterpolating() {
    if (cmInterp < 0) return false;
    const fInst = fieldFrom(GameInfo, S('Instance')); if (fInst.isNull()) return false;
    const out = Memory.alloc(Process.pointerSize); staticGet(classVtable(dom, GameInfo), fInst, out);
    const gi = out.readPointer(); if (gi.isNull()) return false;
    const fCam = fieldFrom(GameInfo, S('GameCamera')); if (fCam.isNull()) return false;
    const cam = gi.add(fieldOff(fCam)).readPointer(); if (cam.isNull()) return false;
    return cam.add(cmInterp).readU8() !== 0;
}
// a dexterity round in progress (Woody.InDexterity, the mini-game's own
// gate in CanWoodyUse): a tap landing inside it is lost — the round's
// done-pass click (Item.cs:1462-1473) only counts once DexterityDone is up,
// so the tap waits for the round to end (dexterity.js may be playing it)
const wInDex = WoodyK.isNull() ? -1 : offOf(WoodyK, 'InDexterity');
function dexterityRunning() {
    if (wInDex < 0) return false;
    const fInst = fieldFrom(GameInfo, S('Instance')); if (fInst.isNull()) return false;
    const out = Memory.alloc(Process.pointerSize); staticGet(classVtable(dom, GameInfo), fInst, out);
    const gi = out.readPointer(); if (gi.isNull()) return false;
    const fW = fieldFrom(GameInfo, S('Woody')); if (fW.isNull()) return false;
    const w = gi.add(fieldOff(fW)).readPointer(); if (w.isNull()) return false;
    return w.add(wInDex).readU8() !== 0;
}
function woodyObj() {
    const fInst = fieldFrom(GameInfo, S('Instance')); if (fInst.isNull()) return NULL;
    const out = Memory.alloc(Process.pointerSize); staticGet(classVtable(dom, GameInfo), fInst, out);
    const gi = out.readPointer(); if (gi.isNull()) return NULL;
    const fW = fieldFrom(GameInfo, S('Woody')); if (fW.isNull()) return NULL;
    return gi.add(fieldOff(fW)).readPointer();
}
// an item tap while Woody still walks to or uses the previous tap's item
// waits for him to be free — the runner starts a leg only when the one
// before it completed, and the replay's ~70 frames of tap latency put
// Level214's Cloth click inside the bucket's use, undoing its trick on
// both sides. Busy: Woody.InputLocked (a search item's take, Woody.cs:
// 460-483 — a click then is stored and, the take not being a Blocking
// animation, never replayed: the ammo tap vanished inside the carpet's
// take on every replay), or a Blocking animation (the original's own gate,
// Woody.cs:652-656), or a Single that has not reached its last frame (a
// use, cancellable by a click: Refresh ends a single by StopSingleAnimation
// or a hold, AnimationControllerBase.cs:102-142, ReachedEndFrame
// AnimationInstance.cs:196-203) unless it is an InfiniteLoop pose;
// Woody.Hiding is free. Not the AnimState name alone: a finished single
// lingers as the state (FearRight held a tap 600 frames). The walk to an
// item is busy too — MovePath's last step an item and Woody moving, or
// climbing to it — so a parking click recorded after a leg
// does not pull Woody off the leg's walk when the original's walk runs
// longer (it did: lost in the hatch climb, Woody stood on the hatch when
// the Rottweiler came). WAIT is the caller's: an item tap and a
// parking walk wait, a dodge never does (the runner flees at once). The
// wait is bounded (600 frames) under resolve()'s timeout, and the tap's
// row reports the frames it waited and the state it waited on
const PACK = classFrom(game, S(''), S('PawnAnimationController'));
function methodUp(k0, name, argc) { let k = k0; while (!k.isNull()) { const mm = methodFrom(k, S(name), argc); if (!mm.isNull()) return mm; k = parentOf(k); } return NULL; }
const getAnimState = PACK.isNull() ? NULL : methodUp(PACK, 'get_AnimState', 0);
const wHiding = WoodyK.isNull() ? -1 : offOf(WoodyK, 'Hiding');
const wCtrl = WoodyK.isNull() ? -1 : offOf(WoodyK, 'AnimController');
const wLocked = WoodyK.isNull() ? -1 : offOf(WoodyK, 'InputLocked');
const wItemMove = WoodyK.isNull() ? -1 : offOf(WoodyK, 'ItemMove');
const wMovePath = WoodyK.isNull() ? -1 : offOf(WoodyK, 'MovePath');
const wMovingUp = WoodyK.isNull() ? -1 : offOf(WoodyK, 'MovingUp');
let PS = null;                        // Path.Steps, the List, Step.IsItem offsets
// the walk to an item: MovePath's last step is an item and Woody moves —
// the path outlives the walk and the use, so the flags on it (ItemMove,
// MoveIndex) do not tell a finished walk from one in progress; his
// position does, and the climb to a ShouldWalkUp item is MovingUp
let lastWp = null, moved = false;
function woodyMoved(w) {
    const t = call(methodFrom(Component, S('get_transform'), 0), w, []);
    const b = t.isNull() ? NULL : call(getPosition, t, []);
    if (b.isNull()) return false;
    const p = [b.add(BOX).readFloat(), b.add(BOX + 4).readFloat()];
    const m = lastWp !== null && (Math.abs(p[0] - lastWp[0]) > 1e-4 || Math.abs(p[1] - lastWp[1]) > 1e-4);
    lastWp = p;
    return m;
}
function walkingToItem(w) {
    if (wMovePath < 0) return false;
    const m = woodyMoved(w);
    if (!m && !(wMovingUp >= 0 && w.add(wMovingUp).readU8() !== 0)) return false;
    const path = w.add(wMovePath).readPointer(); if (path.isNull()) return false;
    if (PS === null) PS = { steps: offOf(classOfObj(path), 'Steps') };
    if (PS.steps < 0) return false;
    const list = path.add(PS.steps).readPointer(); if (list.isNull()) return false;
    if (PS.items === undefined) { const lk = classOfObj(list); PS.items = offOf(lk, '_items'); PS.size = offOf(lk, '_size'); }
    if (PS.items < 0 || PS.size < 0) return false;
    const size = list.add(PS.size).readS32(); if (size <= 0) return false;
    const arr = list.add(PS.items).readPointer(); if (arr.isNull()) return false;
    const last = arr.add(4 * Process.pointerSize + (size - 1) * Process.pointerSize).readPointer(); if (last.isNull()) return false;
    if (PS.isItem === undefined) PS.isItem = offOf(classOfObj(last), 'IsItem');
    return PS.isItem >= 0 && last.add(PS.isItem).readU8() !== 0;
}
const cCur = PACK.isNull() ? -1 : offOf(PACK, 'CurrentAnimation');
const classOfObj = f('mono_object_get_class', 'pointer', ['pointer']);
let AI = null;                        // AnimationInstance<AnimationState> offsets
let busyFrames = 0, lastAnim = null;
function singlePlaying(cur) {
    if (cur.isNull()) return false;
    if (AI === null) {
        const k = classOfObj(cur);
        AI = {};
        ['Type', 'InfiniteLoop', 'UsePattern', 'Pattern', 'CurrentFrameIndex', 'CurrentFrame', 'EndFrame', 'Blocking', 'HoldOnLastFrame'].forEach(n => { AI[n] = offOf(k, n); });
        if (Object.keys(AI).some(n => AI[n] < 0)) { AI = { bad: true }; }
    }
    if (AI.bad) return false;
    if (cur.add(AI.Blocking).readU8() !== 0) return true;
    if (cur.add(AI.Type).readS32() !== 0) return false;            // AnimationType.Single
    if (cur.add(AI.InfiniteLoop).readU8() !== 0) return false;
    // a single plays through its last frame too (ReachedEndFrame is one
    // step past it, AnimationInstance.cs:196-203, and Refresh then swaps
    // the next animation in the same call): free only once it is held
    // there (HoldOnLastFrame) — a tap sent on the last frame reached
    // Woody in the laugh that follows a use (Woody.cs:418) and was lost
    const hold = cur.add(AI.HoldOnLastFrame).readU8() !== 0;
    if (cur.add(AI.UsePattern).readU8() !== 0) {
        const pat = cur.add(AI.Pattern).readPointer();
        const len = pat.isNull() ? 0 : pat.add(12).readU32();
        const idx = cur.add(AI.CurrentFrameIndex).readS32();
        return hold ? idx < len - 1 : idx < len;
    }
    const fr = cur.add(AI.CurrentFrame).readS32(), end = cur.add(AI.EndFrame).readS32();
    return hold ? fr < end : fr <= end;
}
function woodyBusy() {
    if (!WAIT) return false;
    const w = woodyObj(); if (w.isNull()) return false;
    if (wHiding >= 0 && w.add(wHiding).readU8() !== 0) return false;
    if (wLocked >= 0 && w.add(wLocked).readU8() !== 0) return true;
    const ctrl = wCtrl >= 0 ? w.add(wCtrl).readPointer() : NULL;
    if (ctrl.isNull() || cCur < 0) return false;
    if (!getAnimState.isNull()) { const st = call(getAnimState, ctrl, []); if (!st.isNull()) lastAnim = st.add(BOX).readS32(); }
    if (walkingToItem(w)) return true;
    return singlePlaying(ctrl.add(cCur).readPointer());
}
function camPos() {
    const arr = call(allCameras, NULL, []);
    const count = arr.isNull() ? 0 : arr.add(12).readU32();
    const cam = count ? arr.add(16).readPointer() : NULL;
    if (cam.isNull()) return null;
    const t = call(methodFrom(Component, S('get_transform'), 0), cam, []);
    const b = t.isNull() ? NULL : call(getPosition, t, []);
    return b.isNull() ? null : [b.add(BOX).readFloat(), b.add(BOX + 4).readFloat()];
}
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function () {
        if (done) return;
        // the opening pans the camera for a couple of seconds; a point
        // computed mid-pan lands elsewhere by the time the tap arrives —
        // wait for three frames of a still camera (the wait is bounded by
        // resolve()'s timeout)
        try {
            const c = camPos();
            if (c !== null && lastCam !== null && Math.abs(c[0] - lastCam[0]) < 1e-4 && Math.abs(c[1] - lastCam[1]) < 1e-4) still++; else still = 0;
            lastCam = c;
            if (cameraInterpolating()) { still = 0; return; }
            if (dexterityRunning()) { still = 0; return; }
            if (busyFrames < 600 && woodyBusy()) { busyFrames++; still = 0; return; }
            if (still < 3) return;
        } catch (e) { send({ error: 'camera: ' + e }); return; }
        done = true;
        try {
            if (SELECT !== null) { const r = selectInventory(SELECT); send({ select: r }); }
            let pos;
            if (NAME === null) {
                // a bare world point (the driver's dodge / staging clicks)
                pos = Memory.alloc(BOX + 12); pos.add(BOX).writeFloat(0); pos.add(BOX + 4).writeFloat(0); pos.add(BOX + 8).writeFloat(0);
            } else {
                const go = call(find, NULL, [newStr(dom, S(NAME))]);
                if (go.isNull()) { send({ error: 'no GameObject ' + NAME }); return; }
                // an item hidden by a behaviour (Item.IsHidden — MugBehavior
                // hides the captain's mug and drops its collider for frames
                // 25-57 of his idle, cs:16-33) takes no click: the raycast
                // meets the zone, and with something in hand the click is
                // abandoned (Woody.ShouldAbortMove) — report it absent, so
                // run.py retries it like an item that is not there yet
                if (itemHidden(go)) { send({ error: 'hidden ' + NAME }); return; }
                const t = call(getTransform, go, []);
                pos = t.isNull() ? NULL : call(getPosition, t, []);   // boxed Vector3
                if (pos.isNull()) { send({ error: 'no transform' }); return; }
            }
            // the point to tap: the item's transform, or the collider point
            // the port clicked (WORLD) — a pivot can sit outside the box
            if (WORLD !== null) { pos.add(BOX).writeFloat(WORLD[0]); pos.add(BOX + 4).writeFloat(WORLD[1]); }
            if (STAGE === 1) { send({ world: [pos.add(BOX).readFloat(), pos.add(BOX + 4).readFloat()], x: 0, y: 0, h: 0, stage: 1 }); return; }
            const framed = frameOn(pos.add(BOX).readFloat(), pos.add(BOX + 4).readFloat());
            const arr = call(allCameras, NULL, []);
            const count = arr.isNull() ? 0 : arr.add(12).readU32();
            const cam = count ? arr.add(16).readPointer() : NULL;
            if (cam.isNull()) { send({ error: 'no Camera in the scene' }); return; }
            if (STAGE === 2) { send({ world: [pos.add(BOX).readFloat(), pos.add(BOX + 4).readFloat()], x: 0, y: 0, h: 0, stage: 2, cam: '' + cam }); return; }
            const sp = call(w2s, cam, [pos.add(BOX)]);       // Vector3 by value
            if (sp.isNull()) { send({ error: 'WorldToScreenPoint failed' }); return; }
            if (STAGE === 3) { send({ world: [pos.add(BOX).readFloat(), pos.add(BOX + 4).readFloat()], x: sp.add(BOX).readFloat(), y: sp.add(BOX + 4).readFloat(), h: 0, stage: 3 }); return; }
            const hb = call(getHeight, NULL, []);
            const h = hb.isNull() ? 0 : hb.add(BOX).readS32();
            send({ busy: busyFrames, anim: lastAnim, world: [pos.add(BOX).readFloat(), pos.add(BOX + 4).readFloat()],
                   x: sp.add(BOX).readFloat(), y: sp.add(BOX + 4).readFloat(), h: h, framed: framed });
        } catch (e) { send({ error: '' + e }); }
    }
});
}
'''


import re as _re
_ANIMS = [l.strip().rstrip(',') for l in open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'src', 'Assembly-CSharp', 'AnimationState.cs'))
          if _re.match(r'^\s*[A-Za-z0-9_]+,?\s*$', l) and l.strip() not in ('{', '}')]
def resolve(session, name, wait=15.0, select=None, world=None, busy=None):
    """the item's tap point on the running game, through an existing
    frida session: (x, y, world) in adb's top-down screen space, or None;
    `select` puts an InventoryType id in Woody's hand first (-1 clears);
    `world` = (x, y) taps that point instead of the item's transform;
    `busy` — wait for Woody to be free first (default: an item tap does)"""
    got = {}
    if busy is None:
        busy = name is not None
    sc = session.create_script(JS.replace('NAME', 'null' if name is None else repr(name)).replace('STAGE', '9')
                               .replace('WAIT', 'true' if busy else 'false')
                               .replace('SELECT', 'null' if select is None else str(int(select)))
                               .replace('WORLD', 'null' if world is None else '[%r, %r]' % (float(world[0]), float(world[1]))))
    def on_msg(m, d):
        p = m.get('payload')
        if isinstance(p, dict) and 'step' not in p:
            if 'select' in p:
                print('select:', p['select'])
            got.update(p)
    sc.on('message', on_msg)
    sc.load()
    for _ in range(int(wait / 0.05)):
        if got:
            break
        time.sleep(0.05)
    # let the hooked frame finish: the point was read after the framing
    # inside GameInfo.Update; a full second here put every tap ~70 frames
    # behind its schedule, and a chain the runner clicks back to back
    # (Level214's bucket then cloth) breaks on that much; 0.2 s still left
    # ~21 frames with adb's `input tap` (0.12 s) and the dispatch, and the
    # raid's five legs summed that into the mug's hidden window — three
    # frames cover the framing's own frame
    time.sleep(0.05)
    if 'error' in got or 'x' not in got:
        return None
    if got.get('busy'):
        print('busy: waited %d frames (anim %s)' % (got['busy'], _ANIMS[got['anim']] if got.get('anim') is not None and 0 <= got['anim'] < len(_ANIMS) else got.get('anim')))
    return int(round(got['x'])), int(round(got['h'] - got['y'])), got.get('world')


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: (a.split('=', 1)[1] if '=' in a else '1')
            for a in argv if a.startswith('--')}
    if not args:
        print(__doc__)
        return 2
    name = args[0]
    import frida
    dev = frida.get_device_manager().add_remote_device(opts.get('host', 'localhost:27042'))
    pkg = opts.get('package', os.environ.get('NFH_PKG', 'com.nordigames.nfh2'))
    app = [a for a in dev.enumerate_applications()
           if a.identifier == pkg and a.pid]
    if not app:
        print('the game is not running')
        return 2
    sess = dev.attach(app[0].pid)
    got = {}
    stage = int(opts.get('stage', 9))          # stop after engine call N (debugging)
    sc = sess.create_script(JS.replace('NAME', repr(name)).replace('STAGE', str(stage)).replace('SELECT', 'null').replace('WAIT', 'true').replace('WORLD', 'null'))
    def on_msg(m, d):
        p = m.get('payload')
        if isinstance(p, dict) and 'step' in p:
            print('  ', p)
        else:
            got.update(p or {'error': str(m)})
    sc.on('message', on_msg)
    sc.load()
    for _ in range(300):
        if got:
            break
        time.sleep(0.05)
    # no explicit unload, and a moment before exit: pulling the Update
    # hook while the player is still inside it has taken the game down
    time.sleep(1.0)
    if 'error' in got or not got:
        print('failed:', got.get('error', 'no answer'))
        return 1
    if 'stage' in got:
        print('stage %s ok: %s' % (got['stage'], got))
        return 0
    sx, sy = int(round(got['x'])), int(round(got['h'] - got['y']))
    print('%s at world (%.3f, %.3f) -> tap %d %d' % (name, got['world'][0], got['world'][1], sx, sy))
    if 'dry' in opts:                      # resolve only, no tap
        return 0
    em = os.environ.get('NFH_EM')
    adb = ['ssh', '-o', 'BatchMode=yes', opts['adb'],
           '%s tap %d %d' % (em or 'bash /tmp/emulator.sh', sx, sy)] \
        if 'adb' in opts else ['bash', '-c', '%s tap %d %d' % (em, sx, sy)] if em \
        else ['adb', 'shell', 'input', 'tap', str(sx), str(sy)]
    subprocess.run(adb, check=False, timeout=60)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

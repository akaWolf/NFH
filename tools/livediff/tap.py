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
// the inventory in hand: Woody.SetUsedInventory(Inventory) (Woody.cs:1062)
// with the InventoryManager's entry of the wanted InventoryType — what the
// HUD's icon click does, for a `usewith` replayed on the original
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
    const setUsed = methodFrom(WoodyK, S('SetUsedInventory'), 1); if (setUsed.isNull()) return 'no SetUsedInventory';
    const args = Memory.alloc(Process.pointerSize); const exc = Memory.alloc(Process.pointerSize); exc.writePointer(NULL);
    if (typeId < 0) { args.writePointer(NULL); invoke(setUsed, woody, args, exc); return 'cleared'; }
    const mgr = woody.add(offOf(WoodyK, 'InvManager')).readPointer(); if (mgr.isNull()) return 'no InvManager';
    const list = mgr.add(offOf(InvMgrK, 'InventoryItems')).readPointer(); if (list.isNull()) return 'no list';
    const listK = f('mono_object_get_class', 'pointer', ['pointer'])(list);
    const items = list.add(offOf(listK, '_items')).readPointer(); const size = list.add(offOf(listK, '_size')).readS32();
    const typeOff = offOf(InvK, 'Type');
    for (let i = 0; i < size; i++) {
        // MonoArray: the object header, the bounds pointer, the length, then the data
        const inv = items.add(4 * Process.pointerSize + i * Process.pointerSize).readPointer();
        if (inv.isNull()) continue;
        if (inv.add(typeOff).readS32() === typeId) { args.writePointer(inv); invoke(setUsed, woody, args, exc); return exc.readPointer().isNull() ? 'selected' : 'threw'; }
    }
    return 'type ' + typeId + ' not in the inventory (' + size + ' entries)';
}
let done = false;
Interceptor.attach(compile(methodFrom(GameInfo, S('Update'), 0)), {
    onEnter: function () {
        if (done) return; done = true;
        try {
            if (SELECT !== null) { const r = selectInventory(SELECT); send({ select: r }); }
            const go = call(find, NULL, [newStr(dom, S(NAME))]);
            if (go.isNull()) { send({ error: 'no GameObject ' + NAME }); return; }
            const t = call(getTransform, go, []);
            const pos = t.isNull() ? NULL : call(getPosition, t, []);   // boxed Vector3
            if (pos.isNull()) { send({ error: 'no transform' }); return; }
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
            send({ world: [pos.add(BOX).readFloat(), pos.add(BOX + 4).readFloat()],
                   x: sp.add(BOX).readFloat(), y: sp.add(BOX + 4).readFloat(), h: h, framed: framed });
        } catch (e) { send({ error: '' + e }); }
    }
});
}
'''


def resolve(session, name, wait=15.0, select=None, world=None):
    """the item's tap point on the running game, through an existing
    frida session: (x, y, world) in adb's top-down screen space, or None;
    `select` puts an InventoryType id in Woody's hand first (-1 clears);
    `world` = (x, y) taps that point instead of the item's transform"""
    got = {}
    sc = session.create_script(JS.replace('NAME', repr(name)).replace('STAGE', '9')
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
    time.sleep(1.0)                        # let the hooked frame finish
    if 'error' in got or 'x' not in got:
        return None
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
    sc = sess.create_script(JS.replace('NAME', repr(name)).replace('STAGE', str(stage)).replace('SELECT', 'null').replace('WORLD', 'null'))
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

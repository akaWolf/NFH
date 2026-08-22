#!/usr/bin/env bash
# The reference machine for track A: the ORIGINAL game running on
# Android-x86 under QEMU, driven headlessly.
#
# Why this shape:
# - the apk ships lib/x86 (libunity.so + libmono.so), so an x86_64 host
#   runs the game natively — no ARM translation anywhere;
# - it is Mono, not IL2CPP, so Frida reaches Assembly-CSharp's methods
#   by name (tools/livediff/probe.js);
# - QEMU rather than Waydroid: no root, no kernel modules, no Wayland
#   compositor, and qcow2 snapshots reset the device between runs.
#
# Everything the guest needs is set from the outside: the initrd is
# repacked with the properties that switch off the setup wizard and adb
# authorisation, and the network is configured over the serial console
# (Android-x86 renames the NIC to wifi_eth and parks a carrier-less
# wlan0 shim on top; its netd routing tables ignore the main table, so
# both the address and a `lookup main` rule have to be placed by hand).
#
#   vm.sh prepare   # unpack the ISO, patch the initrd, install to qcow2
#   vm.sh boot      # start the VM, fix networking, connect adb
#   vm.sh sh 'cmd'  # run a command on the serial root console
#   vm.sh stop
set -e

DIR=${NFH_VM_DIR:-/tmp/nfh-a}
# Android-x86 7.1, 32-bit: the game is Unity 5.3.4f1 (2016) and its
# player refuses to start on 9.0 — see README.md
ISO_URL=${NFH_ISO_URL:-https://mirrors.gigenet.com/OSDN/android-x86/67834/android-x86-7.1-r5.iso}
SRC_DIR=${NFH_SRC_DIR:-/android-7.1-r5}   # what the installer writes to the disk
ADB_PORT=${NFH_ADB_PORT:-6666}   # not 5555: adb mistakes it for an emulator
QEMU="nix-shell -p qemu --run"

cd "$DIR" 2>/dev/null || { mkdir -p "$DIR"; cd "$DIR"; }

serial() {   # run a command on Android's root console (no adb needed)
    python3 - "$1" <<'PY'
import socket, sys, time
s = socket.socket(socket.AF_UNIX); s.connect('mon.sock'.replace('mon', 'ser'))
s.settimeout(0.5); s.sendall(b'\n'); time.sleep(0.3)
s.sendall(sys.argv[1].encode() + b'\n')
end, buf = time.time() + 8, b''
while time.time() < end:
    try:
        b = s.recv(65536)
        if not b: break
        buf += b
    except socket.timeout:
        pass
sys.stdout.write(buf.decode('utf-8', 'replace'))
PY
}

case "${1:-}" in
prepare)
    [ -f android.iso ] || curl -L -o android.iso "$ISO_URL"
    $QEMU "qemu-img create -f qcow2 android.qcow2 6G" >/dev/null
    nix-shell -p p7zip --run "7z x -y android.iso kernel initrd.img" >/dev/null
    # the properties the harness needs, appended where the stock init
    # already appends ro.setupwizard.mode (initrd:init)
    rm -rf ird && mkdir ird && (cd ird && zcat ../initrd.img | cpio -idm 2>/dev/null)
    python3 - <<'PY'
p = 'ird/init'
s = open(p).read()
a = '[ "$SETUPWIZARD" = "0" ] && echo "ro.setupwizard.mode=DISABLED" >> default.prop\n'
assert s.count(a) == 1 and 'NFH-HARNESS' not in s
open(p, 'w').write(s.replace(a, a + '''
# NFH-HARNESS: no adb key prompt, root adbd, adbd on TCP
echo "ro.adb.secure=0" >> default.prop
echo "ro.secure=0" >> default.prop
echo "ro.debuggable=1" >> default.prop
echo "service.adb.tcp.port=5555" >> default.prop
# the VM is given a virtio GPU below, so Android finds a DRM device and
# loads mesa; without one it falls back to a GLES 1.x stub that no Unity
# player accepts (SwiftShader would be the software answer:
# ro.hardware.egl=swiftshader)
'''))
PY
    (cd ird && find . | cpio -o -H newc -R 0:0 --quiet | gzip -9 > ../initrd-nfh.img)
    # AUTO_INSTALL=force answers every installer dialog (install.img:
    # scripts/1-install), so the install needs no console at all
    $QEMU "qemu-system-x86_64 -enable-kvm -m 3072 -smp 4 \
        -kernel kernel -initrd initrd.img \
        -append 'root=/dev/ram0 INSTALL=1 AUTO_INSTALL=force console=ttyS0 DEBUG=' \
        -drive file=android.qcow2,format=qcow2,index=0,media=disk \
        -drive file=android.iso,index=1,media=cdrom,readonly=on \
        -display none -serial file:$DIR/install.log \
        -monitor unix:$DIR/mon.sock,server,nowait -no-reboot" || true
    grep -q "installed successfully" install.log && echo "prepared"
    ;;
boot)
    pkill -f 'qemu-system-x86_64.*android.qcow2' 2>/dev/null || true
    sleep 1; rm -f mon.sock ser.sock
    $QEMU "qemu-system-x86_64 -enable-kvm -m 3072 -smp 4 \
        -kernel kernel -initrd initrd-nfh.img \
        -append 'root=/dev/ram0 SETUPWIZARD=0 SRC=$SRC_DIR console=ttyS0 nomodeset' \
        -drive file=android.qcow2,format=qcow2,index=0,media=disk \
        -netdev user,id=n0,hostfwd=tcp::$ADB_PORT-:5555,hostfwd=tcp::27042-:27042 \
        -device e1000,netdev=n0 \
        -device usb-ehci,id=ehci -device usb-tablet,bus=ehci.0 \
        -device virtio-vga-gl -display egl-headless,rendernode=/dev/dri/renderD128 \
        -vnc 127.0.0.1:1 \
        -serial unix:$DIR/ser.sock,server,nowait \
        -monitor unix:$DIR/mon.sock,server,nowait" &
    for i in $(seq 1 60); do sleep 5; serial 'echo READY' 2>/dev/null | grep -q READY && break; done
    # the address belongs on the real NIC, not the carrier-less shim,
    # and netd's rules never consult the main table on their own
    serial "ip addr add 10.0.2.15/24 dev wifi_eth
            ip route add 10.0.2.0/24 dev wifi_eth src 10.0.2.15
            ip route add default via 10.0.2.2 dev wifi_eth
            ip rule add from all lookup main pref 20000
            setprop service.adb.tcp.port 5555; stop adbd; start adbd" >/dev/null
    sleep 3
    adb connect localhost:$ADB_PORT
    # a sleeping screen pauses Unity outright — the process then idles
    # at 0% CPU and nothing in the log says why
    adb -s localhost:$ADB_PORT shell svc power stayon true
    adb -s localhost:$ADB_PORT shell input keyevent KEYCODE_WAKEUP
    ;;
game)
    # the launcher activity is HandyGames' wrapper, not UnityPlayerActivity
    adb -s localhost:$ADB_PORT shell am start -n \
        com.nordigames.nfh2/com.hg.android.cocos2dx.Application
    ;;
shot)   # Android's own screencap: the QEMU monitor's screendump comes
        # back empty once rendering goes through the virtio GPU
    adb -s localhost:$ADB_PORT exec-out screencap -p > shot.png
    echo "$DIR/shot.png"
    ;;
sh)  serial "$2" ;;
stop) pkill -f 'qemu-system-x86_64.*android.qcow2' || true ;;
*)   sed -n '2,30p' "$0" ;;
esac

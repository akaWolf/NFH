#!/usr/bin/env bash
# The reference machine, take two: the AOSP emulator.
#
# Android-x86 under plain QEMU could not give an app process a graphics
# buffer (see README.md), and the game's player died at surface
# creation. The emulator's goldfish gralloc is built for exactly this,
# and with it the original runs: Unity initialises, the title card
# comes up, and Frida reads GameInfo out of the live process.
#
#   emulator.sh sdk      # fetch Google's SDK + API 25 x86 image into $DIR
#   emulator.sh patch    # make the prebuilts runnable on NixOS
#   emulator.sh avd      # create the AVD
#   emulator.sh boot     # start it headless, then `wait`
#   emulator.sh game     # install the apk + obb, grant storage
#   emulator.sh frida    # push and start frida-server, forward 27042
#
# API 25 (7.1) x86: the game is Unity 5.3.4f1 from 2016 and its player
# refuses to start on API 28 at all; x86 is the only ABI in the apk that
# runs natively on an x86_64 host.
set -e
DIR=${NFH_AOSP_DIR:-/tmp/nfh-aosp}
R=$DIR/sdk
GAME=${NFH_GAME_DIR:-/tmp/nfh-keep/game}
CMDLINE_URL=https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
export ANDROID_SDK_ROOT=$R ANDROID_HOME=$R
export ANDROID_AVD_HOME=$DIR/avd ANDROID_EMULATOR_HOME=$DIR
ADB=$R/platform-tools/adb
mkdir -p "$DIR" "$ANDROID_AVD_HOME"
[ -f $DIR/libs.path ] && export LD_LIBRARY_PATH=$(cat $DIR/libs.path)

resumed() {   # the resumed Activity, e.g. com.nordigames.nfh2/com.hg.framework.MoreGamesActivity
    $ADB shell "dumpsys activity activities" | grep mResumedActivity | head -1 \
        | sed 's/.*u0 //; s/ t[0-9]*}.*//' | tr -d '\r'
}
past_promo() {
    # the cross-promotion is the game's own MoreGamesActivity, up within
    # ten seconds of launch (sampled: tools/livediff/README.md); BACK
    # closes it and the game's Activity resumes
    for i in $(seq 1 30); do
        sleep 3
        case "$(resumed)" in
        *MoreGamesActivity*) $ADB shell input keyevent 4; sleep 3 ;;
        *cocos2dx.Application*) [ $i -gt 3 ] && return 0 ;;
        esac
    done
    echo "the game's Activity never came back" >&2
}

case "${1:-}" in
sdk)
    cd $DIR
    [ -f cmdline.zip ] || curl -sL -o cmdline.zip "$CMDLINE_URL"
    [ -d $R/cmdline-tools/latest ] || {
        nix-shell -p unzip --run "unzip -q -o cmdline.zip -d $R/cmdline-tools"
        mv $R/cmdline-tools/cmdline-tools $R/cmdline-tools/latest
    }
    nix-shell -p jdk17 --run "
        yes | $R/cmdline-tools/latest/bin/sdkmanager --sdk_root=$R --licenses >/dev/null 2>&1 || true
        $R/cmdline-tools/latest/bin/sdkmanager --sdk_root=$R \
            platform-tools emulator 'system-images;android-25;default;x86'"
    ;;
patch)
    # NixOS has no FHS loader, nix-ld is not always enabled, and
    # steam-run's sandbox hides the SDK's own directory — so the
    # prebuilts get their interpreter and rpath rewritten in place
    LIBS=$(nix eval --raw --impure --expr 'with import <nixpkgs> {}; lib.makeLibraryPath [
      glibc stdenv.cc.cc zlib libGL libdrm libpng glib pixman SDL2 libusb1 alsa-lib
      libbsd libcap libcap_ng lzo snappy curl gnutls nettle libgpg-error libgcrypt
      xorg.libX11 xorg.libXext xorg.libXrandr xorg.libXi xorg.libXcursor xorg.libxcb
      xorg.libXfixes xorg.libXau xorg.libXdmcp libpulseaudio ncurses fontconfig
      freetype nss nspr expat libxkbcommon libuuid libepoxy libGLU vulkan-loader
      wayland libffi pcre2 util-linux xorg.libxkbfile xorg.libXtst
      xorg.libXcomposite xorg.libXdamage xorg.libXrender xorg.libSM xorg.libICE
      xorg.libXinerama xorg.libxshmfence xorg.xcbutil xorg.xcbutilimage
      xorg.xcbutilkeysyms xorg.xcbutilrenderutil xorg.xcbutilwm dbus at-spi2-core
      cups libxslt libxml2 mesa harfbuzz icu libwebp libevent jsoncpp libvpx
      nss nspr systemd ]')
    echo "$LIBS" > $DIR/libs.path
    LD=$(nix eval --raw --impure --expr 'with import <nixpkgs> {}; "${glibc}/lib/ld-linux-x86-64.so.2"')
    RPATH="$LIBS:$R/emulator/lib64:$R/emulator/lib64/qt/lib:$R/emulator/lib64/gles_swiftshader:$R/emulator/lib64/vulkan:$R/emulator/lib64/libstdc++"
    nix-shell -p patchelf --run "
      for b in \$(find $R/emulator $R/platform-tools -maxdepth 3 -type f -perm -u+x); do
          head -c 4 \$b | grep -q ELF || continue
          patchelf --print-interpreter \$b >/dev/null 2>&1 || continue
          patchelf --set-interpreter '$LD' --set-rpath '$RPATH' \$b 2>/dev/null || true
      done
      true"
    LD_LIBRARY_PATH=$LIBS $R/emulator/emulator -version | head -1
    ;;
avd)
    nix-shell -p jdk17 --run "echo no | $R/cmdline-tools/latest/bin/avdmanager \
        create avd -n nfh -k 'system-images;android-25;default;x86' --force" | tail -1
    ;;
boot)
    setsid $R/emulator/emulator -avd nfh -no-window -no-audio -no-boot-anim \
        -no-metrics -no-snapshot -gpu swiftshader_indirect \
        -memory 2048 -partition-size 2048 -writable-system \
        > $DIR/emulator.log 2>&1 &
    echo started
    ;;
wait)
    $ADB wait-for-device
    until [ "$($ADB shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; do sleep 5; done
    echo "booted $($ADB shell getprop ro.build.version.release | tr -d '\r') abi=$($ADB shell getprop ro.product.cpu.abi | tr -d '\r')"
    ;;
game)
    $ADB install -r $GAME/com.nordigames.nfh2.apk | tail -1
    $ADB shell mkdir -p /sdcard/Android/obb/com.nordigames.nfh2
    $ADB push $GAME/main.14.com.nordigames.nfh2.obb /sdcard/Android/obb/com.nordigames.nfh2/ | tail -1
    for p in READ_EXTERNAL_STORAGE WRITE_EXTERNAL_STORAGE; do
        $ADB shell pm grant com.nordigames.nfh2 android.permission.$p
    done
    $ADB shell svc power stayon true
    ;;
frida)
    $ADB push ${NFH_FRIDA:-/tmp/nfh-keep/fs-x86} /data/local/tmp/frida-server | tail -1
    $ADB shell chmod 755 /data/local/tmp/frida-server
    $ADB root >/dev/null 2>&1 || true; sleep 3
    $ADB shell "setsid /data/local/tmp/frida-server -D" >/dev/null 2>&1 &
    sleep 3
    $ADB forward tcp:27042 tcp:27042
    echo "frida on 27042"
    ;;
play) $ADB shell am start -n com.nordigames.nfh2/com.hg.android.cocos2dx.Application ;;
level)
    # from a cold start to standing in Level201: the cross-promo screen,
    # the title card, the menu and the episode map, at 320x640
    # a stray tap into the cross-promotion opens the store link in the
    # WebView shell, a separate app that then stays on top of every
    # later launch — put it down first
    $ADB shell am force-stop org.chromium.webview_shell
    $ADB shell am force-stop com.nordigames.nfh2; sleep 2
    $ADB shell am start -n com.nordigames.nfh2/com.hg.android.cocos2dx.Application >/dev/null
    past_promo                                     # "play more games"
    sleep 8;  $ADB shell input tap 320 160         # touch to continue
    sleep 10; $ADB shell input tap 320 149         # START GAME
    sleep 12; $ADB shell input tap 600 305         # the episode's play button
    sleep 25; echo "in level"
    ;;
menu)
    # the same walk, stopping on the episode map: attach the recorder
    # here, then `tap 600 305` starts the level with its first frame
    # already hooked
    # a stray tap into the cross-promotion opens the store link in the
    # WebView shell, a separate app that then stays on top of every
    # later launch — put it down first
    $ADB shell am force-stop org.chromium.webview_shell
    $ADB shell am force-stop com.nordigames.nfh2; sleep 2
    $ADB shell am start -n com.nordigames.nfh2/com.hg.android.cocos2dx.Application >/dev/null
    past_promo
    sleep 8;  $ADB shell input tap 320 160
    sleep 10; $ADB shell input tap 320 149
    sleep 12; echo "on the episode map"
    ;;
purchased)
    # mirror the owner's own purchase onto the test bench: the level packs
    # are recorded as a PlayerPrefs key (LevelUnlocker.cs:65-86,
    # Purchaser.GetPurchasePackName), and this install has no store
    # account to restore it from. Only for a copy whose packs were bought.
    P=/data/data/com.nordigames.nfh2/shared_prefs/com.nordigames.nfh2.v2.playerprefs.xml
    $ADB root >/dev/null 2>&1; sleep 1
    $ADB shell am force-stop com.nordigames.nfh2
    $ADB pull $P $DIR/prefs.xml >/dev/null
    python3 - "$DIR/prefs.xml" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
key = 'nfh.02pack_levels'
if re.search(r'name="%s"' % re.escape(key), s):
    s = re.sub(r'(<int name="%s" value=")0(" />)' % re.escape(key), r'\g<1>1\2', s)
else:
    s = s.replace('</map>', '    <int name="%s" value="1" />\n</map>' % key)
open(p, 'w').write(s)
PY
    $ADB push $DIR/prefs.xml $P >/dev/null
    $ADB shell "chown u0_a63:u0_a63 $P; chmod 660 $P; restorecon $P; grep 02pack $P"
    ;;
tap)  $ADB shell input tap "$2" "$3" ;;
shot) $ADB exec-out screencap -p > $DIR/shot.png; echo $DIR/shot.png ;;
adb)  shift; $ADB "$@" ;;
*)    sed -n '2,20p' "$0" ;;
esac

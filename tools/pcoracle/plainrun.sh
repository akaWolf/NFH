#!/bin/sh
# usage: plainrun.sh nfh1|nfh2 <seconds> [WINEDEBUG]  — run game.exe under Wine on Xvfb :97 for N seconds,
# screenshot to ~/nfh-bench/wine/logs/<game>_plain.png, stderr to <game>_plain.log; hard cleanup
G=$1; SECS=${2:-25}; DBG=${3:--all}
W=/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0/bin
T=$(dirname "$(readlink -f "$0")")
export WINEPREFIX=$HOME/nfh-bench/wine/nfh WINEDLLOVERRIDES="mscoree,mshtml=" DISPLAY=:97 WINEDEBUG=$DBG
L=$HOME/nfh-bench/wine/logs
Xvfb :97 -screen 0 1024x768x24 +extension GLX >/dev/null 2>&1 & XP=$!
sleep 1.5
WINEDEBUG=-all $W/wineserver -p
cd $HOME/nfh-bench/wine/${G}game/bin
$W/wine ${DESKTOP:+explorer /desktop=nfh,1024x768} game.exe > $L/${G}_plain.log 2>&1 & GP=$!
sleep $SECS
echo "alive: $(pgrep -f "game.exe" | wc -l) game.exe processes after $SECS s"
$T/xwininfo-result/bin/xwininfo -root -tree -display :97 > $L/${G}_plain.windows 2>&1
$T/xwd-result/bin/xwd -root -silent -display :97 -out $L/${G}_plain.xwd
kill -9 $GP 2>/dev/null
WINEDEBUG=-all $W/wineserver -k9 2>/dev/null; sleep 1
pkill -9 -f "wine-preloader|wine64-preloader" 2>/dev/null
kill -9 $XP 2>/dev/null
cd ~/projects/own/NFH && nix-shell --run "python3 tools/pcoracle/xwd2png.py $L/${G}_plain.xwd $L/${G}_plain.png" >/dev/null 2>&1
echo "log: $(wc -l < $L/${G}_plain.log) lines; png: $(ls -la $L/${G}_plain.png | cut -d' ' -f5) bytes"

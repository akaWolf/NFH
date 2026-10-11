#!/bin/sh
# usage: menuwalk.sh nfh1|nfh2 "<x y wait> ..." — run the game windowed on Xvfb :97, click the given window-relative
# points (xdotool) with waits, screenshot after each click into ~/nfh-bench/wine/logs/<game>_menu_<i>.png
G=$1; CLICKS=$2
W=/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0/bin
T=$(dirname "$(readlink -f "$0")")
export WINEPREFIX=$HOME/nfh-bench/wine/nfh WINEDLLOVERRIDES="mscoree,mshtml=" DISPLAY=:97 WINEDEBUG=-all
L=$HOME/nfh-bench/wine/logs
Xvfb :97 -screen 0 1024x768x24 +extension GLX >/dev/null 2>&1 & XP=$!
sleep 1.5
$W/wineserver -p
cd $HOME/nfh-bench/wine/${G}game/bin
$W/wine game.exe > $L/${G}_menu.log 2>&1 & GP=$!
sleep ${START:-20}
WID=$($T/xdotool-result/bin/xdotool search --name "Neighbours From Hell" | head -1)
OX=$($T/xwininfo-result/bin/xwininfo -id $WID | awk '/Absolute upper-left X/ {print $NF}')
OY=$($T/xwininfo-result/bin/xwininfo -id $WID | awk '/Absolute upper-left Y/ {print $NF}')
echo "window $WID at +$OX+$OY"
i=0
set -- $CLICKS
while [ $# -ge 3 ]; do
  i=$((i+1))
  if [ "$1" = key ]; then
    echo "key $2"
    $T/xdotool-result/bin/xdotool key --window $WID $2
  else
    PX=$(( ( $1 + 30 ) * 4 / 3 + OX )); PY=$((OY+$2))
    echo "click game($1,$2) -> X($PX,$PY)"
    $T/xdotool-result/bin/xdotool mousemove $PX $PY sleep 0.3 click 1
  fi
  sleep $3
  $T/xwd-result/bin/xwd -root -silent -display :97 -out $L/${G}_menu_$i.xwd
  shift 3
done
kill -9 $GP 2>/dev/null; $W/wineserver -k9 2>/dev/null; sleep 1
pkill -9 -f "wine-preloader|wine64-preloader" 2>/dev/null; kill -9 $XP 2>/dev/null
cd ~/projects/own/NFH && for f in $L/${G}_menu_*.xwd; do nix-shell --run "python3 tools/pcoracle/xwd2png.py $f ${f%.xwd}.png" >/dev/null 2>&1; done
echo "shots: $(ls $L/${G}_menu_*.png | wc -l)"

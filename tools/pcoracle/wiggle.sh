#!/bin/sh
# wiggle.sh <start delay s> <seconds> — move the mouse up and down fast on :97 (a PC minigame's thumb)
T=$(dirname "$(readlink -f "$0")"); X=$T/xdotool-result/bin/xdotool; export DISPLAY=:97
sleep $1; end=$(( $(date +%s) + $2 )); i=0
while [ $(date +%s) -lt $end ]; do
  $X mousemove 400 200 sleep 0.05 mousemove 400 420 sleep 0.05
  i=$((i+1)); if [ $((i % 20)) -eq 0 ]; then $T/xwd-result/bin/xwd -root -silent -display :97 -out $HOME/nfh-bench/wine/logs/wiggle_$i.xwd; fi
done
echo "wiggled $i"

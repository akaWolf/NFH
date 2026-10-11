#!/bin/sh
# clicks.sh nfh2 "<gx gy wait> | key <name> <wait> ..." — the menuwalk click loop against a running game window
G=$1; CLICKS=$2; T=$(dirname "$(readlink -f "$0")"); L=$HOME/nfh-bench/wine/logs
X=$T/xdotool-result/bin/xdotool
sleep ${START:-18}
WID=$($X search --name "[Nn]eighbou*rs [Ff]rom [Hh]ell" | head -1)
OX=$($T/xwininfo-result/bin/xwininfo -id $WID | awk '/Absolute upper-left X/ {print $NF}')
OY=$($T/xwininfo-result/bin/xwininfo -id $WID | awk '/Absolute upper-left Y/ {print $NF}')
echo "window $WID at +$OX+$OY"
i=0; set -- $CLICKS
while [ $# -ge 3 ]; do
  i=$((i+1))
  if [ "$1" = sync ]; then
    n=0; while [ ! -f $L/level_started ] && [ $n -lt 300 ]; do sleep 0.2; n=$((n+1)); done
    echo "$(date +%s.%N) synced to the level start ($(cat $L/level_started 2>/dev/null))"
  elif [ "$1" = key ]; then echo "$(date +%s.%N) key $2"; $X key --window $WID $2
  elif [ "$1" = move ]; then echo "$(date +%s.%N) move $2"; $X mousemove $(echo $2 | tr , " ")
  elif [ "$1" = focus ]; then echo "$(date +%s.%N) focus"; $X windowactivate --sync $WID; $X windowfocus --sync $WID
  elif [ -z "$WINDOWED" ]; then PX=$((OX+$1)); PY=$((OY+$2)); echo "$(date +%s.%N) click game($1,$2) -> X($PX,$PY)"; $X mousemove $PX $PY sleep 0.3 mousedown 1 sleep 0.2 mouseup 1
  else PX=$(( ( $1 + 30 ) * 4 / 3 + OX )); PY=$((OY+$2)); echo "$(date +%s.%N) click game($1,$2) -> X($PX,$PY)"; $X mousemove $PX $PY sleep 0.3 mousedown 1 sleep 0.2 mouseup 1; fi
  sleep $3
  $T/xwd-result/bin/xwd -root -silent -display :97 -out $L/${G}_clicks_$i.xwd
  shift 3
done
echo done

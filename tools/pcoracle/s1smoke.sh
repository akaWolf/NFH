#!/bin/sh
# usage: s1smoke.sh <level folder> <secs> [clicks]  — NFH1 under the harness with s1_smoke.py
cd "$(dirname "$(readlink -f "$0")")"
L=$1; SECS=$2; CLICKS=${3:-"414 313 4  65 116 3  750 555 1"}
W=/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0
LOGS=$HOME/nfh-bench/wine/logs
export WDBG_LEVEL=$L WDBG_SECS=$SECS WDBG_CLICKS="$CLICKS"
export WDBG_CMD="$W/bin/winedbg --gdb --no-start --port 33333 Z:\\home\\akawolf\\nfh-bench\\wine\\nfh1game\\bin\\game.exe"
timeout $((SECS + 150)) python3 wdbg.py nfh1 $PWD/s1_smoke.py $((SECS + 90)) > $LOGS/s1smoke_$L.log 2>&1
grep -a "hit\|patched\|tick [0-9]*: rets\|WATCHDOG\|^done\|err\|rc=" $LOGS/s1smoke_$L.log | cut -c1-300 | head -40
echo "window: $(grep -a window $LOGS/clicks.log | head -2)"

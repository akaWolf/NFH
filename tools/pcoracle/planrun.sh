#!/bin/sh
# usage: planrun.sh <level number> <level name> <secs> <tag>  — the port's PC plan on the oracle
cd "$(dirname "$(readlink -f "$0")")"
N=$1; L=$2; SECS=$3; TAG=$4
W=/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0
LOGS=${WDBG_LOGS:-$HOME/nfh-bench/wine/logs}
S=s2; [ "$N" -lt 200 ] && S=s1
export WDBG_PLAN=${WDBG_PLAN:-$HOME/projects/own/NFH/tests/plans/pc/$S/Level$N.txt} WDBG_LEVELNUM=$N WDBG_LEVEL=$L WDBG_SECS=$SECS
export WDBG_CLICKS="300 300 4  283 314 4  745 550 1"
export WDBG_CMD="$W/bin/winedbg --gdb --no-start --port ${WDBG_PORT:-33333} Z:\\home\\akawolf\\nfh-bench\\wine\\nfh2game\\bin\\game.exe"
timeout $((SECS + 180)) python3 wdbg.py nfh2 $PWD/oracle.py $((SECS + 100)) > $LOGS/oracle${N}_$TAG.log 2>&1
grep "LEG\|INJECTED\|MINIGAME\|WATCHDOG\|^done\|^plan\|err" $LOGS/oracle${N}_$TAG.log | cut -c1-120
cp $LOGS/oracle_$L.jsonl $LOGS/oracle_${L}_$TAG.jsonl
D=$(ls -d $HOME/nfh-bench/wine/nfh/drive_c/users/*/Documents/JoWooD/NFH2 | head -1)
cp "$(ls -t "$D"/GameLogicLog*.xml | head -1)" $LOGS/gamelog_${L}_$TAG.xml
echo copied

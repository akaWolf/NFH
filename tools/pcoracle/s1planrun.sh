#!/bin/sh
# usage: s1planrun.sh <level number> <level folder> <secs> <tag>  — the port's Season 1 plan on NFH1's oracle
cd "$(dirname "$(readlink -f "$0")")"
N=$1; L=$2; SECS=$3; TAG=$4
W=/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0
LOGS=${WDBG_LOGS:-$HOME/nfh-bench/wine/logs}
export WDBG_PLAN=${WDBG_PLAN:-$HOME/projects/own/NFH/tests/plans/pc/s1/Level$N.txt} WDBG_LEVELNUM=$N WDBG_LEVEL=$L WDBG_SECS=$SECS
export WDBG_CLICKS="400 300 4  414 313 4  65 116 3  750 555 1"
export WDBG_DUMMY=${WDBG_DUMMY:-"300 480"}
export WDBG_CMD="$W/bin/winedbg --gdb --no-start --port ${WDBG_PORT:-33333} Z:\\home\\akawolf\\nfh-bench\\wine\\nfh1game\\bin\\game.exe"
timeout $((SECS + 300)) python3 wdbg.py nfh1 $PWD/s1_oracle.py $((SECS + 240)) > $LOGS/oracle${N}_$TAG.log 2>&1
grep "LEG\|INJECTED\|WATCHDOG\|CAUGHT\|^done\|^plan\|err" $LOGS/oracle${N}_$TAG.log | cut -c1-120
cp $LOGS/oracle_$L.jsonl $LOGS/oracle_${L}_$TAG.jsonl
D=$(ls -d ${WDBG_PREFIX:-$HOME/nfh-bench/wine/nfh}/drive_c/users/*/Documents/JoWooD/NFH1 | head -1)
cp "$(ls -t "$D"/GameLogicLog*.xml | head -1)" $LOGS/gamelog_${L}_$TAG.xml
echo copied

#!/bin/sh
# usage: s1planrun.sh <level number> <level folder> <secs> <tag>  — the port's Season 1 plan on NFH1's oracle
cd "$(dirname "$(readlink -f "$0")")"
N=$1; L=$2; SECS=$3; TAG=$4
W=/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0
LOGS=${WDBG_LOGS:-$HOME/nfh-bench/wine/logs}
export WDBG_PLAN=${WDBG_PLAN:-$HOME/projects/own/NFH/tests/plans/pc/s1/Level$N.txt} WDBG_LEVELNUM=$N WDBG_LEVEL=$L WDBG_SECS=$SECS
# the menu walk: the title, START GAME, `u` (unlockall — gamedata.bnd repacked with the shortcut), the level's
# button (newgameleft.xml: set01's six in two rows, set02's four, set03's four), play
BTN=$(python3 -c "
n=$N; i=n-101
rows={0:(25,185),1:(112,185),2:(199,185),3:(286,185),4:(25,249),5:(112,249),6:(25,348),7:(112,348),8:(199,348),9:(286,348),10:(25,447),11:(112,447),12:(199,447),13:(286,447)}
x,y=rows[i]; print('%d %d' % (x+40, y+30))")
export WDBG_CLICKS="400 300 4  414 313 4  key u 2  $BTN 3  750 555 1"
export WDBG_DUMMY=${WDBG_DUMMY:-"300 480"}
export WDBG_CMD="$W/bin/winedbg --gdb --no-start --port ${WDBG_PORT:-33333} Z:\\home\\akawolf\\nfh-bench\\wine\\nfh1game\\bin\\game.exe"
timeout $((SECS + 300)) python3 wdbg.py nfh1 $PWD/s1_oracle.py $((SECS + 240)) > $LOGS/oracle${N}_$TAG.log 2>&1
grep "LEG\|INJECTED\|WATCHDOG\|CAUGHT\|^done\|^plan\|err" $LOGS/oracle${N}_$TAG.log | cut -c1-120
cp $LOGS/oracle_$L.jsonl $LOGS/oracle_${L}_$TAG.jsonl
D=$(ls -d ${WDBG_PREFIX:-$HOME/nfh-bench/wine/nfh}/drive_c/users/*/Documents/JoWooD/NFH1 | head -1)
cp "$(ls -t "$D"/GameLogicLog*.xml | head -1)" $LOGS/gamelog_${L}_$TAG.xml
echo copied

#!/bin/sh
# usage: idlebatch.sh <secs> <level numbers...>  — the oracle's idle run of each S2 level, one after another
cd "$(dirname "$(readlink -f "$0")")"
SECS=$1; shift
W=/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0
LOGS=$HOME/nfh-bench/wine/logs
for N in "$@"; do
L=$(cd ../.. && python3 -c "import sys; sys.path.insert(0,'tools/pcref'); import canon; print(canon.pc_level($N)['folder'])")
echo "== $N $L $(date +%T)"
env -u WDBG_PLAN -u WDBG_SCRIPT WDBG_LEVELNUM=$N WDBG_LEVEL=$L WDBG_SECS=$SECS WDBG_CLICKS="300 300 4  283 314 4  745 550 1" \
  WDBG_CMD="$W/bin/winedbg --gdb --no-start --port 33333 Z:\\home\\akawolf\\nfh-bench\\wine\\nfh2game\\bin\\game.exe" \
  timeout $((SECS + 180)) python3 wdbg.py nfh2 $PWD/oracle.py $((SECS + 100)) > $LOGS/oracle${N}_idle.log 2>&1
grep "^done\|WATCHDOG\|err" $LOGS/oracle${N}_idle.log | head -3
cp $LOGS/oracle_$L.jsonl $LOGS/oracle_${L}_idle.jsonl
D=$(ls -d $HOME/nfh-bench/wine/nfh/drive_c/users/*/Documents/JoWooD/NFH2 | head -1)
cp "$(ls -t "$D"/GameLogicLog*.xml | head -1)" $LOGS/gamelog_${L}_idle.xml
done
echo "batch done $(date +%T)"

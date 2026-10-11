#!/bin/sh
# usage: parkbatch.sh <secs> <levels...>  — each level's lap with Woody parked: the oracle's plan run of
# ~/nfh-bench/plans/park/LevelN.txt, then the port's replay (to the clock) and the pairing
cd "$(dirname "$(readlink -f "$0")")"
SECS=$1; shift
LOGS=${WDBG_LOGS:-$HOME/nfh-bench/wine/logs}
for N in "$@"; do
L=$(cd ../.. && python3 -c "import sys; sys.path.insert(0,'tools/pcref'); import canon; print(canon.pc_level($N)['folder'])")
echo "== $N $L $(date +%T)"
WDBG_PLAN=$HOME/nfh-bench/plans/park/Level$N.txt ./planrun.sh $N $L $SECS park 2>&1 | grep "LEG\|^plan\|WATCHDOG\|CAUGHT" | cut -c1-100
UNTIL=$SECS ./replay.sh $N $L park 2>&1 | tail -2
R=$HOME/nfh-bench/runs/replay${N}_park
NFH_PROFILE=pc nix-shell --run "python3 ../pcoracle/cmp_pairs.py $LOGS/oracle_${L}_park.jsonl $R/s2_Level$N --segments=$SECS" > $R/pairs.txt 2>&1
sed -n '/== stations (PC \/ port: the action/,$p' $R/pairs.txt | head -12
done
echo "parkbatch done $(date +%T)"

#!/bin/sh
# usage: calib.sh <n> <tag>  — a Season 2 level's PCDepartTicks settled against the oracle's <tag> run (park /
# nocatch): the port's replay without them (NFH_NO_DEPART=1) paired first; a level whose bubble then drifts
# under 0.1 s per 100 s has its keys stripped (its station seconds carry the stands), else the neighbour's
# are calibrated leg by leg (calib_depart.py); the replay with them is paired and reported
cd "$(dirname "$(readlink -f "$0")")"
N=$1; TAG=$2
L=$(cd ../.. && python3 -c "import sys; sys.path.insert(0,'tools/pcref'); import canon; print(canon.pc_level($N)['folder'])")
LOGS=$HOME/nfh-bench/wine/logs
ln -sf $LOGS/gamelog_${L}_$TAG.xml $LOGS/gamelog_${L}_nodep.xml; ln -sf $LOGS/oracle_${L}_$TAG.jsonl $LOGS/oracle_${L}_nodep.jsonl
NFH_NO_DEPART=1 UNTIL=200 ./replay.sh $N $L nodep 2>&1 | tail -1
cd ../..
R0=$HOME/nfh-bench/runs/replay${N}_nodep
NFH_PROFILE=pc nix-shell --run "python3 tools/pcoracle/cmp_pairs.py $LOGS/oracle_${L}_$TAG.jsonl $R0/s2_Level$N --segments=200" > $R0/pairs.txt 2>&1
DRIFT=$(python3 tools/pcoracle/stays_report.py $R0/pairs.txt | grep -o "([+-][0-9.]* s per 100 s" | head -1 | tr -d '(' | awk '{print $1}')
echo "$N without departure ticks: the bubble drifts $DRIFT s per 100 s"
SMALL=$(python3 -c "d='$DRIFT'; print(1 if d and abs(float(d)) < 0.1 else 0)")
if [ "$SMALL" = 1 ]; then
  python3 tools/pcoracle/calib_depart.py $N --strip
else
  python3 tools/pcoracle/calib_depart.py $N $LOGS/oracle_${L}_$TAG.jsonl $R0/s2_Level$N --write 2>&1 | grep -v "^  " | cut -c1-120
fi
cd tools/pcoracle
UNTIL=200 ./replay.sh $N $L $TAG 2>&1 | tail -1
cd ../..
R=$HOME/nfh-bench/runs/replay${N}_$TAG
NFH_PROFILE=pc nix-shell --run "python3 tools/pcoracle/cmp_pairs.py $LOGS/oracle_${L}_$TAG.jsonl $R/s2_Level$N --segments=200" > $R/pairs.txt 2>&1
python3 tools/pcoracle/stays_report.py $R/pairs.txt | grep "^==" | cut -c1-170
echo "calib $N done $(date +%T)"

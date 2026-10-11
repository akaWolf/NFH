#!/bin/sh
# usage: replay.sh <level number> <level name> <tag>  — the oracle run's inputs replayed by the port, compared
cd "$(dirname "$(readlink -f "$0")")/../.."
N=$1; L=$2; TAG=$3
LOGS=$HOME/nfh-bench/wine/logs; R=$HOME/nfh-bench/runs/replay${N}_$TAG
S=s2; [ "$N" -lt 200 ] && S=s1
mkdir -p $R/$S
NFH_PROFILE=pc nix-shell --run "python3 tools/pcoracle/oracle2plan.py $N $LOGS/gamelog_${L}_$TAG.xml" > $R/$S/Level$N.txt
nix-shell --run "python3 tests/run_tricks.py $R/$S/Level$N.txt --out=$R" > $R/run.log 2>&1
tail -3 $R/run.log
python3 tools/pcoracle/cmp_run.py $LOGS/oracle_${L}_$TAG.jsonl $R/${S}_Level$N > $R/cmp.txt
echo "cmp: $R/cmp.txt ($(wc -l < $R/cmp.txt) lines)"

#!/bin/sh
# re-pair Season 2 replays (<tag>: park / nocatch) from the project root and report the legs
cd "$(dirname "$(readlink -f "$0")")/../.."
TAG=$1; shift
for N in "$@"; do
  L=$(python3 -c "import sys; sys.path.insert(0,'tools/pcref'); import canon; print(canon.pc_level($N)['folder'])")
  R=$HOME/nfh-bench/runs/replay${N}_$TAG
  [ -d $R/s2_Level$N ] && [ -f $HOME/nfh-bench/wine/logs/oracle_${L}_$TAG.jsonl ] || { echo "$N: not there"; continue; }
  NFH_PROFILE=pc nix-shell --run "python3 tools/pcoracle/cmp_pairs.py $HOME/nfh-bench/wine/logs/oracle_${L}_$TAG.jsonl $R/s2_Level$N --segments=200" > $R/pairs.txt 2>&1
done
python3 tools/pcoracle/stays_report.py $(for N in "$@"; do echo $HOME/nfh-bench/runs/replay${N}_$TAG/pairs.txt; done) 2>&1 | cut -c1-150

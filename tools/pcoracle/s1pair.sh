#!/bin/sh
# re-pair the finished Season 1 parked laps from the project root (the batch's own pairing ran nix-shell
# from tools/pcoracle, where there is no shell.nix) and report the legs
cd "$(dirname "$(readlink -f "$0")")/../.."
for N in "$@"; do
  L=$(python3 -c "import sys; sys.path.insert(0,'tools/pcref'); import canon; print(canon.pc_level($N)['folder'])")
  R=$HOME/nfh-bench/runs/replay${N}_park
  [ -d $R/s1_Level$N ] && [ -f $HOME/nfh-bench/wine/logs1/oracle_${L}_park.jsonl ] || { echo "$N: not there"; continue; }
  NFH_PROFILE=pc nix-shell --run "python3 tools/pcoracle/cmp_pairs.py $HOME/nfh-bench/wine/logs1/oracle_${L}_park.jsonl $R/s1_Level$N --segments=200" > $R/pairs.txt 2>&1
done
python3 tools/pcoracle/stays_report.py $(for N in "$@"; do echo $HOME/nfh-bench/runs/replay${N}_park/pairs.txt; done) 2>&1 | cut -c1-140

#!/bin/sh
# usage: planbatch.sh <secs> <levels...>  — the port's real Season 2 plans on the oracle, one after another
cd "$(dirname "$(readlink -f "$0")")"
SECS=$1; shift
for N in "$@"; do
  L=$(cd ../.. && python3 -c "import sys; sys.path.insert(0,'tools/pcref'); import canon; print(canon.pc_level($N)['folder'])")
  echo "== $N $L $(date +%T)"
  env -u WDBG_PLAN ./planrun.sh $N $L $SECS planrun 2>&1 | grep "LEG\|^plan\|WATCHDOG\|CAUGHT\|MINIGAME" | cut -c1-110
done
echo "planbatch done $(date +%T)"

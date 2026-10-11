#!/bin/sh
# usage: s1plan.sh <secs> <levels...>  — the port's Season 1 plans on NFH1's oracle (the second instance)
export WDBG_DISPLAY=:96 WDBG_PORT=33334 WDBG_PREFIX=$HOME/nfh-bench/wine/nfh1pfx WDBG_LOGS=$HOME/nfh-bench/wine/logs1 WDBG_WATCHDOG=30
cd "$(dirname "$(readlink -f "$0")")"
SECS=$1; shift
for N in "$@"; do
  L=$(cd ../.. && python3 -c "import sys; sys.path.insert(0,'tools/pcref'); import canon; print(canon.pc_level($N)['folder'])")
  echo "== $N $L $(date +%T)"
  env -u WDBG_PLAN ./s1planrun.sh $N $L $SECS ${TAG:-planrun} 2>&1 | grep "LEG\|^plan\|WATCHDOG\|CAUGHT\|INJECTED" | cut -c1-110
done
echo "s1plan done $(date +%T)"

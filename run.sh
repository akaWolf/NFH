#!/bin/sh
# Launch the level viewer, extracting the game assets on first run.
#   ./run.sh                          # Level101
#   ./run.sh levels/s2/Level208.json
set -e
root=$(cd "$(dirname "$0")" && pwd)
: "${NFH_DATA:=/tmp/nfh-data}"

if [ ! -d "$root/textures/s1" ]; then
    echo "first run: extracting season 1 assets (a few minutes)"
    [ -d "$NFH_DATA/apk" ] || "$root/tools/extract.sh" "$NFH_DATA"
    (cd "$root" && NFH_DATA="$NFH_DATA" python3 tools/extract_textures.py textures/s1)
    (cd "$root" && NFH_DATA="$NFH_DATA" python3 tools/extract_audio.py audio/s1)
    echo "note: season 2 assets need its apk+obb unpacked; see tools/README.md"
fi
cd "$root"
exec python3 runtime/viewer.py "${@:-levels/s1/Level101.json}"

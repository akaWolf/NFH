#!/bin/sh
# Decompile the game assemblies to C# with ILSpy.
#
# One-time setup (no root needed):
#   curl -sSL -o /tmp/dotnet-install.sh https://dot.net/v1/dotnet-install.sh
#   sh /tmp/dotnet-install.sh --channel LTS --install-dir "$HOME/.dotnet" --no-path
#   PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="$HOME/.dotnet" dotnet tool install -g ilspycmd
set -e

root=$(cd "$(dirname "$0")/.." && pwd)
: "${NFH_DATA:=$root/data}"
managed=$NFH_DATA/apk/assets/bin/Data/Managed

DOTNET_ROOT="$HOME/.dotnet"
PATH="$HOME/.dotnet:$HOME/.dotnet/tools:$PATH"
export DOTNET_ROOT PATH DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

[ -f "$managed/Assembly-CSharp.dll" ] || {
    echo "no assemblies under $managed — run tools/extract.sh or set NFH_DATA" >&2
    exit 1
}

for dll in Assembly-CSharp Assembly-CSharp-firstpass CoreFramework; do
    [ -f "$managed/$dll.dll" ] || continue
    echo "decompiling $dll"
    ilspycmd -p -o "$root/src/$dll" -r "$managed" \
             --disable-updatecheck --ignore-decompilation-errors \
             "$managed/$dll.dll"
done

echo "$(find "$root/src" -name '*.cs' | wc -l) files, $(cat $(find "$root/src" -name '*.cs') | wc -l) lines"

#!/bin/sh
# Decompile the game assemblies to C# with ILSpy.
#
# One-time setup (no root needed):
#   curl -sSL -o /tmp/dotnet-install.sh https://dot.net/v1/dotnet-install.sh
#   sh /tmp/dotnet-install.sh --channel LTS --install-dir "$HOME/.dotnet" --no-path
#   PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="$HOME/.dotnet" \
#       dotnet tool install -g ilspycmd --version "$ILSPY_PIN"
set -e

# The pin: runtime/ cites the decompiled text by file AND LINE NUMBER
# (thousands of Pawn.cs:NNNN references). Another ILSpy release shifts
# the numbering and silently degrades every citation — regenerate with
# this exact version only (see src/README.md).
ILSPY_PIN=11.0.0.9375

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

v=$(ilspycmd --version 2>/dev/null | sed -n 's/^ilspycmd: //p')
[ "$v" = "$ILSPY_PIN" ] || {
    echo "WARNING: ilspycmd $v != pinned $ILSPY_PIN — the line numbers" >&2
    echo "runtime/ cites will not match this output (src/README.md)" >&2
}

for dll in Assembly-CSharp Assembly-CSharp-firstpass CoreFramework; do
    [ -f "$managed/$dll.dll" ] || continue
    echo "decompiling $dll"
    ilspycmd -p -o "$root/src/$dll" -r "$managed" \
             --disable-updatecheck --ignore-decompilation-errors \
             "$managed/$dll.dll"
done

echo "$(find "$root/src" -name '*.cs' | wc -l) files, $(cat $(find "$root/src" -name '*.cs') | wc -l) lines"

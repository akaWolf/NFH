# the port's environment on NixOS: PySDL2 over the system SDL2, Pillow for
# the sheet loader, NumPy for the extractors, frida for tools/livediff
#
#   nix-shell --run "python3 runtime/app.py"
#   nix-shell --run "python3 tools/livediff/sweep.py clicks-live"
{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  packages = with pkgs; [
    (python3.withPackages (p: [ p.pysdl2 p.pillow p.numpy p.frida-python ]))
    SDL2 SDL2_image SDL2_mixer SDL2_ttf
  ];
}

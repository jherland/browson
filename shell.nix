# Run nix-shell without arguments to enter an environment with all the
# project dependencies in place.
{
  pkgs ? import (builtins.fetchGit {
    url = "https://github.com/NixOS/nixpkgs/";
    ref = "nixos-20.09";
  }) {}
}:

pkgs.mkShell {
  venvDir = "./.venv";
  buildInputs = with pkgs; [
    git
    python36
    python36Packages.venvShellHook
    python37
    python38
    python39
  ];
  postShellHook = ''
    unset SOURCE_DATE_EPOCH
    pip install flit
    flit install -s
  '';
}

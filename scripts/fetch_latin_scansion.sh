#!/usr/bin/env bash
# Fetch the CUNY-CL/latin_scansion repo (grammars/ source + Makefiles) so we
# can inspect/attempt building the FST scansion grammar locally, without
# committing to installing new deps yet.
#
# This only needs `git` (already available) to download. It does NOT install
# pynini/thrax -- it just clones the repo and, if you pass --try-build,
# attempts `make -j -C grammars` with whatever's already on PATH, so you can
# see exactly what's missing (almost certainly `thraxcompiler`).
#
# Usage:
#   scripts/fetch_latin_scansion.sh              # clone only
#   scripts/fetch_latin_scansion.sh --try-build   # clone + attempt the build

set -euo pipefail

_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_DEST="$_ROOT/vendor/latin_scansion"
_TRY_BUILD=false

for arg in "$@"; do
  case "$arg" in
    --try-build) _TRY_BUILD=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

mkdir -p "$_ROOT/vendor"

if [ -d "$_DEST/.git" ]; then
  echo "Already cloned at $_DEST -- pulling latest instead of re-cloning."
  git -C "$_DEST" pull --ff-only
else
  echo "Cloning CUNY-CL/latin_scansion into $_DEST ..."
  git clone --depth 1 https://github.com/CUNY-CL/latin_scansion "$_DEST"
fi

echo
echo "Fetched. Key paths:"
echo "  $_DEST/grammars/          (Thrax grammar source + Makefile)"
echo "  $_DEST/environment.yml    (conda env: pynini, thrax, make, protobuf)"
echo "  $_DEST/latin_scansion/    (Python library, already pip-installed separately)"

if [ "$_TRY_BUILD" = true ]; then
  echo
  echo "Attempting 'make -j -C grammars' with whatever's already on PATH ..."
  echo "(expected to fail without thrax -- this just shows exactly what's missing)"
  echo
  if make -j -C "$_DEST/grammars"; then
    echo
    echo "Build succeeded unexpectedly -- check $_DEST/grammars/ for the compiled .far file(s)."
  else
    echo
    echo "Build failed (exit $?), most likely because 'thraxcompiler' isn't installed."
    echo "thrax has no pip wheel -- it needs the conda environment:"
    echo "  conda env create -f $_DEST/environment.yml"
    echo "  conda activate scansion"
    echo "  make -j -C $_DEST/grammars"
  fi
fi

#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ -n "$DAGONGREN_PYTHON" ]; then
  "$DAGONGREN_PYTHON" scripts/desktop_launcher.py "$@"
else
  python3 scripts/desktop_launcher.py "$@"
fi
code=$?
if [ "$code" -ne 0 ]; then
  printf '\nRequires Python 3.10+. See docs/desktop-testing.md. Press Enter to close.\n'
  read -r unused
fi
exit "$code"

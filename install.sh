#!/bin/sh
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo "Python 3 needed (install python3)"; exit 1; }
python3 install.py "$@"

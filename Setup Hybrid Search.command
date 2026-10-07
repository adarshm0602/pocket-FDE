#!/bin/zsh
cd "$(dirname "$0")" || exit 1
PYTHONPATH=pocket-fde .venv/bin/python -m web.hybrid
printf '\nPress Enter to close.'
read -r

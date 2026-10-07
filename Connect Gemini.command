#!/bin/zsh
task_root="${0:A:h}"
"$task_root/.venv/bin/python" "$task_root/pocket-fde/web/connect_gemini.py"
printf '\nPress Enter to close this setup.\n'
read -r

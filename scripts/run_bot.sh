#!/bin/sh
# Keeps the bot running on a server where you don't have admin rights.
#
# It starts the bot, and whenever the bot stops (a crash, a lost connection), starts it again
# after RESTART_DELAY seconds. Let cron launch this script every 10 minutes: flock lets only one
# copy run at a time, so that also brings the bot back after the server restarts.
#
#   */10 * * * * PYTHON=/path/to/envs/micropaperbot/bin/python flock -n $HOME/.micropaperbot.lock $HOME/micropaperbot/scripts/run_bot.sh
#
# PYTHON is your conda environment's Python (run `which python` with the environment active).
# The bot's output goes to logs/bot.log.
#
# The bot runs by its full path, so `pkill -f micropaperbot/scripts/bot.py` restarts only this bot
# when another bot made from the same code (such as neuropaperbot) runs on the same server.
PYTHON="${PYTHON:-python3}"
RESTART_DELAY="${RESTART_DELAY:-30}"

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
while true; do
    "$PYTHON" "$(pwd)/scripts/bot.py" >> logs/bot.log 2>&1
    status=$?
    echo "$(date -u '+%Y-%m-%d %H:%M:%S') The bot stopped (exit code $status); starting it again in $RESTART_DELAY seconds." >> logs/bot.log
    sleep "$RESTART_DELAY"
done

#!/bin/bash
# usage: LICHII_GAME=<path to the title> tools/nx2/oot/ab_cycle.sh <label> [ENV=VALUE ...]
# Restarts Lichii, loads the save with 4 presses of A, then replays the 30 s course 3 times and
# prints the per-pass FPS summary (ab_move.py). Results go to $LICHII_OUT/run-<label>.
set -u
label=$1; shift
root=$(cd "$(dirname "$0")/../../.." && pwd)
bin=${LICHII_BIN:-$root/build/native/bin/lichii}
game=${LICHII_GAME:?set LICHII_GAME to the title path}
out=${LICHII_OUT:-/tmp/lichii-oot}/run-$label
mkdir -p "$out"
pkill -KILL -x lichii; sleep 2
env "$@" MANGOHUD=0 QT_QPA_PLATFORM=xcb EDEN_NX2_DEBUG_SERVER=127.0.0.1:47890 EDEN_DKB_FRAME_TRACE=1 \
    EDEN_NX2_PRELOAD_ALL_PIPELINES=1 ${LICHII_TASKSET:+taskset -c $LICHII_TASKSET} \
    setsid nohup "$bin" "$game" > "$out/stdout.txt" 2>&1 &
sleep 5
cd "$(dirname "$0")"
python3 -I load_save.py || exit 1
sleep 15
for i in 1 2 3; do python3 -I ab_move.py "${label}_$i" 2>&1 | tail -4; sleep 5; done
cp "${LICHII_LOG:-$HOME/.local/share/eden/log/eden_log.txt}" "$out/eden_log.txt"

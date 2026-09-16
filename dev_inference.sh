#!/bin/bash

echo "Starting model server on port 8001..."

# Injected environment targets for text-to-phoneme synthesizer 
export ESPEAK_DATA_PATH="/usr/lib/x86_64-linux-gnu/espeak-ng-data"
export PHONEMIZER_ESPEAK_PATH="/usr/bin/espeak-ng"
export PHONEMIZER_ESPEAK_LIBRARY="/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"

uv run fastapi run inference/main.py --host 0.0.0.0 --port 8001

#!/bin/bash
ffmpeg -f alsa -i default \
  -ac 1 \
  -ar 16000 \
  -c:a pcm_s16le \
  learner.wav
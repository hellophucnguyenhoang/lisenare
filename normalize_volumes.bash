mkdir -p ready_to_listen
parallel ffmpeg -loglevel quiet -i {} -filter:a "loudnorm=I=-16:TP=-1.5" "ready_to_listen/{.}.wav" ::: *.wav

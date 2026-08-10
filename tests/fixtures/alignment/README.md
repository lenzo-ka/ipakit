# Forced-alignment fixtures

`hello-world.wav` was synthesized on macOS 26 on 2026-08-10 with:

```sh
say -v Samantha -r 155 -o hello-world.aiff 'hello world'
ffmpeg -i hello-world.aiff -ar 16000 -ac 1 -c:a pcm_s16le hello-world.wav
```

It is a 16 kHz mono 16-bit PCM recording. `hello-world.json` records the
PocketSphinx 5.1.1 default en-us model's second-pass alignment of that file;
starts and durations are decoder frames and the recorded frame rate is read
from the decoder configuration.

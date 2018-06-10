# Open Chicken Coop

## General status

* streams video + audio over TCP
* basic silence/noise detection

## `spawn_detect`

### Usage

```
cd sounds
# add audio files of recorded ambient sounds in ambient/, or generate fake ones with:
make fake_ambient

# generate audio noise profile
make

cd ..
# start main program, run ./occ -h to get command line usage help
./occ.py -a 'alsa:sysdefault:CARD=C615' -s v4l2:/dev/video0 -v debug
```

Sample output:
```
2018-06-10 14:10:01,104 INFO [capture] Running FFmpeg capture process with: ffmpeg -hide_banner -loglevel quiet -re -f v4l2 -i /dev/video0 -f alsa -ac 1 -i sysdefault:CARD=C615 -map 0:v -c:v libxvid -qscale:v 4 -map 1:a -c:a libfdk_aac -q:a 4 -muxdelay 0.1 -f mpegts udp://localhost:1234 -c:a copy -f wav -
2018-06-10 14:10:01,105 INFO [chicken noise detection] Running SoX ambient noise filtering with: sox -q -t wav - -t wav - noisered sounds/ambient_profile 0.3
2018-06-10 14:10:01,107 INFO [chicken noise detection] Running FFmpeg chicken noise detection with: ffmpeg -hide_banner -nostats -f wav -i - -filter:a silencedetect=noise=-10dB:duration=1 -f null /dev/null
2018-06-10 14:10:05,973 DEBUG [chicken noise detection] [silencedetect @ 0x555b10f32bc0] silence_start: 0
2018-06-10 14:10:05,973 INFO [chicken noise detection] silence -> chicken noise
2018-06-10 14:10:07,028 DEBUG [chicken noise detection] [silencedetect @ 0x555b10f32bc0] silence_end: 3.86233 | silence_duration: 3.86233
2018-06-10 14:10:07,028 INFO [chicken noise detection] chicken noise -> silence
2018-06-10 14:10:15,029 DEBUG [chicken noise detection] [silencedetect @ 0x555b10f32bc0] silence_start: 3.96121
2018-06-10 14:10:15,029 INFO [chicken noise detection] silence -> chicken noise
2018-06-10 14:10:16,232 DEBUG [chicken noise detection] [silencedetect @ 0x555b10f32bc0] silence_end: 13.037 | silence_duration: 9.07581
2018-06-10 14:10:16,233 INFO [chicken noise detection] chicken noise -> silence
2018-06-10 14:10:18,951 DEBUG [chicken noise detection] [silencedetect @ 0x555b10f32bc0] silence_start: 13.1032
2018-06-10 14:10:18,951 INFO [chicken noise detection] silence -> chicken noise
2018-06-10 14:10:20,005 DEBUG [chicken noise detection] [silencedetect @ 0x555b10f32bc0] silence_end: 16.864 | silence_duration: 3.76081
2018-06-10 14:10:20,005 INFO [chicken noise detection] chicken noise -> silence

```

### Requirements

* [Python >=3.5](https://www.python.org/)
* [SoX](http://sox.sourceforge.net/)
* [FFmpeg](https://www.ffmpeg.org/), compiled with and `--enable-libfdk-aac` and `--enable-libxvid`.

### TODO

* systemd service
* video filters
* audio filters
* AUR package

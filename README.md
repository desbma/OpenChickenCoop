# Open Chicken Coop

## General status

* streams video + audio over UDP
* very basic silence/noise detection

## `spawn_detect`

### Usage

```
cd sounds
# add audio files of recorded ambient sounds in ambient, or generate fake ones with:
make fake_ambient
# make audio profile
make
cd ..
# run ./occ -h to get command line usage help
./occ.py -a 'alsa:sysdefault:CARD=C615' -s v4l2:/dev/video0 -v debug
```

### Requirements

* [Python 3](https://www.python.org/)
* [SoX](http://sox.sourceforge.net/)
* [FFmpeg](https://www.ffmpeg.org/), compiled with libfdk_aac, see [here](https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu) for Ubuntu

### TODO

* tests
* systemd service
* video filters
* audio filters
* improve streaming
* AUR package

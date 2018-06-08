# Open Chicken Coop

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
./occ.py -a alsa:hw:2 -s v4l2:/dev/video0 -v debug
```

### Requirements

* python3
* sox
* ffmpeg

### TODO

* tests
* systemd service
* video filters
* audio filters
* AUR package

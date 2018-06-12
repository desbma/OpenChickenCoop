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
2018-06-10 17:03:13,062 INFO MainThread [capture] Running FFmpeg capture process with: ffmpeg -loglevel quiet -re -f v4l2 -input_format mjpeg -i /dev/video0 -f alsa -ac 1 -i sysdefault:CARD=C615 -sdp_file /tmp/occ_unu2_5z_/av.sdp -map 0:v -c:v libxvid -qscale 4 -f rtp rtp://127.0.0.1:10001 -map 1:a -c:a libopus -b:a 64k -f rtp rtp://127.0.0.1:10011 -map 1:a -c:a copy -f wav -
2018-06-10 17:03:13,064 INFO StreamingServerThread [streaming server] TCP server started, serving on port 11000, connect to it with 'ffplay tcp://IP:11000'
2018-06-10 17:03:13,064 INFO NoiseDetectionThread [chicken noise detection] Running SoX ambient noise filtering with: sox -q -t wav - -t wav - noisered sounds/ambient_profile 0.3
2018-06-10 17:03:13,066 INFO NoiseDetectionThread [chicken noise detection] Running FFmpeg chicken noise detection with: ffmpeg -hide_banner -nostats -f wav -i - -filter:a silencedetect=noise=-10dB:duration=1 -f null /dev/null
2018-06-10 17:03:17,911 DEBUG NoiseDetectionThread [chicken noise detection] [silencedetect @ 0x564812ebabc0] silence_start: 0
2018-06-10 17:03:17,911 INFO NoiseDetectionThread [chicken noise detection] silence -> chicken noise
2018-06-10 17:03:19,117 DEBUG NoiseDetectionThread [chicken noise detection] [silencedetect @ 0x564812ebabc0] silence_end: 3.99481 | silence_duration: 3.99481
2018-06-10 17:03:19,117 INFO NoiseDetectionThread [chicken noise detection] chicken noise -> silence
2018-06-10 17:03:26,549 INFO Thread-1 [streaming server] Got request from ('127.0.0.1', 54022)
2018-06-10 17:03:26,549 INFO Thread-1 [streaming server] Running FFmpeg streaming process with: ffmpeg -loglevel quiet -protocol_whitelist file,rtp,udp -i /tmp/occ_unu2_5z_/av.sdp -map v -map a -c:v copy -c:a copy -f matroska -

```

### Requirements

* [Python >=3.5](https://www.python.org/)
* [SoX](http://sox.sourceforge.net/)
* [FFmpeg](https://www.ffmpeg.org/), compiled with `--enable-libxvid`.

### TODO

* systemd service
* video filters
* audio filters
* AUR package


## Target hardware

Galaxy S7 Edge (SM-G935F)

Reason for choice: I have one with a broken screen, so not worth much on the aftermarket.

Pros:
+ IP68
+ powerful 8 cores CPU
+ good battery
+ good camera
+ hardware video encoding & decoding

Cons:
- no official LineageOS ROM for now

### Steps to prepare

1. Factory wipe
2. Install Google Play
3. Uninstall/disable all other ~~crap~~apps that can be
4. Do a full Android + Apps update
5. Install [Linux Deploy](https://play.google.com/store/apps/details?id=ru.meefik.linuxdeploy&hl=en)
6. Root phone **TODO**

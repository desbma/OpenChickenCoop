.PHONY: all fake_ambient clean

SOX    := sox -q -R
FFMPEG := ffmpeg -hide_banner -loglevel quiet

INTERNAL_FFMPEG_CODEC_PARAMS = -c:a wavpack -f wv

AMBIENT_FILES := $(wildcard ambient/*)


all:: ambient_profile

print-%:
	@echo $*=$($*)

ambient_profile: ambient_concat.wv
	${SOX} $^ -n noiseprof $@

ambient_concat.wv: ambient_list.txt
	${FFMPEG} -f concat -safe 0 -i $^ ${INTERNAL_FFMPEG_CODEC_PARAMS} $@

ambient_list.txt: ${AMBIENT_FILES}
	-rm -f $@
	find ambient -type f -printf "file '%p'\n" >> $@

fake_ambient: ambient/fake_ambient.wv

ambient/fake_ambient.wv:
	mkdir -p $(dir $@)
	${SOX} -c 1 -b 16 -r 48k -n $@ -G synth 30 whitenoise loudness -50 50 norm 2> /dev/null

clean:
	-rm -f ambient_concat.wv ambient_list.txt ambient/fake_ambient.wv

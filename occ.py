#!/usr/bin/env python3

""" Open Chicken Coop. """

import argparse
import logging
import subprocess
import sys

import colored_logging


def parse_audio_device(s):
  """ Parse command line audio device. """
  try:
    atype, dev = s.split(":", 1)
  except ValueError as e:
    raise argparse.ArgumentTypeError("Audio source should be in the form TYPE:DEVICE")
  return atype, dev


def parse_video_device(s):
  """ Parse command line video device. """
  try:
    vtype, dev = s.split(":", 1)
  except ValueError:
    raise argparse.ArgumentTypeError("Video source should be in the form TYPE:DEVICE")
  return vtype, dev


if __name__ == "__main__":
  # parse args
  arg_parser = argparse.ArgumentParser(description=__doc__,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  arg_parser.add_argument("-a",
                          "--audio-source",
                          required=True,
                          type=parse_audio_device,
                          help="""Audio source device.
                                  Prefix with type ie. 'alsa:XXX' or 'pulseaudio:YYY'.
                                  Identify device with 'arecord -L' for alsa, or 'pacmd list-sources' for pulseaudio.""")
  arg_parser.add_argument("-s",
                          "--video-source",
                          required=True,
                          type=parse_video_device,
                          help="""Video source device.
                                  Prefix with type ie. 'v4l2:XXX'.
                                  Identify device 'v4l2-ctl --list-formats-ext' or 'ffmpeg -f v4l2 -list_formats all -i /dev/video0'.""")
  arg_parser.add_argument("-v",
                          "--verbosity",
                          choices=("warning", "normal", "debug"),
                          default="normal",
                          dest="verbosity",
                          help="Level of output to display")
  args = arg_parser.parse_args()

  # setup logger
  logging_level = {"warning": logging.WARNING,
                   "normal": logging.INFO,
                   "debug": logging.DEBUG}
  logging.getLogger().setLevel(logging_level[args.verbosity])
  if sys.stderr.isatty():
    logging_formatter = colored_logging.ColoredFormatter(fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s")
  else:
    # assume systemd service in 'simple' mode
    logging_formatter = logging.Formatter(fmt="%(levelname)s [%(name)s] %(message)s")
  logging_handler = logging.StreamHandler()
  logging_handler.setFormatter(logging_formatter)
  logging.getLogger().addHandler(logging_handler)

  # build ffmpeg command line
  # TODO don't hardcode input channel count
  cmd = ["ffmpeg", "-hide_banner", "-y",
         "-f", args.video_source[0], "-i", args.video_source[1],
         "-f", args.audio_source[0], "-ac", "1", "-i", args.audio_source[1],
         "-map", "0:v", "-c:v", "copy",
         "-map", "1:a", "-c:a", "libopus", "-b:a", "64k",
         "-f", "matroska", "/tmp/a.mkv"]
  logging.getLogger().debug(f"Running FFMpeg: {subprocess.list2cmdline(cmd)}")
  ffmpeg_process = subprocess.Popen(cmd)
  ffmpeg_process.wait()

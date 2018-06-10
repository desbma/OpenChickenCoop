#!/usr/bin/env python3

""" Open Chicken Coop. """

import argparse
import logging
import selectors
import subprocess
import sys
import threading

import colored_logging


def parse_audio_device(s):
  """ Parse command line audio device. """
  try:
    atype, dev = s.split(":", 1)
  except ValueError:
    raise argparse.ArgumentTypeError("Audio source should be in the form TYPE:DEVICE")
  return atype, dev


def parse_video_device(s):
  """ Parse command line video device. """
  try:
    vtype, dev = s.split(":", 1)
  except ValueError:
    raise argparse.ArgumentTypeError("Video source should be in the form TYPE:DEVICE")
  return vtype, dev


class NoiseDetectionThread(threading.Thread):

  def __init__(self, capture_process, noise_name, db_limit, profile_path, *args, **kwargs):
    self.capture_process = capture_process
    self.noise_name = noise_name
    self.db_limit = db_limit
    self.profile_path = profile_path

    self.logger = logging.getLogger(f"{noise_name} noise detection")

    super().__init__(*args, **kwargs)

  def run(self):
    try:
      # sox noise filtering
      sox_cmd = ["sox", "-q",
                 "-t", "wav", "-",
                 "-t", "wav", "-",
                 "noisered", self.profile_path, "0.3"]
      self.logger.info(f"Running SoX ambient noise filtering with: {subprocess.list2cmdline(sox_cmd)}")
      noise_filtering_process = subprocess.Popen(sox_cmd,
                                                 stdin=self.capture_process.stdout,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)
      assert(noise_filtering_process.poll() is None)

      # ffmpeg silence detection
      # TODO tune audio silence threshold
      noise_detection_cmd = ["ffmpeg", "-hide_banner", "-nostats",
                             "-f", "wav", "-i", "-",
                             "-filter:a", f"silencedetect=noise={self.db_limit}dB:duration=1",
                             "-f", "null", "/dev/null"]
      self.logger.info(f"Running FFmpeg {self.noise_name} noise detection with: {subprocess.list2cmdline(noise_detection_cmd)}")
      noise_detection_process = subprocess.Popen(noise_detection_cmd,
                                                 stdin=noise_filtering_process.stdout,
                                                 stdout=subprocess.DEVNULL,
                                                 stderr=subprocess.PIPE,
                                                 universal_newlines=True)
      assert(noise_detection_process.poll() is None)

      # parse ffmpeg output
      pending_line = ""
      while noise_detection_process.poll() is None:
        try:
          noise_detection_process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
          pass

        new_output = self.readNonBlocking(noise_detection_process.stderr)
        for new_line in new_output.splitlines(keepends=True):
          pending_line = pending_line + new_line
          if pending_line.endswith("\n"):
            if pending_line.startswith("[silencedetect"):
              self.logger.debug(pending_line.strip())
              if "silence_start" in pending_line:
                self.logger.info(f"silence -> {self.noise_name} noise ")
              elif "silence_end" in pending_line:
                self.logger.info(f"{self.noise_name} noise -> silence")
            pending_line = ""

    except Exception as e:
      self.logger.error(f"{e.__class__.__qualname__}: {e}")

  def readNonBlocking(self, file):
    r = []
    poller = selectors.DefaultSelector()
    poller.register(file, selectors.EVENT_READ)
    while True:
      events = poller.select(timeout=0.05)
      if not events:
        break
      r.append(file.read(1))
    return "".join(r)


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

  # ffmpeg capture
  # TODO don't hardcode audio input parameters (ie. channel count)
  # TODO don't hardcode video input parameters (ie. res, fps...)
  # TODO don't hardcode audio encoding parameters
  # TODO don't hardcode video encoding parameters
  # TODO optional hqdn3d filter
  capture_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "quiet",
                 "-re",
                 "-f", args.video_source[0], "-i", args.video_source[1],
                 "-f", args.audio_source[0], "-ac", "1", "-i", args.audio_source[1],
                 "-map", "0:v", "-c:v", "libxvid", "-qscale:v", "4",
                 "-map", "1:a", "-c:a", "libfdk_aac", "-q:a", "4",
                 "-muxdelay", "0.1",
                 "-f", "mpegts", "udp://localhost:1234",
                 "-c:a", "copy",
                 "-f", "wav", "-"]
  logging.getLogger("capture").info(f"Running FFmpeg capture process with: {subprocess.list2cmdline(capture_cmd)}")
  capture_process = subprocess.Popen(capture_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
  assert(capture_process.poll() is None)

  # noise detection thread
  nd_thread = NoiseDetectionThread(capture_process, "chicken", -10, "sounds/ambient_profile")
  nd_thread.start()
  nd_thread.join()

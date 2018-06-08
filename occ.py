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


class SilenceDetectionThread(threading.Thread):

  def __init__(self, capture_process, *args, **kwargs):
    self.capture_process = capture_process
    self.logger = logging.getLogger(self.__class__.__name__)
    super().__init__(*args, **kwargs)

  def run(self):
    try:
      # TODO insert sox noisered process + more filtering

      # ffmpeg silence detection
      # TODO tune audio silence threshold
      silence_detection_cmd = ["ffmpeg", "-hide_banner", "-nostats",
                               "-f", "flac", "-i", "-",
                               "-filter:a", "silencedetect=noise=-10dB:duration=1",
                               "-f", "null", "/dev/null"]
      self.logger.debug(f"Running FFmpeg silence detection with: {subprocess.list2cmdline(silence_detection_cmd)}")
      silence_detection_process = subprocess.Popen(silence_detection_cmd,
                                                   stdin=self.capture_process.stdout,
                                                   stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.PIPE,
                                                   universal_newlines=True)

      # parse silence detection output
      pending_line = ""
      while silence_detection_process.poll() is None:
        try:
          silence_detection_process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
          pass

        new_output = self.readNonBlocking(silence_detection_process.stderr)
        for new_line in new_output.splitlines(keepends=True):
          pending_line = pending_line + new_line
          if pending_line.endswith("\n"):
            if pending_line.startswith("[silencedetect"):
              self.logger.debug(pending_line.strip())
              if "silence_start" in pending_line:
                self.logger.info("Silence -> noise")
              elif "silence_end" in pending_line:
                self.logger.info("Noise -> silence")
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
  # TODO don't hardcode input channel count
  # TODO optional hqdn3d filter
  # TODO option video storage with rotation
  capture_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "quiet",
                 "-re",
                 "-f", args.video_source[0], "-i", args.video_source[1],
                 "-f", args.audio_source[0], "-ac", "1", "-i", args.audio_source[1],
                 "-map", "0:v", "-c:v", "libxvid", "-qscale:v", "4",
                 "-map", "1:a", "-c:a", "libfdk_aac", "-q:a", "4",
                 "-muxdelay", "0.1",
                 "-f", "mpegts", "udp://localhost:1234",
                 "-f", "flac", "-"]
  logging.getLogger("Capture").debug(f"Running FFmpeg capture process with: {subprocess.list2cmdline(capture_cmd)}")
  capture_process = subprocess.Popen(capture_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

  # silence detection thread
  sd_thread = SilenceDetectionThread(capture_process)
  sd_thread.start()
  sd_thread.join()

#!/usr/bin/env python3

""" Open Chicken Coop. """

import argparse
import inspect
import logging
import os
import selectors
import shlex
import socketserver
import subprocess
import sys
import tempfile
import threading

import colored_logging


LOCAL_UDP_PORT_VIDEO = 10001
LOCAL_UDP_PORT_AUDIO = 10011
STREAMING_SERVER_PORT = 11000


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

  """ Thread to detect noise/silence in input audio stream. """

  def __init__(self, *, capture_process, noise_name, db_limit, profile_path, on_noise_command):
    self.capture_process = capture_process
    self.noise_name = noise_name
    self.db_limit = db_limit
    self.profile_path = profile_path
    self.on_noise_command = shlex.split(on_noise_command) if (on_noise_command is not None) else None

    self.logger = logging.getLogger(f"{noise_name} noise detection")

    super().__init__(daemon=True, name=__class__.__name__)

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
                self.logger.info(f"silence -> {self.noise_name} noise")
                self.noiseAction()
              elif "silence_end" in pending_line:
                self.logger.info(f"{self.noise_name} noise -> silence")
            pending_line = ""

    except Exception as e:
      self.logger.error(f"{e.__class__.__qualname__}: {e}")

  def noiseAction(self):
    """ Called on noise detected, run user command. """
    if self.on_noise_command is not None:
      # TODO pass time as env var
      self.logger.info(f"Running user command: {subprocess.list2cmdline(self.on_noise_command)}")
      subprocess.call(self.on_noise_command, stdin=subprocess.DEVNULL)

  def readNonBlocking(self, file):
    """ Read data from a file descriptor without blocking, return data or None. """
    r = []
    poller = selectors.DefaultSelector()
    poller.register(file, selectors.EVENT_READ)
    while True:
      events = poller.select(timeout=0.05)
      if not events:
        break
      r.append(file.read(1))
    return "".join(r)


class StreamingServerRequestHandler(socketserver.StreamRequestHandler):

  """ Streaming server request handler. """

  def handle(self):
    logger = logging.getLogger("streaming server")

    logger.info(f"Got request from {self.client_address}")
    got_sem = self.server.connection_sem.acquire(blocking=False)
    if got_sem:
      try:
        stream_cmd = ["ffmpeg", "-loglevel", "quiet",
                      "-protocol_whitelist", "file,rtp,udp",
                      "-i", self.server.sdp_filepath,
                      "-f", "s16le", "-ac", "1", "-ar", "48k", "-i", f"udp://127.0.0.1:{LOCAL_UDP_PORT_AUDIO}",
                      "-map", "0:v", "-map", "1:a",
                      "-c:v", "copy",
                      "-c:a", "libopus", "-b:a", "64k",
                      "-f", "matroska", "-"]
        logger.info(f"Running FFmpeg streaming process with: {subprocess.list2cmdline(stream_cmd)}")
        subprocess.run(stream_cmd,
                       stdout=self.wfile,  # connect stdout to TCP socket
                       stderr=subprocess.DEVNULL,
                       check=True)
      except subprocess.CalledProcessError as e:
        # peer probably disconnected
        logger.warning(f"Command '{subprocess.list2cmdline(stream_cmd)}' returned {e.returncode}")
      finally:
        self.server.connection_sem.release()
    else:
      logger.warning("A client is already connected, dropping this connection")


class StreamingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

  """ Streaming server. """

  allow_reuse_address = True

  def __init__(self, sdp_filepath):
    self.sdp_filepath = sdp_filepath
    self.connection_sem = threading.BoundedSemaphore(value=1)
    super().__init__(("0.0.0.0", STREAMING_SERVER_PORT), StreamingServerRequestHandler)


class StreamingServerThread(threading.Thread):

  """ Streaming server thread. """

  def __init__(self, server):
    self.server = server

    self.logger = logging.getLogger("streaming server")

    super().__init__(daemon=True, name=__class__.__name__)

  def run(self):
    self.logger.info(f"TCP server started, serving on port {STREAMING_SERVER_PORT}, connect to it with 'ffplay tcp://IP:{STREAMING_SERVER_PORT}'")

    self.server.serve_forever()


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
  arg_parser.add_argument("-c",
                          "--noise-command",
                          default=None,
                          help="""Command to run when chicken noise is detected.""")
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
    logging_formatter = colored_logging.ColoredFormatter(fmt="%(asctime)s %(levelname)s %(threadName)s [%(name)s] %(message)s")
  else:
    # assume systemd service in 'simple' mode
    logging_formatter = logging.Formatter(fmt="%(levelname)s %(threadName)s [%(name)s] %(message)s")
  logging_handler = logging.StreamHandler()
  logging_handler.setFormatter(logging_formatter)
  logging.getLogger().addHandler(logging_handler)

  with tempfile.TemporaryDirectory(prefix="%s_" % (os.path.splitext(os.path.basename(inspect.getfile(inspect.currentframe())))[0])) as tmp_dir:
    # ffmpeg capture
    # TODO don't hardcode audio input parameters (ie. channel count)
    # TODO don't hardcode video input parameters (ie. res, fps...)
    # TODO don't hardcode audio encoding parameters
    # TODO don't hardcode video encoding parameters
    # TODO optional hqdn3d filter
    logger = logging.getLogger("capture")
    sdp_filepath = os.path.join(tmp_dir, "av.sdp")
    capture_cmd = ["ffmpeg", "-loglevel", "quiet",
                   "-re",
                   "-f", args.video_source[0], "-input_format", "mjpeg", "-i", args.video_source[1],
                   "-f", args.audio_source[0], "-ar", "48k", "-ac", "1", "-i", args.audio_source[1],
                   "-sdp_file", sdp_filepath,
                   # unfortunately, mpegts or rtp can not transport raw video reliably, so we have to transcode video early
                   "-map", "0:v", "-c:v", "libxvid", "-qscale", "4", "-f", "rtp", f"rtp://127.0.0.1:{LOCAL_UDP_PORT_VIDEO}",
                   "-map", "1:a", "-c:a", "pcm_s16le", "-f", "s16le", f"udp://127.0.0.1:{LOCAL_UDP_PORT_AUDIO}",
                   "-map", "1:a", "-c:a", "copy", "-f", "wav", "-"]
    logger.info(f"Running FFmpeg capture process with: {subprocess.list2cmdline(capture_cmd)}")
    capture_process = subprocess.Popen(capture_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert(capture_process.poll() is None)

    # streaming server thread
    streaming_server = StreamingServer(sdp_filepath)
    streaming_server_thread = StreamingServerThread(streaming_server)
    streaming_server_thread.start()

    # noise detection thread
    nd_thread = NoiseDetectionThread(capture_process=capture_process,
                                     noise_name="chicken",
                                     db_limit=-10,
                                     profile_path="sounds/ambient_profile",
                                     on_noise_command=args.noise_command)
    nd_thread.start()
    try:
      nd_thread.join()
    except KeyboardInterrupt:
      logger.warning("Catched SIGINT, existing")
      pass

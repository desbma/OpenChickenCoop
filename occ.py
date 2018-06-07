#!/usr/bin/env python3

""" Open Chicken Coop. """

import argparse
import logging
import sys

import colored_logging


if __name__ == "__main__":
  # parse args
  arg_parser = argparse.ArgumentParser(description=__doc__,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  arg_parser.add_argument("-t",
                          "--audio-type",
                          choices=("alsa", "pulseaudio"),
                          required=True,
                          help="Audio source type")
  arg_parser.add_argument("-s",
                          "--audio-source",
                          required=True,
                          help="Audio source device. Identify with 'arecord -L' for alsa, or 'pacmd list-sources' for pulseaudio")
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

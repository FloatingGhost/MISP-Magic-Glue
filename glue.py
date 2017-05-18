import os
import zmq
import sys
import json
import pymisp
import warnings
from pyaml import yaml
import logging
import argparse

class GlueError(Exception):
    pass

# Set up logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Create argparser
parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument("-c", "--config", default="misp-glue.yaml", help="Config file location")

args = parser.parse_args()

log.debug("Parsed arguments")

try:
    log.debug("Trying to read config file %s", args.config)
    with open(args.config, "r") as f:
        config = yaml.load(f.read())
except FileNotFoundError:
    raise GlueError("Could not load config file at {}".format(args.config))
except PermissionError:
    raise GlueError("Could not read config file {} :: PERMISSIONS ERROR".format(args.config))

if not config:
    raise GlueError("I think your YAML is invalid!")

# Set up our ZMQ socket to recieve MISP JSON on publish
context = zmq.Context()
socket = context.socket(zmq.SUB)

log.info("Subscribing to tcp://%s:%s", config["zmq"]["host"], config["zmq"]["port"])

# Connect to the socket
socket.connect("tcp://{}:{}".format(
                                    config["zmq"]["host"],
                                    config["zmq"]["port"]
                                    ))
# Set the option to subscribe
socket.setsockopt_string(zmq.SUBSCRIBE, '')

while True:
    # Wait for something to come in on the ZMQ socket
    message = socket.recv().decode("utf-8")[10:]

    log.info("Recieved a message!")
    log.debug("Processing...")

    # Load the message JSON
    msg = json.loads(message)

    log.debug(msg)

    # Load it as a misp object
    ev = pymisp.mispevent.MISPEvent()
    ev.load(msg)


import os
import zmq
import sys
import json
import pymisp
import warnings
from pyaml import yaml
import logging
import argparse
import requests
from urllib.parse import urljoin

class GlueError(Exception):
    pass

# Set up logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Create argparser
parser = argparse.ArgumentParser(description='Run a glue process between MISP and MISP-Modules')
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

# Get MISP-Modules mod list
log.info("Connecting to Modules server at http://%s:%s", config["misp"]["modules"]["host"],
                                                         config["misp"]["modules"]["port"])
modulesURL = "http://{}:{}".format(config["misp"]["modules"]["host"],
                                   config["misp"]["modules"]["port"])

modules = requests.get(urljoin(modulesURL, "modules")).json()
configModules = config["misp"]["modules"]["run-modules"]
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

    # For each attribute in the event
    for attrib in ev.attributes:

        # Extract the type and value
        type_ = attrib.type
        value = attrib.value
    
        # Figure out what we can run with this type
        allowedModules = []

        for mod in modules:
            # First check if the type is right
            if "input" in mod["mispattributes"] and type_ in mod["mispattributes"]["input"]:
                # Then check if the user is OK with running it
                if configModules == ["ALL"] or mod["name"] in configModules:
                    allowedModules.append(mod) 
    
        # Run all the modules
        for mod in allowedModules:
            # Run the module 
            payload = {
                "module": mod["name"],
                type_ : value
            }

            # Extract any additional config
            if mod["name"] in config.get("additional-config", []):
                payload["config"] = config["additional-config"][mod["name"]]

            # Send off the request
            req = requests.post(urljoin(modulesURL, "query"), data=json.dumps(payload))

            output = req.json()
    
            print(output)

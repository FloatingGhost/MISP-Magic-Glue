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


# Create argparser
parser = argparse.ArgumentParser(description='Run a glue process between MISP and MISP-Modules')
parser.add_argument("-c", "--config", default="misp-glue.yaml", help="Config file location")
parser.add_argument("-v", "--verbose", default=False, action="store_true")

args = parser.parse_args()

# Set up logger
logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
log = logging.getLogger(__name__)

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

api = pymisp.PyMISP(config["misp"]["url"], config["misp"]["apikey"])

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
            if "expansion" in mod["meta"].get("module-type", []):
                if "input" in mod["mispattributes"] and type_ in mod["mispattributes"]["input"]:
                    # Then check if the user is OK with running it
                    if configModules == ["ALL"] or mod["name"] in configModules:
                        allowedModules.append(mod) 
    
        # Run all the modules
        log.debug("Allowed Modules %s", [x["name"] for x in allowedModules])

        for mod in allowedModules:
            log.info("Running %s", mod)
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
        
            log.debug("RECV %s", output)
        
            if "error" not in output:
                for result in output["results"]:
                    for value in result["values"]:
                        log.debug("Adding %s:%s", result["types"][0], value)
                        ev.add_attribute(result["types"][0], value)
            else:
                log.fatal(output["error"])

            log.debug("Sending event update")
            api.update_event(ev.id, ev)            

            log.debug("OK")

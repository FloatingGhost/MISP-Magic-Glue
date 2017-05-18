# MAGIC GLUUUUEE

CURRENTLY BUGGY: Will run into an infinite loop upon updating an event

## Installation

First, go install MISP-Modules, and make sure ZMQ is all switched on and stuff

```bash
cp misp-glue.default.yaml misp-glue.yaml

vim misp-glue.yaml
```

Modify the settings as needed.

- zmq: The zmq server settings, needs `host` and `port`
- misp: MISP API connection settings. Needs `url`, `apikey`
  - modules: MISP-modules connection settings. Needs `host`, `port`, `run-modules`
    - run-modules: This is a list of allowed modules, use the *exact* name as reported by `curl <modules>/query`. Leave as `- "ALL"` to enable all modules.
- additional-config: For module-specific settings. Add an entry using the exact module name, and set as needed.

The run `python3 glue.py` and leave it! When an event is published, the service will pick up the event, run any allowed modules, and then add them to the misp event.

## Assumptions
- Assumes MISP-Modules server to be accessable from the script's running location


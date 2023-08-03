import glob
import json
import os
from os.path import *

import sys

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, os.path.join(dir_module, "src/build/python"))

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

sys.path.insert(0, os.path.join(DIR_ROOT, "../.."))

from fabfile import _get_modules_all

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    # Build metadata publish JSON
    metadata_monitor_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Monitor") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_entity_metadata("monitor", DIR_ROOT, metadata_monitor_df)

    metadata_monitor_path = abspath(join(DIR_ROOT, "src/main/resources/config/services.json"))
    with open(metadata_monitor_path, 'w') as metadata_monitor_file:
        metadata_monitor_file.write(json.dumps(_get_modules_all("docker-compose.yml"), indent=2))
    print("Build generate script [monitor] service metadata persisted to [{}]".format(metadata_monitor_path))

import glob
import json
from os.path import *

import sys

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
for dir_module in glob.glob(join(DIR_ROOT, "../../*/*")):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, join(dir_module, "src/build/python"))

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

sys.path.insert(0, abspath(join(DIR_ROOT, "../../..")))

from fabfile import _get_modules_all

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    # Build metadata publish JSON
    metadata_supervisor_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Supervisor") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_entity_metadata("supervisor", DIR_ROOT, metadata_supervisor_df)

    metadata_supervisor_path = abspath(join(DIR_ROOT, "src/main/resources/config/services.json"))
    with open(metadata_supervisor_path, 'w') as metadata_supervisor_file:
        metadata_supervisor_file.write(json.dumps(_get_modules_all("docker-compose.yml"), indent=2))
    print("Build generate script [supervisor] service metadata persisted to [{}]".format(metadata_supervisor_path))

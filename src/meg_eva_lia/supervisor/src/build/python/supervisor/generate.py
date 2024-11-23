import json
from os.path import *

from fabfile import _get_modules_by_hosts
from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

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
    write_entity_metadata("supervisor", join(DIR_ROOT, "src/main/resources/config/mqtt"), metadata_supervisor_df,
                          "homeassistant/+/supervisor/#", "asystem/supervisor/#")

    metadata_supervisor_path = abspath(join(DIR_ROOT, "src/main/resources/config/services.json"))
    with open(metadata_supervisor_path, 'w') as metadata_supervisor_file:
        metadata_supervisor_file.write(json.dumps(_get_modules_by_hosts("docker-compose.yml"), indent=2))
    print("Build generate script [supervisor] service metadata persisted to [{}]".format(metadata_supervisor_path))

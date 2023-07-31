import glob
import os
import sys
from os.path import *
import json

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    # Build metadata publish JSON
    metadata_digitemps_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "DigiTemp") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    write_entity_metadata("digitemp", DIR_ROOT, metadata_digitemps_df)

    metadata_digitemps_dicts = []
    for _, row in metadata_digitemps_df.iterrows():
        metadata_digitemps_dicts.append(row[[
            "unique_id",
            "connection_mac",
        ]].dropna().to_dict())

    metadata_digitemp_dicts = [row.dropna().to_dict() for index, row in metadata_digitemps_df.iterrows()]
    metadata_digitemp_path = abspath(join(DIR_ROOT, "src/main/resources/config/sensors.json"))
    with open(metadata_digitemp_path, 'w') as metadata_digitemp_file:
        metadata_digitemp_file.write(json.dumps(metadata_digitemps_dicts, indent=2))

import glob
import os
import sys
from os.path import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
for dir_module in glob.glob(join(DIR_ROOT, "../../*/*")):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, join(dir_module, "src/build/python"))

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    # Build metadata publish JSON
    metadata_publish_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Internet") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0)
        ]
    write_entity_metadata("internet", join(DIR_ROOT, "src/main/resources/config/mqtt"), metadata_publish_df,
                          "homeassistant/+/internet/#", "telegraf/+/internet/#")

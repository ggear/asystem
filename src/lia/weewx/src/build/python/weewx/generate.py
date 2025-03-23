from os.path import *

import pandas as pd

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    metadata_weewx_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "WeeWX") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["unique_id_device"].str.len() > 0)
        ]
    metadata_weewx_dicts = [row.dropna().to_dict() for index, row in metadata_weewx_df.iterrows()]
    metadata_weewx_str = "[[[inputs]]]\n"
    for metadata_weewx_dict in metadata_weewx_dicts:
        metadata_weewx_str += ("            " + """
            [[[[{}]]]]
                name = {}        
              """.format(
            metadata_weewx_dict["unique_id_device"],
            metadata_weewx_dict["unique_id"]
        ).strip() + "\n")
    weewx_conf_path = join(DIR_ROOT, "src/main/resources/image/config/weewx.conf")
    with open(weewx_conf_path + ".template", "rt") as weewx_conf_template_file:
        with open(weewx_conf_path, "wt") as weewx_conf_file:
            for line in weewx_conf_template_file:
                weewx_conf_file.write(line.replace('$INPUTS_METADATA', metadata_weewx_str))
    print("Build generate script [weewx] entity metadata persisted to [{}]".format(weewx_conf_path))

    # Build metadata publish JSON
    metadata_publish_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "WeeWX") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0)
        ]
    write_entity_metadata("weewx", join(DIR_ROOT, "src/main/resources/image/config/mqtt"),
                          metadata_publish_df, "homeassistant/+/weewx/#", "weewx/#")

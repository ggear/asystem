import glob
import json
import os
import shutil
import sys
import pandas as pd

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_entity_metadata

pd.options.mode.chained_assignment = None

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
            metadata_weewx_dict["unique_id"].replace("compensation_sensor_", "")
        ).strip() + "\n")
    weewx_conf_path = os.path.join(DIR_ROOT, "src/main/resources/config/weewx.conf")
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
    metadata_publish_df["name"] = metadata_publish_df["name"].str.replace("compensation_sensor_", "")
    metadata_publish_df["unique_id"] = metadata_publish_df["unique_id"].str.replace("compensation_sensor_", "")
    metadata_publish_df["state_topic"] = metadata_publish_df["state_topic"].str.replace("compensation_sensor_", "")
    metadata_publish_df["discovery_topic"] = metadata_publish_df["discovery_topic"].str.replace("compensation_sensor_", "")
    metadata_device_columns = [column for column in metadata_publish_df.columns
                               if (column.startswith("device_") and column != "device_class")]
    metadata_device_columns_rename = {column: column.replace("device_", "") for column in metadata_device_columns}
    metadata_publish_dir_root = os.path.join(DIR_ROOT, "src/main/resources/config/mqtt")
    if os.path.exists(metadata_publish_dir_root):
        shutil.rmtree(metadata_publish_dir_root)
    for index, row in metadata_publish_df.iterrows():
        metadata_publish_dict = row[[
            "unique_id",
            "name",
            "state_class",
            "unit_of_measurement",
            "device_class",
            "icon",
            "force_update",
            "state_topic",
            "value_template",
            "qos",
        ]].dropna().to_dict()
        metadata_publish_dict["device"] = \
            row[metadata_device_columns].rename(metadata_device_columns_rename).dropna().to_dict()
        metadata_publish_dir = os.path.abspath(os.path.join(metadata_publish_dir_root, row['discovery_topic']))
        os.makedirs(metadata_publish_dir)
        metadata_publish_str = json.dumps(metadata_publish_dict, ensure_ascii=False)
        metadata_publish_path = os.path.abspath(os.path.join(metadata_publish_dir, metadata_publish_dict["unique_id"] + ".json"))
        with open(metadata_publish_path, 'a') as metadata_publish_file:
            metadata_publish_file.write(metadata_publish_str)
            print("Build generate script [weewx] entity metadata [sensor.{}] persisted to [{}]"
                  .format(metadata_publish_dict["unique_id"], metadata_publish_path))

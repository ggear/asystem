import glob
import json
import os
import shutil
import sys

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_entity_metadata

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
            print("Build generate script [internet] entity metadata [sensor.{}] persisted to [{}]"
                  .format(metadata_publish_dict["unique_id"], metadata_publish_path))

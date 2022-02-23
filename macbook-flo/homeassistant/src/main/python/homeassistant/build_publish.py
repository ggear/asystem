from __future__ import print_function

import json
import os
import shutil
import subprocess
import sys

DIR_MODULE_ROOT = os.path.abspath("{}/..".format(os.path.dirname(os.path.realpath(__file__))))
DIR_ROOT = os.path.abspath("{}/../../../../".format(DIR_MODULE_ROOT))
sys.path.insert(0, DIR_MODULE_ROOT)

from build import load_env
from build import load_entity_metadata

if __name__ == "__main__":
    env = load_env()
    metadata_df = load_entity_metadata()

    # Build metadata publish JSON
    metadata_publish_df = metadata_df[
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["index"] > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0)
        ]
    metadata_publish_dicts = [row.dropna().to_dict() for index, row in metadata_publish_df[[
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
    ]].iterrows()]
    metadata_device_columns = [column for column in metadata_publish_df.columns
                               if (column.startswith("device_") and column != "device_class")]
    metadata_device_columns_rename = {column: column.replace("device_", "") for column in metadata_device_columns}
    metadata_device_pub_dicts = [row.dropna().to_dict() for index, row in
                                 metadata_publish_df[metadata_device_columns]
                                     .rename(columns=metadata_device_columns_rename).iterrows()]
    metadata_publish_dir = os.path.abspath(os.path.join(DIR_MODULE_ROOT, "../resources/entity_metadata"))
    if os.path.exists(metadata_publish_dir):
        shutil.rmtree(metadata_publish_dir)
    os.makedirs(metadata_publish_dir)
    for index, metadata_publish_dict in enumerate(metadata_publish_dicts):
        metadata_publish_dict["device"] = metadata_device_pub_dicts[index]
        metadata_publish_str = json.dumps(metadata_publish_dict, ensure_ascii=False).encode('utf8')
        metadata_publish_path = os.path.abspath(os.path.join(metadata_publish_dir, metadata_publish_dict["unique_id"] + ".json"))
        with open(metadata_publish_path, 'a') as metadata_publish_file:
            metadata_publish_file.write(metadata_publish_str)
            print("Build script [homeassistant] entity metadata [sensor.{}] persisted to [{}]"
                  .format(metadata_publish_dict["unique_id"], metadata_publish_path))

    subprocess.call(['bash', os.path.join(DIR_MODULE_ROOT, '../resources/entity_metadata_publish.sh')])
    print("Build script [homeassistant] entity metadata published")

import glob
import os
import sys

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_entity_metadata

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    metadata_wrangle_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["unique_id_device"].str.len() > 0) &
        (metadata_df["device_via_device"] == "Wrangle")
        ]
    metadata_wrangle_dicts = [row.dropna().to_dict() for index, row in metadata_wrangle_df.iterrows()]
    wrangle_conf_path = os.path.join(DIR_ROOT, "src/main/resources/config/mqtt_metadata.csv")
    for metadata_wrangle_dict in metadata_wrangle_dicts:
        # TODO: Provide implementation
        print(metadata_wrangle_dict)

    print("Build generate script [wrangle] entity metadata persisted to [{}]".format(wrangle_conf_path))
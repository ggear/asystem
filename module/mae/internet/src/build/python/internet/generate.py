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

    metadata_internet_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["unique_id_device"].str.len() > 0) &
        (metadata_df["device_via_device"] == "Internet") &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    internet_conf_path = os.path.join(DIR_ROOT, "src/main/resources/mqtt_metadata.csv")
    metadata_internet_df.to_csv(internet_conf_path, index=False)
    print("Build generate script [internet] entity metadata persisted to [{}]".format(internet_conf_path))
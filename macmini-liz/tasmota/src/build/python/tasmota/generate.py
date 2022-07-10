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

    metadata_sonoff_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Sonoff") &
        (metadata_df["device_name"].str.len() > 0)
        ]
    metadata_sonoff_dicts = [row.dropna().to_dict() for index, row in metadata_sonoff_df.iterrows()]
    sonoff_device_backup_type = "dmp"
    for device_dict in metadata_sonoff_dicts:
        sonoff_device_path = os.path.join(DIR_ROOT, "src/build/resources", device_dict["device_name"])
        os.system("decode-config.py -s {} --backup-type {} --backup-file {}".format(device_dict["device_name"], sonoff_device_backup_type, sonoff_device_path))
        print("Build generate script [sonoff] device config persisted to [{}.{}]".format(sonoff_device_path, sonoff_device_backup_type))

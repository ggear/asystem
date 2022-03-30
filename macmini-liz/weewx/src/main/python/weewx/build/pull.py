import glob
import os
import sys

DIR_MODULE_ROOT = os.path.abspath("{}/../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/*/*/".format("{}/../../../../../../..".format(os.path.dirname(os.path.realpath(__file__))))):
    if dir_module.split("/")[-2] == "homeassistant":
        sys.path.insert(0, "{}/src/main/python".format(dir_module))
sys.path.insert(0, DIR_MODULE_ROOT)

from homeassistant.build.pull import load_entity_metadata

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
    weewx_conf_path = os.path.join(DIR_MODULE_ROOT, "../../../src/main/resources/config/weewx.conf")
    with open(weewx_conf_path + ".template", "rt") as weewx_conf_template_file:
        with open(weewx_conf_path, "wt") as weewx_conf_file:
            for line in weewx_conf_template_file:
                weewx_conf_file.write(line.replace('$INPUTS_METADATA', metadata_weewx_str))
    print("Build script [weewx] entity metadata persisted to [{}]".format(weewx_conf_path))

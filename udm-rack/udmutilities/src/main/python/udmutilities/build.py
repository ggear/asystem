import glob
import os
import sys

DIR_MODULE_ROOT = os.path.abspath("{}/..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/*/*/".format("{}/../../../../../..".format(os.path.dirname(os.path.realpath(__file__))))):
    if dir_module.split("/")[-2] == "homeassistant":
        sys.path.insert(0, "{}/src/main/python".format(dir_module))
sys.path.insert(0, DIR_MODULE_ROOT)

from homeassistant.build import load_entity_metadata

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    metadata_udmutilities_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0) &
        (metadata_df["connection_ip"].str.len() > 0)
        ]
    metadata_udmutilities_df = metadata_udmutilities_df.set_index(
        metadata_udmutilities_df["connection_ip"].str.split(".").str[-1]).sort_index()
    metadata_udmutilities_dicts = [row.dropna().to_dict() for index, row in metadata_udmutilities_df.iterrows()]
    dnsmasq_conf_path = os.path.join(DIR_MODULE_ROOT, "../../../src/main/resources/config/dhcp.janeandgraham.com.conf")
    with open(dnsmasq_conf_path, "w") as dnsmasq_conf_file:
        for metadata_udmutilities_dict in metadata_udmutilities_dicts:
            dnsmasq_conf_file.write("dhcp-host=set:net_LAN_br0_192-168-1-0-24,{},{},{}\n".format(
                metadata_udmutilities_dict["connection_mac"],
                metadata_udmutilities_dict["connection_ip"],
                metadata_udmutilities_dict["device_name"],
            ))
            print("Build script [udmutilities] host [{}] with IP [{}] defined".format(
                metadata_udmutilities_dict["device_name"],
                metadata_udmutilities_dict["connection_ip"],
            ))
    print("Build script [udmutilities] dnsmasq config persisted to [{}]".format(dnsmasq_conf_path))

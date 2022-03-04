import glob
import os
import sys

import pandas as pd

pd.options.mode.chained_assignment = None

DIR_MODULE_ROOT = os.path.abspath("{}/..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/*/*/".format("{}/../../../../../..".format(os.path.dirname(os.path.realpath(__file__))))):
    if dir_module.split("/")[-2] == "homeassistant":
        sys.path.insert(0, "{}/src/main/python".format(dir_module))
sys.path.insert(0, DIR_MODULE_ROOT)

from homeassistant.build import load_entity_metadata

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"

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

    dnsmasq_conf_root_path = os.path.join(DIR_MODULE_ROOT, "../../../src/main/resources/config/udm-dnsmasq")
    for dnsmasq_conf_path in glob.glob(os.path.join(dnsmasq_conf_root_path, "{}*".format(DNSMASQ_CONF_PREFIX))):
        os.remove(dnsmasq_conf_path)

    for vlan in metadata_udmutilities_df["connection_vlan"].unique():
        metadata_udmutilities_vlan_df = metadata_udmutilities_df[(metadata_udmutilities_df["connection_vlan"] == vlan)]
        metadata_udmutilities_vlan_df = metadata_udmutilities_vlan_df.set_index(
            metadata_udmutilities_vlan_df["connection_ip"].str.split(".").str[3].apply(lambda x: '{0:0>3}'.format(x))
        ).sort_index()
        metadata_udmutilities_dicts = [row.dropna().to_dict() for index, row in metadata_udmutilities_vlan_df.iterrows()]
        dnsmasq_conf_path = os.path.join(DIR_MODULE_ROOT, dnsmasq_conf_root_path, "{}-{}-custom.conf".format(
            DNSMASQ_CONF_PREFIX,
            vlan.replace("net", "vlan" + vlan.split("_")[2].replace("br", ""))
        ))
        with open(dnsmasq_conf_path, "w") as dnsmasq_conf_file:
            for metadata_udmutilities_dict in metadata_udmutilities_dicts:
                dnsmasq_conf_file.write("dhcp-host=set:{},{},{},{}\n".format(
                    metadata_udmutilities_dict["connection_vlan"],
                    metadata_udmutilities_dict["connection_mac"],
                    metadata_udmutilities_dict["connection_ip"],
                    metadata_udmutilities_dict["device_name"],
                ))
                print("Build script [udmutilities] host [{}] with IP [{}] defined".format(
                    metadata_udmutilities_dict["device_name"],
                    metadata_udmutilities_dict["connection_ip"],
                ))
        print("Build script [udmutilities] dnsmasq config persisted to [{}]".format(dnsmasq_conf_path))

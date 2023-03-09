import glob
import os
import sys

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_env
from homeassistant.generate import load_modules
from homeassistant.generate import load_entity_metadata

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.janeandgraham.com:443"

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules()
    metadata_df = load_entity_metadata()

    metadata_dhcphosts_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["connection_vlan"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    dnsmasq_conf_root_path = os.path.join(DIR_ROOT, "src/main/resources/config/udm-dnsmasq")
    for dnsmasq_conf_path in glob.glob(os.path.join(dnsmasq_conf_root_path, "{}*".format(DNSMASQ_CONF_PREFIX))):
        os.remove(dnsmasq_conf_path)
    unifi_clients = {}
    unifi_session = requests.Session()
    unifi_server_up = True
    try:
        unifi_session.post('{}/api/auth/login'.format(UNIFI_CONTROLLER_URL), json={
            'username': env["UNIFI_ADMIN_USER"],
            'password': env["UNIFI_ADMIN_KEY"]
        }, verify=False).raise_for_status()
        unifi_clients_response = unifi_session.get('{}/proxy/network/api/s/default/list/user'.format(UNIFI_CONTROLLER_URL), verify=False)
    except:
        unifi_server_up = False
    if not unifi_server_up or unifi_clients_response.status_code != 200:
        print("Build generate script [udmutilities] could not connect to UniFi")
    else:
        for unifi_client in unifi_clients_response.json()['data']:
            unifi_clients[unifi_client["mac"]] = unifi_client["name"] if "name" in unifi_client else (
                unifi_client["hostname"] if "hostname" in unifi_client else "")
        unifi_clients_response = unifi_session.get('{}/proxy/network/api/s/default/stat/device'.format(UNIFI_CONTROLLER_URL), verify=False)
        if unifi_clients_response.status_code != 200:
            print("Build generate script [udmutilities] could not connect to UniFi")
        else:
            for unifi_client in unifi_clients_response.json()['data']:
                unifi_clients[unifi_client["mac"]] = unifi_client["name"] if "name" in unifi_client else ""
    metadata_dhcphosts_hosts = {}
    metadata_dhcphosts_dnsmasq = {}
    metadata_dhcphosts_df = metadata_dhcphosts_df.fillna('')
    for vlan in metadata_dhcphosts_df["connection_vlan"].unique():
        metadata_dhcphosts_vlan_df = metadata_dhcphosts_df[(metadata_dhcphosts_df["connection_vlan"] == vlan)]
        metadata_dhcphosts_vlan_df = metadata_dhcphosts_vlan_df.set_index(
            metadata_dhcphosts_vlan_df["connection_ip"].str.split(".").str[3].apply(lambda x: '{0:0>3}'.format(x))
        ).sort_index()
        metadata_dhcphosts_dicts = [row.dropna().to_dict() for index, row in metadata_dhcphosts_vlan_df.iterrows()]
        dnsmasq_conf_path = os.path.join(dnsmasq_conf_root_path, "{}-{}-custom.conf".format(
            DNSMASQ_CONF_PREFIX,
            vlan.replace("net", "vlan" + vlan.split("_")[2].replace("br", "")) if len(vlan) > 0 else "vlanX"
        ))
        metadata_dhcphosts_dnsmasq[dnsmasq_conf_path] = []
        for metadata_dhcphosts_dict in metadata_dhcphosts_dicts:
            metadata_dhcphosts_dnsmasq[dnsmasq_conf_path].append("dhcp-host={},{}{}\n".format(
                metadata_dhcphosts_dict["connection_mac"],
                (metadata_dhcphosts_dict["connection_ip"] + ",")
                if "connection_ip" in metadata_dhcphosts_dict and len(metadata_dhcphosts_dict["connection_ip"]) > 0 else "",
                metadata_dhcphosts_dict["device_name"],
            ))
            if "connection_ip" in metadata_dhcphosts_dict and len(metadata_dhcphosts_dict["connection_ip"]) > 0:
                if metadata_dhcphosts_dict["device_name"] not in metadata_dhcphosts_hosts:
                    metadata_dhcphosts_hosts[metadata_dhcphosts_dict["device_name"]] = \
                        [metadata_dhcphosts_dict["connection_ip"]]
                else:
                    metadata_dhcphosts_hosts[metadata_dhcphosts_dict["device_name"]] \
                        .append(metadata_dhcphosts_dict["connection_ip"])
    for dnsmasq_conf_path in metadata_dhcphosts_dnsmasq:
        with open(dnsmasq_conf_path, "w") as dnsmasq_conf_file:
            for metadata_dhcphosts_dnsmasq_line in metadata_dhcphosts_dnsmasq[dnsmasq_conf_path]:
                dnsmasq_conf_file.write(metadata_dhcphosts_dnsmasq_line)
                mac = metadata_dhcphosts_dnsmasq_line.split("=")[1].split(",")[0].strip()
                name = metadata_dhcphosts_dnsmasq_line.split("=")[1].split(",")[-1].strip()
                if mac in unifi_clients:
                    if unifi_clients[mac] != name:
                        print(
                            "Build generate script [udmutilities] dnsmasq config host [{}] doesn't match UniFi alias [{}]".format(
                                name,
                                unifi_clients[mac],
                            ), file=sys.stderr)
                    else:
                        print(
                            "Build generate script [udmutilities] dnsmasq config host [{}] matches UniFi alias [{}]".format(
                                name,
                                unifi_clients[mac],
                            ))
                else:
                    print(
                        "Build generate script [udmutilities] dnsmasq config host [{}] not found in UniFi".format(
                            name,
                        ), file=sys.stderr)
        print("Build generate script [udmutilities] dnsmasq config persisted to [{}]".format(dnsmasq_conf_path))

    metadata_dhcphosts_ips = {}
    hosts_conf_path = os.path.join(DIR_ROOT, "src/main/resources/config/udm-utilities/run-pihole/custom.list")
    for metadata_dhcphosts_host in metadata_dhcphosts_hosts:
        metadata_dhcphosts_hosts[metadata_dhcphosts_host].sort()
        metadata_dhcphosts_ips[metadata_dhcphosts_hosts[metadata_dhcphosts_host][0]] = metadata_dhcphosts_host
    with open(hosts_conf_path, "w") as hosts_conf_file:
        for metadata_dhcphosts_ip in sorted(metadata_dhcphosts_ips):
            hosts_conf_file.write("{} {}.janeandgraham.com {}\n".format(
                metadata_dhcphosts_ip,
                metadata_dhcphosts_ips[metadata_dhcphosts_ip],
                metadata_dhcphosts_ips[metadata_dhcphosts_ip]
            ))

    metadata_dhcpaliases_path = os.path.abspath(os.path.join(dnsmasq_conf_root_path, "dhcp.dhcpServers-aliases.conf"))
    with open(metadata_dhcpaliases_path, 'w') as metadata_haas_file:
        for name in modules:
            if "{}_HTTP_PORT".format(name.upper()) in modules[name][1]:
                metadata_haas_file.write("cname={},{}.janeandgraham.com,{}\n".format(
                    name,
                    name,
                    modules["nginx"][0][0],
                ))

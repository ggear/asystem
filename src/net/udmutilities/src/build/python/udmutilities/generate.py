import glob
import os
import re
import sys
from os.path import *

import pandas as pd
import requests
import urllib3

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import load_env
from homeassistant.generate import load_modules
from homeassistant.generate import write_certificates

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.local.janeandgraham.com:443"

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules(load_disabled=False, load_infrastrcture=False)
    metadata_df = load_entity_metadata()

    write_certificates("udmutilities", join(DIR_ROOT, "src/main/resources/image/udm-certificates"))

    metadata_dhcp_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_identifiers"].str.len() > 0) &
        (metadata_df["connection_vlan"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    dnsmasq_conf_root_path = join(DIR_ROOT, "src/main/resources/image/udm-dnsmasq")
    metadata_dhcp_df = metadata_dhcp_df.fillna('')
    if not metadata_dhcp_df.loc[metadata_dhcp_df["connection_ip"] != '', :]["connection_ip"].is_unique:
        raise Exception("Build generate script [udmutilities] found non-unique IP addresses!")
    if not metadata_dhcp_df.loc[metadata_dhcp_df["connection_mac"] != '', :]["connection_mac"].is_unique:
        raise Exception("Build generate script [udmutilities] found non-unique MAC addresses!")
    for dnsmasq_conf_path in glob.glob(join(dnsmasq_conf_root_path, "{}*".format(DNSMASQ_CONF_PREFIX))):
        os.remove(dnsmasq_conf_path)
    unifi_mac_name = {}
    unifi_session = requests.Session()
    unifi_server_up = True
    try:
        unifi_session.post('{}/api/auth/login'.format(UNIFI_CONTROLLER_URL), json={
            'username': env["UNIFI_ADMIN_USER"],
            'password': env["UNIFI_ADMIN_KEY"]
        }, verify=False).raise_for_status()
        unifi_clients_response = unifi_session.get(
            '{}/proxy/network/api/s/default/list/user'.format(UNIFI_CONTROLLER_URL), verify=False)
    except:
        unifi_server_up = False
    if not unifi_server_up or unifi_clients_response.status_code != 200:
        print("Build generate script [udmutilities] could not connect to UniFi controller")
    else:
        for unifi_client in unifi_clients_response.json()['data']:
            unifi_mac_name[unifi_client["mac"]] = unifi_client["name"] if "name" in unifi_client else (
                unifi_client["hostname"] if "hostname" in unifi_client else "")
        unifi_devices_response = unifi_session.get(
            '{}/proxy/network/api/s/default/stat/device'.format(UNIFI_CONTROLLER_URL), verify=False)
        if unifi_devices_response.status_code != 200:
            print("Build generate script [udmutilities] could not connect to UniFi controller")
        else:
            for unifi_device in unifi_devices_response.json()['data']:
                unifi_mac_name[unifi_device["mac"]] = unifi_device["name"] if "name" in unifi_device else ""
    metadata_dhcp_ips = {}
    metadata_dhcp_hosts = {}
    metadata_dhcp_dnsmasq = {}
    for vlan in metadata_dhcp_df["connection_vlan"].unique():
        metadata_dhcp_vlan_df = metadata_dhcp_df[(metadata_dhcp_df["connection_vlan"] == vlan)]
        metadata_dhcp_vlan_df = metadata_dhcp_vlan_df.set_index(
            metadata_dhcp_vlan_df["connection_ip"].str.split(".").str[3].apply(lambda x: '{0:0>3}'.format(x))
        ).sort_index()
        metadata_dhcp_dicts = [row.dropna().to_dict() for index, row in metadata_dhcp_vlan_df.iterrows()]
        dnsmasq_conf_path = join(dnsmasq_conf_root_path, "{}-{}-custom.conf".format(DNSMASQ_CONF_PREFIX, vlan))
        metadata_dhcp_dnsmasq[dnsmasq_conf_path] = []
        for metadata_dhcp_dict in metadata_dhcp_dicts:
            metadata_dhcp_dnsmasq[dnsmasq_conf_path].append("dhcp-host={},{}{}\n".format(
                metadata_dhcp_dict["connection_mac"],
                metadata_dhcp_dict["device_identifiers"],
                ("," + metadata_dhcp_dict["connection_ip"]) \
                    if "connection_ip" in metadata_dhcp_dict and len(metadata_dhcp_dict["connection_ip"]) > 0 else "",
            ))
            if "connection_ip" in metadata_dhcp_dict and len(metadata_dhcp_dict["connection_ip"]) > 0:
                if metadata_dhcp_dict["device_identifiers"] not in metadata_dhcp_hosts:
                    metadata_dhcp_hosts[metadata_dhcp_dict["device_identifiers"]] = \
                        [metadata_dhcp_dict["connection_ip"]]
                else:
                    metadata_dhcp_hosts[metadata_dhcp_dict["device_identifiers"]] \
                        .append(metadata_dhcp_dict["connection_ip"])
    for dnsmasq_conf_path in metadata_dhcp_dnsmasq:
        with open(dnsmasq_conf_path, "w") as dnsmasq_conf_file:
            for metadata_dhcp_dnsmasq_line in metadata_dhcp_dnsmasq[dnsmasq_conf_path]:
                dnsmasq_conf_file.write(metadata_dhcp_dnsmasq_line)
                mac = metadata_dhcp_dnsmasq_line.split("=")[1].split(",")[0].strip()
                name = metadata_dhcp_dnsmasq_line.split("=")[1].split(",")[-1].strip()
                if mac in unifi_mac_name:
                    if unifi_mac_name[mac] != name and unifi_mac_name[mac] != "":
                        print("Build generate script [udmutilities] dnsmasq config "
                              "host [{}] doesn't match UniFi alias [{}]".format(
                            name,
                            unifi_mac_name[mac],
                        ), file=sys.stderr)
                    else:
                        print("Build generate script [udmutilities] dnsmasq config "
                              "host [{}] matches UniFi alias [{}]".format(
                            name,
                            unifi_mac_name[mac],
                        ))
                else:
                    if not re.match(r"u??\-.*", name):
                        print("Build generate script [udmutilities] dnsmasq config host [{}] not found in UniFi".format(
                            name,
                        ), file=sys.stderr)
        print("Build generate script [udmutilities] dnsmasq config persisted to [{}]".format(dnsmasq_conf_path))

    # INFO: Disable podman services since it has been deprecated since udm-pro-3
    # metadata_dhcp_ips = {}
    # hosts_conf_path = join(DIR_ROOT, "src/main/resources/image/udm-utilities/run-pihole/custom.list")
    # for metadata_dhcp_host in metadata_dhcp_hosts:
    #     metadata_dhcp_hosts[metadata_dhcp_host].sort()
    #     metadata_dhcp_ips[metadata_dhcp_hosts[metadata_dhcp_host][0]] = metadata_dhcp_host
    # with open(hosts_conf_path, "w") as hosts_conf_file:
    #     for metadata_dhcp_ip in sorted(metadata_dhcp_ips):
    #         hosts_conf_file.write("{} {}.janeandgraham.com {}\n".format(
    #             metadata_dhcp_ip,
    #             metadata_dhcp_ips[metadata_dhcp_ip],
    #             metadata_dhcp_ips[metadata_dhcp_ip]
    #         ))

    # INFO: Possible host and domain naming schemes:
    #
    # home.janeandgraham.com
    # homeassistant.janeandgraham.com
    # homeassistant.local.janeandgraham.com
    # homeassistant
    # macmini-meg.local.janeandgraham.com
    # macmini-meg.local
    # macmini-meg
    #
    # home.janeandgraham.com
    # homeassistant.janeandgraham.com
    # homeassistant.lan.janeandgraham.com
    # homeassistant
    # macmini-meg.lan.janeandgraham.com
    # macmini-meg.local
    # macmini-meg
    #
    # home.wan.janeandgraham.com
    # homeassistant.cdn.janeandgraham.com
    # homeassistant.lan.janeandgraham.com
    # homeassistant
    # macmini-meg.lan.janeandgraham.com
    # macmini-meg.local
    # macmini-meg
    #
    # home.public.janeandgraham.com
    # homeassistant.private.proxy.janeandgraham.com
    # homeassistant.private.service.janeandgraham.com
    # homeassistant
    # macmini-meg.private.host.janeandgraham.com
    # macmini-meg.local
    # macmini-meg

    metadata_dhcpaliases_path = abspath(join(dnsmasq_conf_root_path, "dhcp.dhcpServers-aliases.conf"))
    with open(metadata_dhcpaliases_path, 'w') as metadata_hass_file:
        for name in modules:

            if "{}_HTTP_PORT".format(name.upper()) in modules[name][1]:
                metadata_hass_file.write("cname={}.janeandgraham.com,{}\n".format(
                    name,
                    modules["nginx"][0][0],
                ))
            metadata_hass_file.write("cname={},{}.local.janeandgraham.com,{}\n".format(
                name,
                name,
                modules[name][0][0],
            ))

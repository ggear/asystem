from asystem import *

pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_bootstrap_env(DIR_ROOT)

    write_container_healthchecks(working_dir=join(DIR_ROOT, "src/main/resources/data"))

    write_container_backup()
    write_container_restore()

    hosts_path = join(DIR_ROOT, "src/main/resources/pushcerts-hosts.sh")
    os.makedirs(os.path.dirname(hosts_path), exist_ok=True)
    hosts_labels = {line.split("=")[0]: line.split("=")[-1].split(",") for line in Path(join(DIR_ROOT, "../../../.hosts")).read_text().strip().split("\n")}
    host_pull_label = os.path.basename(os.path.dirname(DIR_ROOT))
    with open(hosts_path, "w") as hosts_file:
        hosts_file.write("#!/bin/bash\n\n")
        for certificates_path in Path(os.path.join(DIR_ROOT, "../..")).rglob("certificates.sh"):
            certificates_path = os.path.abspath(certificates_path)
            certificates_path_tokens = certificates_path.split("/src/")
            if "/target/" not in certificates_path and len(certificates_path_tokens) > 2:
                module_tokens = certificates_path_tokens[1].split("/")
                group_path = Path(join(certificates_path_tokens[0], "src", certificates_path_tokens[1], ".group"))
                group = group_path.read_text().strip() if group_path.is_file() else ""
                if len(module_tokens) > 1 and group != "-1":
                    service_name = module_tokens[1]
                    host_pull = f"{hosts_labels[host_pull_label][0]}-{host_pull_label}"
                    host_push = f"{hosts_labels[module_tokens[0]][0]}-{module_tokens[0]}"
                    install_path = Path(certificates_path).relative_to(join(certificates_path_tokens[0], "src", certificates_path_tokens[1], "src/main/resources"))
                    script_path = f"/var/lib/asystem/install/{service_name}/latest/{install_path}"
                    hosts_file.write(
                        f"""
if ssh -n -q -o "StrictHostKeyChecking=no" root@{host_push} "{script_path} pull {host_pull} {host_push}" &&
  ssh -n -q -o "StrictHostKeyChecking=no" root@{host_push} "{script_path} push {host_pull} {host_push}"; then
  logger -t pushcerts "Pushed new certificates to [{host_push}]"
else
  logger -t pushcerts "Failed to push new certificates to [{host_push}]"
fi
                    """.strip()
                        + "\n"
                    )
    print(f"Build generate script [letsencrypt] entity metadata persisted to [{hosts_path}]")

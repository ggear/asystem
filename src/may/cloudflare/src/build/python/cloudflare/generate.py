from asystem import *

pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_bootstrap_env(DIR_ROOT)
    modules = load_bootstrap_modules()

    write_container_healthchecks(working_dir=join(DIR_ROOT, "src/main/resources/data"))

    resources = set()
    for name in modules:
        for key in modules[name][1]:
            if key.startswith("{}_HTTP_API_".format(name.upper())) and key.endswith("_CONTEXT"):
                resources.add(key[len("{}_HTTP_API_".format(name.upper())):-len("_CONTEXT")].lower())
    hostnames = [hostname.strip() for hostname in env["CLOUDFLARE_HOSTNAME"].split(",") if hostname.strip()]
    for hostname in hostnames:
        if hostname.split(".")[0] not in resources:
            raise ValueError("tunnel hostname [{}] matches no declared api resource of [{}]".format(hostname, sorted(resources)))

    config_path = abspath(join(DIR_ROOT, "src/main/resources/data/config.yml"))
    os.makedirs(dirname(config_path), exist_ok=True)
    with open(config_path, "w") as config_file:
        config_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
tunnel: {}
credentials-file: /asystem/etc/.credentials.json
metrics: 0.0.0.0:{}
ingress:
""".format(env["CLOUDFLARE_ID"], env["CLOUDFLARE_METRICS_PORT"]).strip() + "\n")
        for hostname in hostnames:
            config_file.write("""
  - hostname: {}
    service: https://{}:{}
""".format(hostname, hostname, env["CLOUDFLARE_ORIGIN_PORT"]).strip("\n") + "\n")
        config_file.write("  - service: http_status:404\n")
    print("Build generate script [cloudflare] entity metadata persisted to [{}]".format(config_path))

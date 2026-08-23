from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_bootstrap_env(DIR_ROOT)
    modules = load_bootstrap_modules(include_disabled=False, include_infrastructure=False)
    metadata_df = load_bootstrap_entities()

    write_container_bootstrap()
    write_container_healthchecks()
    write_container_certificates()

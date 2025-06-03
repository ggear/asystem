from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_bootstrap(working_dir=join(DIR_ROOT, "src/main/resources/data"))
    write_healthcheck()

import glob
import os
import sys

DIR_MODULE_ROOT = os.path.abspath("{}/../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/*/*/".format("{}/../../../../../../..".format(os.path.dirname(os.path.realpath(__file__))))):
    if dir_module.split("/")[-2] == "anode":
        sys.path.insert(0, "{}/src/main/python".format(dir_module))
sys.path.insert(0, DIR_MODULE_ROOT)

from anode.metadata.build import load
import subprocess

if __name__ == "__main__":
    sensors = load()

    # TODO: Provide implementation
    subprocess.call("./build.sh", cwd=DIR_MODULE_ROOT + "/../resources")

    print("Metadata script [grafana] dashboard saved")

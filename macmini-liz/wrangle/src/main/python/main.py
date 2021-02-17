from __future__ import print_function

import glob
import importlib
import os
import sys
import time

from wrangle import script


def main(arguments=[]):
    time_start = int(time.time())
    script.print_log("Wrangle", "Started")
    profile_loaded = None
    runtime_errors = 0
    try:
        with open(script.get_file(".profile") if len(arguments) <= 1 else arguments[1], 'r') as profile_file:
            profile_loaded = script.load_profile(profile_file)
    except Exception as exception:
        runtime_errors += 1
        script.print_log("Wrangle", "Error loading profile", exception)
    if profile_loaded is not None:
        for module_path in glob.glob("{}/wrangle/*/*.py".format(os.path.dirname(os.path.realpath(__file__)))):
            if not module_path.endswith("__init__.py"):
                module_name = os.path.basename(os.path.dirname(module_path))
                time_start_module = int(time.time())
                script.print_log(module_name.title(), "Started")
                module = getattr(importlib.import_module("wrangle.{}".format(module_name)), module_name.title())()
                module.run()
                module.print_counters()
                runtime_errors += (
                        module.get_counter(script.CTR_SRC_FILES, script.CTR_ACT_ERRORED) +
                        module.get_counter(script.CTR_SRC_DATA, script.CTR_ACT_ERRORED)
                )
                script.print_log(module_name.title(), "Completed in [{}] secs".format(int(time.time()) - time_start_module))
    script.print_log("Wrangle", "Completed in [{}] secs".format(int(time.time()) - time_start))
    return runtime_errors

if __name__ == "__main__":
    sys.exit(main(sys.argv))

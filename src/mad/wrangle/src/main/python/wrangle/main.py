import argparse
import glob
import importlib
import sys
import time
from os.path import *

from wrangle import plugin


def configure(argv=None):
    parser = argparse.ArgumentParser(
        prog="wrangle",
        description=(
            "Wrangle external data required by ASystem"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-o", "--once",
        action="store_true",
        help=(
            "force-reprocessing, log-debug, and run all plugins once and exit"
        ),
    )
    parser.add_argument(
        "-p", "--poll-period",
        type=int,
        default=30,
        metavar="MINUTES",
        help=(
            "run continuously, sleeping MINUTES between cycles (default: 30)"
        ),
    )
    parser.add_argument(
        "--force-reprocessing",
        action="store_true",
        help="flush each plugin's cached state and reprocess all files",
    )
    parser.add_argument(
        "--force-downloads",
        action="store_true",
        help="force all files to be re-downloaded even if cached",
    )
    parser.add_argument(
        "--disable-uploads",
        action="store_true",
        help="skip remote system uploads and write to local cache only",
    )
    parser.add_argument(
        "--disable-downloads",
        action="store_true",
        help="skip remote system downloads and read from local cache only",
    )
    parser.add_argument(
        "--drive-scope",
        choices=["production", "staging", "testing"],
        default="production",
        help="scope remote uploads and downloads (default: production)",
    )
    parser.add_argument(
        "-l", "--log",
        choices=["debug", "info", "warning", "error", "fatal"],
        default=None,
        help="logging verbosity (default: info; debug when --once is set)",
    )
    args = parser.parse_args(argv)
    if args.poll_period < 0:
        parser.error("argument -p/--poll-period: MINUTES must be >= 0")
    if args.once:
        args.force_reprocessing = True
    if args.log is None:
        args.log = "debug" if args.once else "info"
    plugin.config.log_level = args.log
    plugin.config.drive_scope = plugin.DataRepoScope(args.drive_scope)
    plugin.config.force_reprocessing = args.force_reprocessing
    plugin.config.force_downloads = args.force_downloads
    plugin.config.disable_uploads = args.disable_uploads
    plugin.config.disable_downloads = args.disable_downloads
    return args


def run_once():
    module_count = 0
    module_errored_count = 0
    plugin_dir = join(dirname(realpath(__file__)), "plugin")
    module_names = sorted(
        basename(module_path)
        for module_path in glob.glob(join(plugin_dir, "*"))
        if isdir(module_path) and not basename(module_path).startswith("_")
    )
    for module_name in module_names:
        module_count += 1
        module_errored = False
        module = None
        try:
            module_class = "".join(part.capitalize() for part in module_name.split("_"))
            module = getattr(importlib.import_module(f"wrangle.plugin.{module_name}"), module_class)()
            module.run()
            counters = module.get_counters()
            for source in counters:
                for action in counters[source]:
                    if action == plugin.CTR_ACT_ERRORED and counters[source][action] > 0:
                        module_errored = True
        except Exception as exception:
            if module is not None:
                module.print_log(
                    "Module threw unexpected exception",
                    exception=exception,
                )
            else:
                plugin.print_log(
                    module_name,
                    "Module failed to load or initialize",
                    exception=exception,
                )
            module_errored = True
        if module_errored:
            module_errored_count += 1
    return module_count != 0 and module_count > module_errored_count


def main(argv=None):
    args = configure(argv)
    try:
        plugin.database_open()
        while True:
            success = run_once()
            plugin.config.force_reprocessing = False
            if args.once or not args.poll_period:
                return success
            time.sleep(args.poll_period * 60)
    except KeyboardInterrupt:
        plugin.print_log(
            "wrangle",
            "Interrupted, exiting",
        )
        return True
    finally:
        plugin.database_close()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

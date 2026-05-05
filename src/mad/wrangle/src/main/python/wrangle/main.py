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
        "--repo-scope",
        choices=["production", "staging", "cache"],
        default="production",
        help="scope remote uploads and downloads (default: production)",
    )
    parser.add_argument(
        "--filter-plugins",
        default=None,
        metavar="CSV",
        help=(
            "run only plugins listed in CSV (example: balances,equity)"
        ),
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
    filter_plugins = None
    if args.filter_plugins is not None:
        filter_plugins = []
        for plugin_name in (name.strip() for name in args.filter_plugins.split(",")):
            if plugin_name and plugin_name not in filter_plugins:
                filter_plugins.append(plugin_name)
        available_plugins = set(_get_plugins())
        missing_plugins = [plugin_name for plugin_name in filter_plugins if plugin_name not in available_plugins]
        if missing_plugins:
            parser.error("\n".join(f"argument --filter-plugins: plugin '{plugin_name}' does not exist" for plugin_name in missing_plugins))
    args.filter_plugins = filter_plugins
    if args.once:
        args.force_reprocessing = True
    if args.log is None:
        args.log = "debug" if args.once else "info"
    plugin.config.log_level = args.log
    plugin.config.repo_scope = plugin.RepoScope(args.repo_scope)
    plugin.config.force_reprocessing = args.force_reprocessing
    plugin.config.force_downloads = args.force_downloads
    plugin.config.disable_uploads = args.disable_uploads
    plugin.config.disable_downloads = args.disable_downloads
    return args


def run_once(filter_plugins=None):
    plugin_count = 0
    plugin_errored_count = 0
    plugin_names = _get_plugins()
    if filter_plugins is not None:
        filter_plugin_set = set(filter_plugins)
        plugin_names = [plugin_name for plugin_name in plugin_names if plugin_name in filter_plugin_set]
    for plugin_name in plugin_names:
        plugin_count += 1
        plugin_errored = False
        plugin_instance = None
        try:
            plugin_class = "".join(part.capitalize() for part in plugin_name.split("_"))
            plugin_instance = getattr(importlib.import_module(f"wrangle.plugin.{plugin_name}"), plugin_class)()
            plugin_instance.run()
            counters = plugin_instance.get_counters()
            for source in counters:
                for action in counters[source]:
                    if action == plugin.CTR_ACT_ERRORED and counters[source][action] > 0:
                        plugin_errored = True
        except Exception as exception:
            if plugin_instance is not None:
                plugin_instance.print_log("Plugin threw unexpected exception", exception=exception)
            else:
                plugin.print_log(plugin_name, "Plugin failed to load or initialise", exception=exception)
            plugin_errored = True
        if plugin_errored:
            plugin_errored_count += 1
    return plugin_count != 0 and plugin_count > plugin_errored_count


def _get_plugins():
    plugin_dir = join(dirname(realpath(__file__)), "plugin")
    return sorted(
        basename(plugin_path)
        for plugin_path in glob.glob(join(plugin_dir, "*"))
        if isdir(plugin_path) and not basename(plugin_path).startswith("_")
    )


def main(argv=None):
    args = configure(argv)
    try:
        plugin.database_open()
        while True:
            success = run_once(filter_plugins=args.filter_plugins)
            plugin.config.force_reprocessing = False
            if args.once or not args.poll_period:
                return success
            time.sleep(args.poll_period * 60)
    except KeyboardInterrupt:
        plugin.print_log("wrangle", "Interrupted, exiting")
        return True
    finally:
        plugin.database_close()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

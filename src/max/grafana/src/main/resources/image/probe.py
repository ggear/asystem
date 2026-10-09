import glob
import os
import sys
from os.path import abspath, basename, dirname, join, realpath
from pathlib import Path
from typing import Any

import requests
import yaml

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_DASHBOARDS = join(DIR_ROOT, "src/main/resources/data/dashboards")
TIMEOUT = 120
POINTS = 500
SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "y": 31536000,
}

if __name__ == "__main__":
    # noinspection HttpUrlsUsage
    server = sys.argv[1] if len(sys.argv) > 1 else f"http://{os.environ['GRAFANA_SERVICE_PROD']}:{os.environ['GRAFANA_HTTP_PORT']}"
    dashboards = sys.argv[2] if len(sys.argv) > 2 else DIR_DASHBOARDS
    credentials = (os.environ["GRAFANA_USER"], os.environ["GRAFANA_TOKEN"])
    faults, probed = [], 0
    for path in sorted(glob.glob(join(dashboards, "generated/*.yaml")) + glob.glob(join(dashboards, "custom/*.yaml"))):
        resource = yaml.safe_load(Path(path).read_text())
        if resource.get("kind") != "Dashboard":
            continue
        start = resource["spec"]["timeSettings"]["from"]
        for element in resource["spec"]["elements"].values():
            group = element["spec"]["data"]["spec"]
            for query in group["queries"]:
                spec = query["spec"]["query"]
                probed += 1
                floor = group.get("queryOptions", {}).get("interval") or "1s"
                interval = max(int(floor[:-1]) * SECONDS[floor[-1]],
                               int(start[4:-1]) * SECONDS[start[-1]] // POINTS) * 1000
                result: dict[str, Any]
                try:
                    response = requests.post(f"{server}/api/ds/query", auth=credentials, timeout=TIMEOUT, json={
                        "from": start,
                        "to": "now",
                        "queries": [{
                            "refId": "A",
                            "datasource": {
                                "uid": spec["datasource"]["name"],
                            },
                            "intervalMs": interval,
                            "maxDataPoints": POINTS,
                            **spec["spec"],
                        }],
                    })
                    answer = response.json()
                    result = answer.get("results", {}).get("A") or {"error": answer.get("message") or f"status [{response.status_code}]"}
                except (requests.RequestException, ValueError) as error:
                    result = {"error": str(error)}
                frames = [frame for frame in result.get("frames", [])
                          if (frame.get("data", {}).get("values") or [[]])[0]]
                if result.get("error") or not frames:
                    faults.append((basename(path)[:-5], element["spec"]["title"], result.get("error") or "empty"))
    for dashboard, title, fault in faults:
        print(f"Probe fault dashboard [{dashboard}] panel [{title}] fault [{fault}]")
    print(f"Probe ran [{probed}] queries with [{len(faults)}] faults")
    sys.exit(1 if faults else 0)

"""The only tool an AI agent student uses: one command per call.

    python -m harness.student NAME open
    python -m harness.student NAME look
    python -m harness.student NAME click "56"
    python -m harness.student NAME type "Олена"
    python -m harness.student NAME wait 10
    python -m harness.student NAME reload
    python -m harness.student NAME offline 8
    python -m harness.student NAME close

Each call prints the step number, the time, and what is on the screen after
the command. The driver records the same step on its side.
"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("HARNESS_API", "http://127.0.0.1:8198")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    name, cmd = argv[0], argv[1]
    arg = " ".join(argv[2:]) if len(argv) > 2 else None
    payload = json.dumps({"student": name, "cmd": cmd, "arg": arg}).encode("utf-8")
    request = urllib.request.Request(API + "/cmd", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            print(response.read().decode("utf-8"))
            return 0
    except urllib.error.HTTPError as error:
        print(error.read().decode("utf-8"))
        return 1
    except urllib.error.URLError as error:
        print(f"The classroom is not running ({error.reason}).")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

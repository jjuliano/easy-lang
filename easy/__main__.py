"""Run an Easy program from a file or a link.

    python3 -m easy insertion.easy
    python3 -m easy https://github.com/jjuliano/datastructures/blob/main/session03-algorithms/easy/insertion.easy
"""

import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from easy.machine import EasyError, run

USAGE = """\
usage: python3 -m easy FILE
       python3 -m easy URL
       python3 -m easy --explain FILE

FILE is a program on your machine. URL is an http or https link.
A GitHub "blob" link is read as the file itself.
--explain, or -x, prints each step first. The program's own lines follow.
Install once with:
  curl -fsSL -A easy-lang https://raw.githubusercontent.com/jjuliano/easy-lang/main/install.py | python3

  python3 -m easy insertion.easy
  python3 -m easy --explain https://github.com/jjuliano/datastructures/blob/main/session03-algorithms/easy/search.easy
"""

MAX_BYTES = 1_000_000


def as_fetch_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.netloc == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 5 and parts[2] == "blob":
            user, repo, ref = parts[0], parts[1], parts[3]
            rest = "/".join(parts[4:])
            return f"https://raw.githubusercontent.com/{user}/{repo}/{ref}/{rest}"
    return url


def load_source(spec):
    fetch = as_fetch_url(spec)
    if fetch is None:
        path = Path(spec)
        if not path.is_file():
            raise EasyError(f"no such file {spec}")
        return path.read_text(encoding="utf-8")
    request = urllib.request.Request(fetch, headers={"User-Agent": "easy-lang"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(MAX_BYTES + 1)
    except urllib.error.URLError as exc:
        raise EasyError(f"could not fetch {spec}") from exc
    if len(payload) > MAX_BYTES:
        raise EasyError("program is too large")
    return payload.decode("utf-8")


def main(argv=None):
    if argv is None:
        argv = sys.argv
    explain = False
    specs = []
    for arg in argv[1:]:
        if arg in ("-x", "--explain"):
            explain = True
        elif arg in ("-h", "--help"):
            print(USAGE, file=sys.stderr, end="")
            return 0
        else:
            specs.append(arg)
    if len(specs) != 1:
        print(USAGE, file=sys.stderr, end="")
        return 2
    supplied = []
    if not sys.stdin.isatty():
        supplied = sys.stdin.read().split()
    try:
        source = load_source(specs[0])
        result = run(source, inputs=supplied, explain=explain)
    except EasyError as exc:
        print(f"easy: {exc}", file=sys.stderr)
        return 1
    if explain:
        for line in result.trace:
            print(line, file=sys.stderr)
    for line in result.output:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

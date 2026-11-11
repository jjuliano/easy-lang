import sys

from easy.machine import EasyError, run


def main(argv):
    if len(argv) != 2:
        print("usage: python -m easy program.easy", file=sys.stderr)
        return 2
    source = open(argv[1], encoding="utf-8").read()
    supplied = []
    if not sys.stdin.isatty():
        supplied = sys.stdin.read().split()
    try:
        result = run(source, inputs=supplied)
    except EasyError as exc:
        print(f"easy: {exc}", file=sys.stderr)
        return 1
    for line in result.output:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

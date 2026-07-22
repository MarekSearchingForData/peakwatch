"""PeakWatch CLI: py -m peakwatch <refresh|validate|allocate|all>"""
import sys

from . import collect, validate, allocator


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else "all"
    if verb in ("refresh", "all"):
        collect.refresh()
    if verb in ("validate", "all"):
        if not validate.validate() and verb == "all":
            sys.exit("stopping: validation failed")
    if verb in ("allocate", "all"):
        allocator.run_slice()


if __name__ == "__main__":
    main()

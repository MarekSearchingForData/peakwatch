"""PeakWatch CLI: py -m peakwatch <refresh|validate|analyze|allocate|experiment|all>"""
import sys

from . import collect, validate, allocator, analytics, experiments


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else "all"
    if verb in ("refresh", "all"):
        collect.refresh()
    if verb in ("validate", "all"):
        if not validate.validate() and verb == "all":
            sys.exit("stopping: validation failed")
    if verb in ("analyze", "all"):
        analytics.run()
    if verb in ("allocate", "all"):
        allocator.run_slice()
    if verb in ("experiment", "all"):
        experiments.run()


if __name__ == "__main__":
    main()

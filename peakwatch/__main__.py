"""PeakWatch CLI: py -m peakwatch <refresh|validate|analyze|allocate|experiment|all>"""
import sys

from . import collect, validate, allocator, analytics, experiments


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else "all"
    # Operating rhythms (the two parallel tracks):
    #   daily   = operations loop: fresh data -> checks -> peak risk + alert
    #   monthly = settlement loop: new RNL -> re-score zoo -> next predictions
    if verb == "daily":
        collect.refresh()
        if not validate.validate():
            sys.exit("stopping: validation failed")
        analytics.run()
        from . import peakmodel
        peakmodel.run()
        return
    if verb == "monthly":
        collect.refresh()
        if not validate.validate():
            sys.exit("stopping: validation failed")
        allocator.run_slice()
        experiments.run()
        from . import dollars
        dollars.run()
        return
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
    if verb == "decompose":
        from . import decompose
        decompose.run_slice()
    if verb == "dollars":
        from . import dollars
        dollars.run()
    if verb == "peakprob":
        from . import peakmodel
        peakmodel.run()
    if verb == "townhourly":
        from . import townhourly
        townhourly.run()


if __name__ == "__main__":
    main()

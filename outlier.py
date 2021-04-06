#!/usr/bin/env python3
'''
pr0pto
.pto utilities
Copyright 2012 John McMaster
'''
import argparse
import sys
from xystitch.pto.project import PTOProject
from xystitch.benchmark import Benchmark
from xystitch.optimizer import gen_cps, pto2icm, tmpdbg
from xystitch import statistics


def run(pto_fn, pto_fn_out=None, stdev=3.0):
    print(('In: %s' % pto_fn))
    bench = Benchmark()

    # TODO: l/r compensation

    pto = PTOProject.from_file_name(pto_fn)
    icm = pto2icm(pto)
    deltas = []
    pairs = []
    cpls = []
    for cpl, ((n_fn, N_fn), (nx, ny), (Nx, Ny)) in gen_cps(pto, icm=icm):
        delta = ((nx - Nx)**2 + (ny - Ny)**2)**0.5
        deltas.append(delta)
        pairs.append((n_fn, N_fn))
        cpls.append(cpl)
        if tmpdbg and (n_fn == 'c005_r003.jpg' and N_fn == 'c005_r004.jpg'):
            print(('debug', (n_fn, N_fn), (nx, ny), (Nx, Ny)))
            print(('debug', delta))

    deltas_u = statistics.mean(deltas)
    deltas_sd = statistics.stdev(deltas)
    print(("Delta mean: %0.1f" % deltas_u))
    print(("Delta stdev: %0.1f" % deltas_sd))
    _deltas_min = deltas_u - deltas_sd * stdev
    deltas_max = deltas_u + deltas_sd * stdev

    outlier_cps = 0
    outlier_pairs = set()
    pair_cur = None
    pairi = 0
    for cpl, (n_fn, N_fn), delta in zip(cpls, pairs, deltas):
        if pair_cur != (n_fn, N_fn):
            pairi = 0
            pair_cur = (n_fn, N_fn)
        else:
            pairi += 1

        # really only care about max
        if delta > deltas_max:
            # canonical file names
            fna, fnb = sorted((n_fn, N_fn))
            print(("%s %s %u: outlier delta %0.1f" % (fna, fnb, pairi, delta)))
            outlier_pairs.add((fna, fnb))
            outlier_cps += 1
            pto.remove_control_point_line(cpl)
    print("")
    print(("Flagged cps: %u" % outlier_cps))
    print(("Flagged pairs: %u" % len(outlier_pairs)))
    for fna, fnb in sorted(list(outlier_pairs)):
        print(("  %s %s" % (fna, fnb)))

    if pto_fn_out:
        pto.save_as(pto_fn_out)

    bench.stop()
    print(('Completed in %s' % bench))


def run_print(pto_fn, stdev=3):
    print(('In: %s' % pto_fn))

    pto = PTOProject.from_file_name(pto_fn)
    icm = pto2icm(pto)
    for ((n_fn, N_fn), (nx, ny), (Nx, Ny)) in gen_cps(pto, icm=icm):
        print(("%s:(%s, %s) %s:(%s, %s)" % (n_fn, nx, ny, N_fn, Nx, Ny)))
        print(("  %s, %s" % (nx - Nx, ny - Ny)))


def main():
    parser = argparse.ArgumentParser(description='Manipulate .pto files')
    parser.add_argument('--verbose',
                        action="store_true",
                        help='Verbose output')
    parser.add_argument('--stdev',
                        type=float,
                        default=3.0,
                        help='Max healthy standard deviation')
    parser.add_argument('pto_in',
                        nargs='?',
                        default="out.pto",
                        help='project to work on')
    parser.add_argument('pto_out',
                        nargs='?',
                        default=None,
                        help='project to work on')
    args = parser.parse_args()
    run(args.pto_in, args.pto_out, stdev=args.stdev)


if __name__ == "__main__":
    main()

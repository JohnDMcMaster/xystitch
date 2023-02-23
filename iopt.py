#!/usr/bin/env python3
"""
Iterative position optimizer
Uses a mix of statistical techniques
"""
import argparse
from xystitch.optimizer import XYOptimizer
from xystitch.pto.project import PTOProject
from xystitch.pto.util import center
from xystitch.benchmark import Benchmark
from xystitch.config import config_pto_defaults
from xystitch.util import add_bool_arg


def run(pto_in,
        pto_out=None,
        stdev=3.0,
        anchor_cr=None,
        check_poor_opt=True,
        r_orders=2,
        verbose=False):
    if pto_out is None:
        pto_out = pto_in

    print('pr0npto starting')
    print('In: %s' % pto_in)
    print('Out: %s' % pto_out)
    bench = Benchmark()

    pto = PTOProject.from_file_name(pto_in)
    # Make sure we don't accidently override the original
    pto.remove_file_name()
    config_pto_defaults(pto)

    print('Optimizing')
    opt = XYOptimizer(pto)
    opt.debug = verbose
    opt.stdev = stdev
    opt.r_orders = r_orders
    opt.run(anchor_cr=anchor_cr, check_poor_opt=check_poor_opt)

    print('Centering...')
    center(pto)

    print('Saving to %s' % pto_out)
    pto.save_as(pto_out)

    bench.stop()
    print('Completed in %s' % bench)


def main():
    parser = argparse.ArgumentParser(
        description='Iterative position optimizer')
    parser.add_argument('--verbose',
                        action="store_true",
                        help='Verbose output')
    parser.add_argument(
        '--stdev',
        type=float,
        default=3.0,
        help='xy-opt: keep points within n standard deviations')
    parser.add_argument('--anchor-cr',
                        default=None,
                        help='xy-opt: use col,row instead of guessing anchor')
    add_bool_arg(parser, '--check-poor-opt', default=True, help='')
    # TODO: get mode from out.json
    parser.add_argument(
        '--row-orders',
        # More conservative but less accurate
        default=2,
        type=int,
        help=
        "Number of row regressions. backlash compensated => 1, serpentine => 2"
    )
    parser.add_argument('--pto-in',
                        default="out.pto",
                        help='input .pto file name (default: out.pto)')
    parser.add_argument('--pto-out',
                        help='output .pto file name (default: pto-in)')

    args = parser.parse_args()
    anchor_cr = None
    if args.anchor_cr:
        anchor_c, anchor_r = args.anchor_cr.split(",")
        anchor_cr = int(anchor_c), int(anchor_r)
    run(pto_in=args.pto_in,
        pto_out=args.pto_out,
        stdev=args.stdev,
        anchor_cr=anchor_cr,
        check_poor_opt=args.check_poor_opt,
        r_orders=args.row_orders,
        verbose=args.verbose)


if __name__ == "__main__":
    main()

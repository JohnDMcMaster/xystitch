#!/usr/bin/env python3
"""
Assume images are in a perfectly linear array
Use detected features to create and solve a linear system
then place images onto that grid
"""
import argparse
from xystitch.pto.project import PTOProject
from xystitch.pto.util import center, resave_hugin
from xystitch.linear_optimizer import linear_reoptimize


def run(pto_fn_in=None, pto_fn_out=None, allow_missing=False, r_orders=2):
    if pto_fn_out is None:
        pto_fn_out = pto_fn_in
    print('Reference in: %s' % pto_fn_in)
    print('Out: %s' % pto_fn_out)

    # Have to start somewhere...
    pto = PTOProject.from_file_name(pto_fn_in)
    pto.remove_file_name()

    linear_reoptimize(pto, allow_missing=allow_missing, r_orders=r_orders)

    print('Centering...')
    center(pto)

    # ??? probably some old hack
    # print('Converting to Hugin form...')
    # resave_hugin(pto)

    print('Saving to %s' % pto_fn_out)
    pto.save_as(pto_fn_out)


def main():
    parser = argparse.ArgumentParser(
        description="Linear regression dead reckoning position optimizer")
    parser.add_argument('--allow-missing',
                        action="store_true",
                        dest="allow_missing",
                        default=True,
                        help='Allow missing images')
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
    run(args.pto_in,
        args.pto_out,
        args.allow_missing,
        r_orders=args.row_orders)


if __name__ == "__main__":
    main()

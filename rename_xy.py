#!/usr/bin/env python3
"""
Originally created to fix up a specific image set
Now a more generic tool
"""

from xystitch.util import add_bool_arg

import argparse
import glob
import os
import shutil
import math


def run(dir_in, dir_out, layout="serp-lr", cols=None, endrows=None, dry=True):
    imrows = []
    fns = sorted(glob.glob("%s/*.jpg" % dir_in))
    if cols is not None:
        assert len(fns) % cols == 0
        currow = None
        for fni, fn in enumerate(fns):
            fn = os.path.basename(fn)
            if currow is None:
                currow = []
                imrows.append(currow)
            currow.append(fn)
            if (fni + 1) % cols == 0:
                currow = None
    elif endrows is not None:
        # Bucket into rows
        endrows = endrows.split(",")
        imrows = []
        currow = None
        endrowi = 0
        for fn in fns:
            fn = os.path.basename(fn)
            if currow is None:
                currow = []
                imrows.append(currow)
            currow.append(fn)
            if fn == endrows[endrowi]:
                currow = None
                endrowi += 1
    else:
        raise Exception("Need either cols or endrows")

    if layout == "serp-lr":
        # Apply sepertine pattern starting from upper left
        for rowi, imrow in enumerate(imrows):
            if rowi % 2 == 1:
                imrow.reverse()
    elif layout == "serp-rl":
        # Apply sepertine pattern starting from upper right
        for rowi, imrow in enumerate(imrows):
            if rowi % 2 == 0:
                imrow.reverse()
    else:
        raise Exception("Invalid layout %s" % layout)
    """
    # Images have excessive overlap
    # Delete every other row and every other column
    # XXX: row1 might have better features than row0
    del imrows[1]
    for rowi, imrow in enumerate(imrows):
        this_cols = len(imrow)
        new_imrow = []
        for raw_coli, fn in enumerate(imrow):
            if raw_coli % 2 == 0:
                new_imrow.append(fn)
        imrows[rowi] = new_imrow
    """

    # Calculate number columns
    ncols = int(max([len(imrow) for imrow in imrows]))
    nrows = len(imrows)
    print(("%u cols x %u rows" % (ncols, nrows)))

    if not os.path.exists(dir_out):
        os.mkdir(dir_out)

    # Fit images as best as possible to rows
    for row, imrow in enumerate(imrows):
        this_cols = len(imrow)
        for raw_coli, fn in enumerate(imrow):
            col = int(round(1.0 * raw_coli / this_cols * ncols))
            print(("%s: %uc, %ur" % (fn, col, row)))
            if not dry:
                shutil.copyfile("%s/%s" % (dir_in, fn),
                                "%s/r%03u_c%03u.jpg" % (dir_out, row, col))


def main():
    parser = argparse.ArgumentParser(
        description='Rename manually captured images into a grid')
    add_bool_arg(parser, '--dry', default=True, help='')
    parser.add_argument('--layout', default="serp-lr", help='')
    parser.add_argument('--cols',
                        type=int,
                        default=None,
                        help='Use evenly distributed columns')
    parser.add_argument(
        '--endrows',
        help=
        'Manually specify last image in each row when irregular to interpolate cols. Last assumed'
    )
    parser.add_argument('dir_in', help='')
    parser.add_argument('dir_out', help='')
    args = parser.parse_args()

    run(args.dir_in,
        args.dir_out,
        layout=args.layout,
        cols=args.cols,
        endrows=args.endrows,
        dry=args.dry)


if __name__ == "__main__":
    main()

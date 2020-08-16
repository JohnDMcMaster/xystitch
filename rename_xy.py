#!/usr/bin/python3

from xystitch.util import add_bool_arg

import argparse
import glob
import os
import shutil
import math

def run(dir_in, dir_out, endrows, dry):
    # Bucket into rows
    endrows = endrows.split(",")
    imrows = []
    currow = None
    endrowi = 0
    for fn in sorted(glob.glob("%s/*.jpg" % dir_in)):
        fn = os.path.basename(fn)
        if currow is None:
            currow = []
            imrows.append(currow)
        currow.append(fn)
        if fn == endrows[endrowi]:
            currow = None
            endrowi += 1

    # Apply sepertine pattern
    for rowi, imrow in enumerate(imrows):
        if rowi % 2 == 1:
            imrow.reverse()

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

    # Calculate number columns
    ncols = int(max([len(imrow) for imrow in imrows]))
    nrows = len(imrows)
    print("%u cols x %u rows" % (ncols, nrows))

    if not os.path.exists(dir_out):
        os.mkdir(dir_out)

    # Fit images as best as possible to rows
    for row, imrow in enumerate(imrows):
        this_cols = len(imrow)
        for raw_coli, fn in enumerate(imrow):
            col = int(round(1.0 * raw_coli / this_cols * ncols))
            print("%s: %uc, %ur" % (fn, col, row))
            if not dry:
                shutil.copyfile("%s/%s" % (dir_in, fn), "%s/r%03u_c%03u.jpg" % (dir_out, row, col))

def main():
    parser = argparse.ArgumentParser(
        description='Rename manually captured images into a grid')
    add_bool_arg(parser, '--dry', default=True, help='')
    parser.add_argument('dir_in', help='')
    parser.add_argument('dir_out', help='')
    parser.add_argument('endrows', help='')
    args = parser.parse_args()

    run(args.dir_in, args.dir_out, args.endrows, dry=args.dry)

if __name__ == "__main__":
    main()


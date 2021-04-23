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

def seed_layout(fns, cols, endrows):
    imrows = []
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
    return imrows

def rm_rowcols(imrows, rm_even_row=False, rm_odd_row=False, rm_even_col=False, rm_odd_col=False):
    if rm_even_row:
        ret = []
        for rowi, imrow in enumerate(imrows):
            if rowi % 2 == 1:
                ret.append(imrow)
        imrows = ret
    elif rm_odd_row:
        ret = []
        for rowi, imrow in enumerate(imrows):
            if rowi % 2 == 0:
                ret.append(imrow)
        imrows = ret

    if rm_even_col:
        for rowi, imrow in enumerate(imrows):
            tmp = []
            for coli, im in enumerate(imrow):
                if coli % 2 == 1:
                    tmp.append(im)
            imrows[rowi] = tmp
    elif rm_odd_col:
        for rowi, imrow in enumerate(imrows):
            tmp = []
            for coli, im in enumerate(imrow):
                if coli % 2 == 0:
                    tmp.append(im)
            imrows[rowi] = tmp

    return imrows

def apply_serpentine(imrows, layout):
    if layout.find("serp-") != 0:
        return imrows
    # Apply serpentine pattern
    if layout == "serp-lr-ud" or layout == "serp-lr-du":
        # Apply sepertine pattern starting from upper left
        for rowi, imrow in enumerate(imrows):
            if rowi % 2 == 1:
                imrow.reverse()
    elif layout == "serp-rl-ud" or layout == "serp-rl-du":
        # Apply sepertine pattern starting from upper right
        for rowi, imrow in enumerate(imrows):
            if rowi % 2 == 0:
                imrow.reverse()
    else:
        raise Exception("Invalid layout %s" % layout)
    return imrows

def apply_du(imrows, layout):
    # Reverse to be top to bottom
    if layout not in ("serp-lr-du", "serp-rl-du", "lr-du", "rl-du"):
        return
    # Mirror along x axis
    for row in range(len(imrows) // 2):
        imrows[row], imrows[len(imrows) - row - 1] = imrows[len(imrows) - row - 1], imrows[row]
    return imrows

def trim_overlap(imrows):
    # Images have excessive overlap
    # Delete every other row and every other column
    # XXX: row1 might have better features than row0
    del imrows[1]
    for rowi, imrow in enumerate(imrows):
        # this_cols = len(imrow)
        new_imrow = []
        for raw_coli, fn in enumerate(imrow):
            if raw_coli % 2 == 0:
                new_imrow.append(fn)
        imrows[rowi] = new_imrow
    return imrows

def move_images(imrows, dir_in, dir_out, dry):
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

def run(dir_in, dir_out, layout="serp-lr-ud", cols=None, endrows=None, dry=True,
        rm_even_row=False, rm_odd_row=False, rm_even_col=False, rm_odd_col=False):
    fns = sorted(glob.glob("%s/*.jpg" % dir_in))
    # Get images into a grid, although not necessarily with the right orientation
    imrows = seed_layout(fns, cols, endrows)
    imrows = rm_rowcols(imrows, rm_even_row=rm_even_row, rm_odd_row=rm_odd_row, rm_even_col=rm_even_col, rm_odd_col=rm_odd_col)
    # Its more intuitive to get left/right right if we do this before serp
    imrows = apply_du(imrows, layout)
    imrows = apply_serpentine(imrows, layout)
    # imrows = trim_overlap(imrows)
    move_images(imrows, dir_in, dir_out, dry)


def main():
    parser = argparse.ArgumentParser(
        description='Rename manually captured images into a grid')
    add_bool_arg(parser, '--dry', default=True, help='')
    add_bool_arg(parser, '--rm-even-row', default=False, help='')
    add_bool_arg(parser, '--rm-odd-row', default=False, help='')
    add_bool_arg(parser, '--rm-even-col', default=False, help='')
    add_bool_arg(parser, '--rm-odd-col', default=False, help='')
    parser.add_argument('--layout', required=True, help='')
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
        dry=args.dry,
        rm_even_row=args.rm_even_row,
        rm_odd_row=args.rm_odd_row,
        rm_even_col=args.rm_even_col,
        rm_odd_col=args.rm_odd_col)


if __name__ == "__main__":
    main()

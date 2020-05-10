#!/usr/bin/python

from xystitch.tiler import Tiler
from xystitch.pto.project import PTOProject
from xystitch.config import config
from xystitch.single import singlify, HugeJPEG, coord
from xystitch.util import logwt, add_bool_arg, size2str, mksize, mem2pix

import argparse
import glob
import multiprocessing
import os
import re
import sys
import time
from PIL import Image


def run(args):
    log_dir = args.log
    out_dir = 'out'
    _dt = logwt(log_dir, 'main.log', shift_d=True)

    fn = args.pto[0]

    auto_size = not (args.stp or args.stm or args.stw or args.sth)

    if args.threads < 1:
        raise Exception('Bad threads')
    print('Using %d threads' % args.threads)

    print('Loading %s' % args.pto)
    project = PTOProject.from_file_name(args.pto)
    print('Creating tiler')

    t = Tiler(
        project,
        out_dir,
        stw=mksize(args.stw),
        sth=mksize(args.sth),
        stp=None,
        clip_width=args.clip_width,
        clip_height=args.clip_height,
        log_dir=log_dir,
        is_full=args.full)
    t.threads = args.threads
    t.verbose = args.verbose
    t.st_dir = args.st_dir
    t.force = args.force
    t.merge = args.merge
    t.out_extension = args.out_ext
    t.ignore_errors = args.ignore_errors
    t.ignore_crop = args.ignore_crop
    t.st_limit = float(args.st_limit)

    # TODO: make this more proper?
    if args.nona_args:
        t.nona_args = args.nona_args.replace('"', '').split(' ')
    if args.enblend_args:
        t.enblend_args = args.enblend_args.replace('"', '').split(' ')

    if args.super_t_xstep:
        t.super_t_xstep = args.super_t_xstep
    if args.super_t_ystep:
        t.super_t_ystep = args.super_t_ystep

    t.enblend_lock = args.enblend_lock

    if args.single_dir and not os.path.exists(args.single_dir):
        os.mkdir(args.single_dir)

    t.calc_expected_tiles()

    print('Forcing tiler on all images')
    for fn in glob.glob(args.st_dir + "/*.jpg"):
        print("")
        print("%s" % fn)
        im = Image.open(fn)
        width, height = im.size
        x0, y0 = coord(fn)
        #t.make_tile(im, x, y, row, col)
        st_bounds = [x0, x0 + width, y0, y0 + height]
        t.process_image(im, st_bounds)

    print('Creating single image')
    single_fn = args.single_fn
    if single_fn is None:
        single_fn = 'out.jpg'
    if args.single_dir:
        single_fn = os.path.join(args.single_dir, single_fn)
    # sometimes I restitch with different supertile size
    # this results in excessive merge, although really I should just delete the old files
    if args.merge:
        print('Single: using glob strategy on merge')
        s_fns = glob.glob(os.path.join(args.st_dir, 'st_*x_*y.jpg'))
    else:
        print('Single: using output strategy')
        s_fns = t.st_fns

    single_fn_alt = None
    if args.single_fn is None:
        single_fn_alt = single_fn.replace('.jpg', '.tif')

    try:
        singlify(s_fns, single_fn, single_fn_alt)
    except HugeJPEG:
        print('WARNING: single: exceeds max image size')

def main():
    parser = argparse.ArgumentParser(
        description='Convert supertiles to tiles')
    parser.add_argument(
        'pto', default='out.pto', nargs='?', help='pto project')
    parser.add_argument('--stw', help='Supertile width')
    parser.add_argument('--sth', help='Supertile height')
    parser.add_argument('--stp', help='Supertile pixels')
    parser.add_argument('--stm', help='Supertile memory')
    parser.add_argument(
        '--force', action="store_true", help='Force by replacing old files')
    parser.add_argument(
        '--merge',
        action="store_true",
        help="Don't delete anything and only generate things missing")
    parser.add_argument(
        '--out-ext',
        default='.jpg',
        help='Select output image extension (and type), .jpg, .png, .tif, etc')
    parser.add_argument(
        '--full', action="store_true", help='use only 1 supertile')
    parser.add_argument(
        '--st-xstep',
        action="store",
        dest="super_t_xstep",
        type=int,
        help='Supertile x step (advanced)')
    parser.add_argument(
        '--st-ystep',
        action="store",
        dest="super_t_ystep",
        type=int,
        help='Supertile y step (advanced)')
    parser.add_argument(
        '--clip-width',
        action="store",
        dest="clip_width",
        type=int,
        help='x clip (advanced)')
    parser.add_argument(
        '--clip-height',
        action="store",
        dest="clip_height",
        type=int,
        help='y clip (advanced)')
    parser.add_argument(
        '--ignore-crop',
        action="store_true",
        help='Continue even if not cropped')
    parser.add_argument('--nona-args')
    parser.add_argument('--enblend-args')
    parser.add_argument(
        '--ignore-errors',
        action="store_true",
        dest="ignore_errors",
        help='skip broken tile stitches (advanced)')
    parser.add_argument(
        '--verbose', '-v', action="store_true", help='spew lots of info')
    parser.add_argument(
        '--st-dir',
        default='st',
        help='store intermediate supertiles to given dir')
    parser.add_argument(
        '--st-limit',
        default='inf',
        help=
        'debug (exit after # supertiles, typically --st-limit 1 --threads 1)')
    parser.add_argument(
        '--single-dir',
        default='single',
        help='folder to put final output composite image')
    parser.add_argument(
        '--single-fn', default=None, help='file name to write in single dir')
    add_bool_arg(parser,
        '--enblend-lock',
        default=False,
        help=
        'use lock file to only enblend (memory intensive part) one at a time')
    parser.add_argument(
        '--threads', type=int, default=multiprocessing.cpu_count())
    parser.add_argument('--log', default='pr0nts', help='Output log file name')
    args = parser.parse_args()

    run(args)

if __name__ == "__main__":
    main()


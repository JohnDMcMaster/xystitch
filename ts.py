#!/usr/bin/python
'''
pr0ntile: IC die image stitching and tile generation
Copyright 2012 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''
'''
pr0nts: xystitch tile stitcher
This takes in a .pto project and outputs 
Described in detail here: 
http://uvicrec.blogspot.com/2012/02/tile-stitch.html
'''

from xystitch.tiler import Tiler
from xystitch.pto.project import PTOProject
from xystitch.config import config
from xystitch.single import singlify, HugeImage
from xystitch.util import logwt, add_bool_arg, size2str, mksize, mem2pix

import argparse
import glob
import multiprocessing
import os
import re
import sys
import time


def run(args):
    if args.threads < 1:
        raise Exception('Bad threads')
    print 'Using %d threads' % args.threads

    log_dir = args.log
    out_dir = 'out'
    _dt = logwt(log_dir, 'main.log', shift_d=True)

    fn = args.pto[0]

    auto_size = not (args.stp or args.stm or args.stw or args.sth)

    print 'Assuming input %s is pto project to be stitched' % args.pto
    project = PTOProject.from_file_name(args.pto)
    print 'Creating tiler'
    stp = None
    if args.stp:
        stp = mksize(args.stp)
    elif args.stm:
        stp = mem2pix(mksize(args.stm))
        print 'Memory %s => %s pix' % (args.stm, size2str(stp))
    elif auto_size:
        stm = config.super_tile_memory()
        if stm:
            stp = mem2pix(mksize(stm))
            # having issues creating very large
            if stp > 2**32 / 4:
                # 66 GB max useful as currently written
                print 'WARNING: reducing to maximum tile size'
                stp = 2**32 / 4

    t = Tiler(
        project,
        out_dir,
        stw=mksize(args.stw),
        sth=mksize(args.sth),
        stp=stp,
        clip_width=args.clip_width,
        clip_height=args.clip_height,
        log_dir=log_dir,
        is_full=args.full)
    t.threads = args.threads
    t.verbose = args.verbose
    t.st_dir = args.st_dir
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
    if args.clip_width:
        t.clip_width = args.clip_width
    if args.clip_height:
        t.clip_height = args.clip_height
    # if they specified clip but not supertile step recalculate the step so they don't have to do it
    if args.clip_width or args.clip_height and not (args.super_t_xstep
                                                    or args.super_t_ystep):
        t.recalc_step()

    t.enblend_lock = args.enblend_lock

    if args.single_dir and not os.path.exists(args.single_dir):
        os.mkdir(args.single_dir)

    print('Running tiler')
    try:
        t.run()
    except KeyboardInterrupt:
        if t.stale_worker:
            print 'WARNING: forcing exit on stuck worker'
            time.sleep(0.5)
            os._exit(1)
        raise
    print('Tiler done!')

    print('Creating single image')
    single_fn = args.single_fn
    if single_fn is None:
        single_fn = 'out.jpg'
    if args.single_dir:
        single_fn = os.path.join(args.single_dir, single_fn)
    # sometimes I restitch with different supertile size
    # this results in excessive merge, although really I should just delete the old files
    if 1:
        print 'Single: using glob strategy on merge'
        s_fns = glob.glob(os.path.join(args.st_dir, 'st_*x_*y.jpg'))
    else:
        print 'Single: using output strategy'
        s_fns = t.st_fns

    single_fn_alt = None
    if args.single_fn is None:
        single_fn_alt = single_fn.replace('.jpg', '.tif')

    try:
        singlify(s_fns, single_fn, single_fn_alt)
    except HugeImage:
        print 'WARNING: single: exceeds max image size, skipped'


def main():
    parser = argparse.ArgumentParser(
        description='create tiles from unstitched images')
    parser.add_argument(
        'pto', default='out.pto', nargs='?', help='pto project')
    parser.add_argument('--stw', help='Supertile width')
    parser.add_argument('--sth', help='Supertile height')
    parser.add_argument('--stp', help='Supertile pixels')
    parser.add_argument('--stm', help='Supertile memory')
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
    add_bool_arg(
        parser,
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

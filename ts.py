#!/usr/bin/env python3
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
from xystitch.util import logwt, add_bool_arg, size2str, mksize, mem2pix, pix2mem
from xystitch.benchmark import Benchmark

import argparse
import glob
import os
import time
import math

def make_threads_stp(args):
    """
    Ultimately require:
    -Number of worker threads
    -Supertile limit in piexels

    STP constraints:
    -Stitching a very large supertile can take a long time
        Time to add images goes up exponentially per image
        Maximum tile constraint
    -Supertiles in old enblend took a lot of memory
        Maximum total memory constraint
    """

    # Maximum threads to use
    # If insufficient memory might reduce
    threads = args.threads
    if not threads:
        threads = config.ts_threads()
    if threads < 1:
        raise Exception('Bad threads')
    print('Max threads: %u' % threads)

    auto_size = not (args.stp or args.stm or args.stw or args.sth)
    stp = None
    if args.stp:
        stp = mksize(args.stp)
    elif args.stm:
        stp = mem2pix(mksize(args.stm))
        print('Memory %s => %s pix' % (args.stm, size2str(stp)))
    elif auto_size:
        stp = config.st_max_pix()

    # having issues creating very large
    if not args.stp and stp > 2**32 / 4:
        # 66 GB max useful as currently written
        print('WARNING: reducing to maximum tile size')
        stp = 2**32 / 4

    # Keep explicit if given
    if not args.threads:
        # Estimate how many supertiles we can fit given memory
        # Try to make the largest supertiles possible
        # TODO: consider different strategies
        # This is "best" making large STs but we could also have "fast"
        max_mem = config.max_mem()
        stm = pix2mem(stp)
        max_st_threads = int(max(math.floor(max_mem / stm), 1))
        print("Strategy best: memory fits %u STs, %u threads available" % (max_st_threads, threads))
        print("  Max total memory: %sB" % size2str(max_mem))
        print("  Max ST pixels: %s" % size2str(stp))
        print("  Estimated max ST memory: %sB" % size2str(stm))
        if threads > max_st_threads:
            print("Reducing threads to safely fit in memory")
        threads = min(max_st_threads, threads)

    return threads, stp

def run(args):
    log_dir = args.log
    out_dir = 'out'
    _outlog, _errlog, outdate, _errdate = logwt(log_dir, 'main.log', shift_d=True)
    worker_stdout = outdate.fd
    bench = Benchmark()

    try:
        print('Assuming input %s is pto project to be stitched' % args.pto)
        project = PTOProject.from_file_name(args.pto)
        print('Creating tiler')
        threads, stp = make_threads_stp(args)

        t = Tiler(pto=project,
                  out_dir=out_dir,
                  stw=mksize(args.stw),
                  sth=mksize(args.sth),
                  stp=stp,
                  clip_width=args.clip_width,
                  clip_height=args.clip_height,
                  log_dir=log_dir,
                  is_full=args.full,
                  dry=args.dry,
                  worker_stdout=worker_stdout)
        t.set_threads(threads)
        t.set_verbose(args.verbose)
        t.set_st_dir(args.st_dir)
        t.set_out_extension(args.out_ext)
        t.set_ignore_errors(args.ignore_errors)
        t.set_ignore_crop(args.ignore_crop)
        t.set_st_limit(float(args.st_limit))

        # TODO: make this more proper?
        if args.nona_args:
            t.nona_args = args.nona_args.replace('"', '').split(' ')
        if args.enblend_args:
            t.enblend_args = args.enblend_args.replace('"', '').split(' ')

        if args.super_t_xstep:
            t.set_super_t_xstep(args.super_t_xstep)
        if args.super_t_ystep:
            t.set_super_t_ystep(args.super_t_ystep)
        if args.clip_width:
            t.set_clip_width(args.clip_width)
        if args.clip_height:
            t.set_clip_height(args.clip_height)
        # if they specified clip but not supertile step recalculate the step so they don't have to do it
        if args.clip_width or args.clip_height and not (args.super_t_xstep
                                                        or args.super_t_ystep):
            t.recalc_step()

        t.set_enblend_lock(args.enblend_lock)

        if args.single_dir and not os.path.exists(args.single_dir):
            os.mkdir(args.single_dir)

        config.set_enblend_safe_mode(args.safe_mode)

        print('Running tiler')
        try:
            t.run()
        except KeyboardInterrupt:
            if t.stale_worker:
                print('WARNING: forcing exit on stuck worker')
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
        except HugeImage:
            print('WARNING: single: exceeds max image size, skipped')
    finally:
        bench.stop()
        print('Completed in %s' % bench)

def main():
    parser = argparse.ArgumentParser(
        description='create tiles from unstitched images')
    parser.add_argument('pto',
                        default='out.pto',
                        nargs='?',
                        help='pto project')
    parser.add_argument('--stw', help='Supertile width')
    parser.add_argument('--sth', help='Supertile height')
    parser.add_argument('--stp', help='Supertile pixels')
    parser.add_argument('--stm', help='Supertile memory')
    parser.add_argument(
        '--out-ext',
        default='.jpg',
        help='Select output image extension (and type), .jpg, .png, .tif, etc')
    parser.add_argument('--full',
                        action="store_true",
                        help='use only 1 supertile')
    parser.add_argument('--st-xstep',
                        action="store",
                        dest="super_t_xstep",
                        type=int,
                        help='Supertile x step (advanced)')
    parser.add_argument('--st-ystep',
                        action="store",
                        dest="super_t_ystep",
                        type=int,
                        help='Supertile y step (advanced)')
    parser.add_argument('--clip-width',
                        action="store",
                        dest="clip_width",
                        type=int,
                        help='x clip (advanced)')
    parser.add_argument('--clip-height',
                        action="store",
                        dest="clip_height",
                        type=int,
                        help='y clip (advanced)')
    parser.add_argument('--ignore-crop',
                        action="store_true",
                        help='Continue even if not cropped')
    parser.add_argument('--nona-args')
    parser.add_argument('--enblend-args')
    # Originally this was false, but usually when something fails I still want best effort
    add_bool_arg(
                        parser,
                        '--ignore-errors',
                        default=True,
                        help='skip broken tile stitches (advanced)')
    parser.add_argument('--verbose',
                        '-v',
                        action="store_true",
                        help='spew lots of info')
    parser.add_argument('--st-dir',
                        default='st',
                        help='store intermediate supertiles to given dir')
    parser.add_argument(
        '--st-limit',
        default='inf',
        help=
        'debug (exit after # supertiles, typically --st-limit 1 --threads 1)')
    parser.add_argument('--single-dir',
                        default='single',
                        help='folder to put final output composite image')
    parser.add_argument('--single-fn',
                        default=None,
                        help='file name to write in single dir')
    add_bool_arg(
        parser,
        '--enblend-lock',
        default=False,
        help=
        'use lock file to only enblend (memory intensive part) one at a time')
    add_bool_arg(
        parser,
        '--dry',
        default=False,
        help=
        'Calculate stitch parameters and exit')
    add_bool_arg(
        parser,
        '--safe-mode',
        default=False,
        help=
        'Use options that will likely generate a stitch, albeit be slower. Includes: disable image caching')
    parser.add_argument('--threads', type=int, default=None)
    parser.add_argument('--log', default='pr0nts', help='Output log file name')
    args = parser.parse_args()

    run(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
'''
pr0ntile: IC die image stitching and tile generation
Copyright 2012 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''
'''
xyts: xystitch tile stitcher
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
    threads = args.get("threads")
    if not threads:
        threads = config.ts_threads()
    if threads < 1:
        raise Exception('Bad threads')
    print('Max threads: %u' % threads)

    auto_size = not (args.get("stp") or args.get("stm") or args.get("stw")
                     or args.get("sth"))
    stp = None
    if args.get("stp"):
        stp = mksize(args.get("stp"))
    elif args.get("stm"):
        stp = mem2pix(mksize(args.get("stm")))
        print('Memory %s => %s pix' % (args.get("stm"), size2str(stp)))
    elif auto_size:
        stp = config.st_max_pix()

    # having issues creating very large
    if not args.get("stp") and stp > 2**32 / 4:
        # 66 GB max useful as currently written
        print('WARNING: reducing to maximum tile size')
        stp = 2**32 / 4

    # Keep explicit if given
    if not args.get("threads"):
        # Estimate how many supertiles we can fit given memory
        # Try to make the largest supertiles possible
        # TODO: consider different strategies
        # This is "best" making large STs but we could also have "fast"
        max_mem = config.max_mem()
        stm = pix2mem(stp)
        max_st_threads = int(max(math.floor(max_mem / stm), 1))
        print("Strategy best: memory fits %u STs, %u threads available" %
              (max_st_threads, threads))
        print("  Max total memory: %sB" % size2str(max_mem))
        print("  Max ST pixels: %s" % size2str(stp))
        print("  Estimated max ST memory: %sB" % size2str(stm))
        if threads > max_st_threads:
            print("Reducing threads to safely fit in memory")
        threads = min(max_st_threads, threads)

    return threads, stp


def run(args):
    log_dir = args.get("log", "xyts")
    out_dir = 'out'
    _outlog, _errlog, outdate, _errdate = logwt(log_dir,
                                                'main.log',
                                                shift_d=True)
    worker_stdout = outdate.fd
    bench = Benchmark()

    pto_fn_in = args.get("pto", "out.pto")
    try:
        print('Assuming input %s is pto project to be stitched' % pto_fn_in)
        project = PTOProject.from_file_name(pto_fn_in)
        print('Creating tiler')
        threads, stp = make_threads_stp(args)

        t = Tiler(pto=project,
                  out_dir=out_dir,
                  stw=mksize(args.get("stw")),
                  sth=mksize(args.get("sth")),
                  stp=stp,
                  clip_width=args.get("clip_width"),
                  clip_height=args.get("clip_height"),
                  log_dir=log_dir,
                  is_full=args.get("full", False),
                  dry=args.get("dry", False),
                  worker_stdout=worker_stdout)
        t.set_threads(threads)
        t.set_verbose(args.get("verbose", False))
        t.set_st_dir(args.get("st_dir", "st"))
        t.set_out_extension(args.get("out_ext", ".jpg"))
        t.set_ignore_errors(args.get("ignore_errors", False))
        t.set_ignore_crop(args.get("ignore_crop", True))
        t.set_st_limit(float(args.get("st_limit", "inf")))

        # TODO: make this more proper?
        if args.get("nona_args"):
            t.nona_args = args.get("nona_args", "").replace('"', '').split(' ')
        if args.get("enblend_args"):
            t.enblend_args = args.get("enblend_args",
                                      "").replace('"', '').split(' ')

        if args.get("super_t_xstep"):
            t.set_super_t_xstep(args.get("super_t_xstep"))
        if args.get("super_t_ystep"):
            t.set_super_t_ystep(args.get("super_t_ystep"))
        if args.get("clip_width"):
            t.set_clip_width(args.get("clip_width"))
        if args.get("clip_height"):
            t.set_clip_height(args.get("clip_height"))
        # if they specified clip but not supertile step recalculate the step so they don't have to do it
        if args.get("clip_width") or args.get("clip_height") and not (
                args.get("super_t_xstep") or args.get("super_t_ystep")):
            t.recalc_step()

        t.set_enblend_lock(args.get("enblend_lock", True))

        single_dir = args.get("single_dir", "single")
        if single_dir and not os.path.exists(single_dir):
            os.mkdir(single_dir)

        config.set_enblend_safer_mode(args.get("safer_mode"))
        config.set_enblend_safest_mode(args.get("safest_mode"))

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
        single_fn = args.get("single_fn")
        if not single_fn:
            single_fn = 'out.jpg'
        if single_dir:
            single_fn = os.path.join(single_dir, single_fn)
        # sometimes I restitch with different supertile size
        # this results in excessive merge, although really I should just delete the old files
        if 1:
            print('Single: using glob strategy on merge')
            s_fns = glob.glob(
                os.path.join(args.get("st_dir", "st"), 'st_*x_*y.jpg'))
        else:
            print('Single: using output strategy')
            s_fns = t.st_fns

        single_fn_alt = None
        if args.get("single_fn") is None:
            single_fn_alt = single_fn.replace('.jpg', '.tif')

        try:
            singlify(s_fns, single_fn, single_fn_alt)
        except HugeImage:
            print('WARNING: single: exceeds max image size, skipped')
    finally:
        bench.stop()
        print('Completed in %s' % bench)


def run_kwargs(**kwargs):
    run(kwargs)


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
    add_bool_arg(parser,
                 '--ignore-crop',
                 default=True,
                 help='Continue even if not cropped')
    parser.add_argument('--nona-args')
    parser.add_argument('--enblend-args')
    # Originally this was false, but usually when something fails I still want best effort
    add_bool_arg(parser,
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
    add_bool_arg(parser,
                 '--dry',
                 default=False,
                 help='Calculate stitch parameters and exit')
    add_bool_arg(
        parser,
        '--safer-mode',
        default=False,
        help=
        'Use options that will likely generate a stitch, albeit be slower. Includes: disable image caching'
    )
    add_bool_arg(
        parser,
        '--safest-mode',
        default=False,
        help=
        'Use options that will very likely generate a stitch, albeit with poor results. Includes: disable image seam optimization entirely'
    )
    parser.add_argument('--threads', type=int, default=None)
    parser.add_argument('--log', default='xyts', help='Output log file name')
    args = parser.parse_args()

    run(vars(args))


if __name__ == "__main__":
    main()

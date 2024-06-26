#!/usr/bin/env python3
'''
pr0pto
.pto utilities
Copyright 2012 John McMaster
'''
import argparse
import sys
from xystitch.optimizer import PTOptimizer, XYOptimizer
from xystitch.optimizer2 import XYOptimizer2
from xystitch.pto.project import PTOProject
from xystitch.pto.util import *
from xystitch.util import IOTimestamp, IOLog
from xystitch.benchmark import Benchmark
from xystitch.config import config_pto_defaults
from xystitch.util import add_bool_arg

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Manipulate .pto files')
    parser.add_argument('--verbose',
                        action="store_true",
                        help='Verbose output')
    parser.add_argument('--center',
                        action="store_true",
                        dest="center",
                        default=None,
                        help='Center the project')
    parser.add_argument('--no-center',
                        action="store_false",
                        dest="center",
                        default=None,
                        help='Center the project')
    parser.add_argument('--anchor',
                        action="store_true",
                        dest="anchor",
                        help='Re-anchor in the center')
    parser.add_argument('--set-optimize-xy',
                        action="store_true",
                        dest="set_optimize_xy",
                        default=False,
                        help='Set project to optimize xy')
    parser.add_argument('--ptoptimizer',
                        action="store_true",
                        help='Run PTOptimizer also center by default')
    parser.add_argument(
        '--xy-opt',
        action="store_true",
        help='Core xy-stitch optimizer. Statistical based xy optimizer')
    parser.add_argument('--xy-opt2',
                        action="store_true",
                        help='Newer algorithm using uscan.json metadata')
    parser.add_argument(
        '--reoptimize',
        action="store_true",
        dest="reoptimize",
        default=True,
        help='When optimizing do not remove all existing optimizations')
    parser.add_argument(
        '--no-reoptimize',
        action="store_false",
        dest="reoptimize",
        default=True,
        help='When optimizing do not remove all existing optimizations')
    parser.add_argument('--lens-model',
                        action="store",
                        default=None,
                        help='Apply lens model file')
    parser.add_argument('--reset-photometrics',
                        action="store_true",
                        dest="reset_photometrics",
                        default=False,
                        help='Reset photometrics')
    parser.add_argument('--basename',
                        action="store_true",
                        dest="basename",
                        default=False,
                        help='Strip image file names down to basename')
    parser.add_argument('--hugin',
                        action="store_true",
                        help='Resave using panotools (Hugin form)')
    parser.add_argument(
        '--pto-ref',
        action='store',
        default=None,
        help='project to use for creating linear system (default: in)')
    parser.add_argument('--allow-missing',
                        action="store_true",
                        help='Allow missing images')
    add_bool_arg(parser, '--stampout', default=True, help='timestamp output')
    parser.add_argument(
        '--stdev',
        type=float,
        default=3.0,
        help='xy-opt: keep points within n standard deviations')
    parser.add_argument('--anchor-cr',
                        default=None,
                        help='xy-opt: use col,row instead of guessing anchor')
    add_bool_arg(parser, '--check-poor-opt', default=True, help='')
    parser.add_argument(
        '--crop',
        default=None,
        help='Set new crop and remove unused images as left,right,top,bottom')
    parser.add_argument('pto',
                        metavar='.pto in',
                        nargs=1,
                        help='project to work on')
    parser.add_argument('out',
                        metavar='.pto out',
                        nargs='?',
                        help='output file, default to override input')
    args = parser.parse_args()
    pto_in = args.pto[0]
    pto_out = args.out
    if pto_out is None:
        pto_out = pto_in

    exist = os.path.exists('pr0npto.log')
    # can easily be multiple invocations, save all data
    _outlog = IOLog(obj=sys, name='stdout', out_fn='pr0npto.log', mode='a')
    _errlog = IOLog(obj=sys, name='stderr', out_fd=_outlog.out_fd)

    if args.stampout:
        _outdate = IOTimestamp(sys, 'stdout')
        _errdate = IOTimestamp(sys, 'stderr')

    if exist:
        _outlog.out_fd.write('\n')
        _outlog.out_fd.write('\n')
        _outlog.out_fd.write('\n')
        _outlog.out_fd.write('*' * 80 + '\n')
        _outlog.out_fd.write('*' * 80 + '\n')
        _outlog.out_fd.write('*' * 80 + '\n')
    print('pr0npto starting')
    print('In: %s' % pto_in)
    print('Out: %s' % pto_out)
    bench = Benchmark()

    pto = PTOProject.from_file_name(pto_in)
    # Make sure we don't accidently override the original
    pto.remove_file_name()

    config_pto_defaults(pto)

    if args.center is True:
        center(pto)

    if args.anchor:
        print('Re-finding anchor')
        center_anchor(pto)

    if args.basename:
        print('Converting to basename')
        make_basename(pto)

    if args.hugin:
        print('Resaving with hugin')
        resave_hugin(pto)

    if args.lens_model:
        print('Applying lens model (FIXME)')

    if args.crop:
        bounds = [int(x) for x in args.crop.split(',')]
        assert len(bounds) == 4
        pl = pto.panorama_line
        pl.set_crop(bounds)
        rm_red_img(pto)
    '''
    if args.pto_ref:
        pto_ref = PTOProject.from_file_name(args.pto_ref)
        pto_ref.remove_file_name()
        linear_reoptimize(pto, pto_ref, args.allow_missing)

    if args.reset_photometrics:
        # Overall exposure
        # *very* important
        #??? shouldn't this be pto.?
        project.panorama_line.set_variable('E', 1)
        # What about m's p and s?

        for image_line in project.image_lines:
            # Don't adjust exposure
            image_line.set_variable('Eev', 1)
            # blue and red white balance correction at normal levels
            image_line.set_variable('Eb', 1)
            image_line.set_variable('Er', 1)
            # Disable EMoR corrections
            image_line.set_variable('Ra', 0)
            image_line.set_variable('Rb', 0)
            image_line.set_variable('Rc', 0)
            image_line.set_variable('Rd', 0)
            image_line.set_variable('Re', 0)
    '''

    if args.set_optimize_xy:
        optimize_xy_only(pto)

    # Needs to be late to get the earlier additions if we used them
    if args.ptoptimizer:
        print('Optimizing')
        opt = PTOptimizer(pto)
        opt.reoptimize = args.reoptimize
        opt.run()
        # Default
        if args.center != False:
            print('Centering...')
            center(pto)

    if args.xy_opt:
        print('Optimizing')
        opt = XYOptimizer(pto)
        opt.debug = args.verbose
        opt.stdev = args.stdev
        anchor_cr = None
        if args.anchor_cr:
            anchor_c, anchor_r = args.anchor_cr.split(",")
            anchor_cr = int(anchor_c), int(anchor_r)
        opt.run(anchor_cr=anchor_cr, check_poor_opt=args.check_poor_opt)
        # Default
        if args.center != False:
            print('Centering...')
            center(pto)

    if args.xy_opt2:
        print('Optimizing')
        opt = XYOptimizer2(pto)
        opt.debug = args.verbose
        opt.stdev = args.stdev
        anchor_cr = None
        if args.anchor_cr:
            anchor_c, anchor_r = args.anchor_cr.split(",")
            anchor_cr = int(anchor_c), int(anchor_r)
        opt.run(anchor_cr=anchor_cr, check_poor_opt=args.check_poor_opt)
        # Default
        if args.center != False:
            print('Centering...')
            center(pto)

    print('Saving to %s' % pto_out)
    pto.save_as(pto_out)

    bench.stop()
    print('Completed in %s' % bench)

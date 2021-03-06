#!/usr/bin/env python3
'''
pr0nstitch: IC die image feature generation for stitching
Copyright 2010 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details

Command refernece:
http://wiki.panotools.org/Panorama_scripting_in_a_nutshell
Some parts of this code inspired by Christian Sattler's tool
(https://github.com/JohnDMcMaster/csstitch)
pr0nstitch is described in detail at
http://uvicrec.blogspot.com/2011/02/scaling-up-image-stitching.html
'''

import argparse
import os.path
import signal
import sys
import traceback
import multiprocessing
from xystitch.grid_stitch import GridStitch
from xystitch.util import logwt
from xystitch.config import config

allow_overwrite = True


def t_or_f(arg):
    arg_value = str(arg).lower()
    return not (arg_value == "false" or arg_value == "0" or arg_value == "no")


def excepthook(excType, excValue, tracebackobj):
    print('%s: %s' % (excType, excValue))
    traceback.print_tb(tracebackobj)
    print('Exiting on exception')
    os._exit(1)


def parser_add_bool_arg(yes_arg, default=False, **kwargs):
    dashed = yes_arg.replace('--', '')
    dest = dashed.replace('-', '_')
    parser.add_argument(yes_arg,
                        dest=dest,
                        action='store_true',
                        default=default,
                        **kwargs)
    parser.add_argument('--no-' + dashed,
                        dest=dest,
                        action='store_false',
                        **kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Stitch images quickly into .pto through hints')
    parser.add_argument('--out', default='out.pto', help='Output file name')
    parser.add_argument('--log',
                        default='pr0nstitch',
                        help='Output log file name')
    parser_add_bool_arg('--grid-only', default=False, help='')
    parser.add_argument('--algorithm', default='grid', help='')
    parser.add_argument('--threads',
                        type=int,
                        default=multiprocessing.cpu_count())
    parser_add_bool_arg('--overwrite', default=False, help='')
    parser_add_bool_arg('--regular', default=True, help='')
    # parser.add_argument('--x-step-frac', type=float, default=None, help='image step fraction')
    # parser.add_argument('--y-step-frac', type=float, default=None, help='image step fraction')
    parser_add_bool_arg('--dry', default=False, help='')
    parser_add_bool_arg('--skip-missing', default=False, help='')
    parser_add_bool_arg('--ignore-errors', default=False, help='')
    parser.add_argument('fns', nargs='+', help='File names')
    args = parser.parse_args()

    log_dir = args.log
    _dt = logwt(log_dir, 'main.log', shift_d=True)
    """
    if args.x_step_frac is not None:
        if args.y_step_frac is None:
            y_step_frac = args.y_step_frac
        else:
            y_step_frac = args.x_step_frac
        config.set_step_frac(args.x_step_frac, y_step_frac)
    """

    depth = 1
    # CNC like precision?
    # Default to true for me
    regular = True

    input_image_file_names = list()
    input_project_file_name = None
    output_project_file_name = None
    for arg in args.fns:
        if arg.find('.pto') > 0:
            output_project_file_name = arg
        elif os.path.isfile(arg) or os.path.isdir(arg):
            input_image_file_names.append(arg)
        else:
            print('unrecognized arg: %s' % arg)
            print('must be pto file, image file, or image dir')
            sys.exit(1)
    if len(input_image_file_names) == 0:
        raise Exception('Requires image file names')

    print('post arg')
    print('output project: %s' % output_project_file_name)

    if args.threads < 1:
        raise Exception('Bad threads')

    if args.algorithm == "grid":
        engine = GridStitch.from_tagged_file_names(input_image_file_names)
        engine.ignore_errors = args.ignore_errors

        print('Using %d threads' % args.threads)
        engine.threads = args.threads
        engine.skip_missing = args.skip_missing
    else:
        raise Exception('need an algorithm / engine')

    engine.log_dir = log_dir
    engine.set_output_project_file_name(output_project_file_name)
    engine.set_regular(regular)
    engine.set_dry(args.dry)

    if not allow_overwrite:
        if output_project_file_name and os.path.exists(
                output_project_file_name):
            print('ERROR: cannot overwrite existing project file: %s' %
                  output_project_file_name)
            sys.exit(1)

    sys.excepthook = excepthook
    # Exit on ^C instead of ignoring
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    engine.run()
    print('Done!')

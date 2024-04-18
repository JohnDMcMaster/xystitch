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

import os.path
import signal
import sys
import traceback
import multiprocessing
import glob
from xystitch.grid_stitch import GridStitch
from xystitch.util import logwt
from xystitch.config import config
from xystitch.util import add_bool_arg


def t_or_f(arg):
    arg_value = str(arg).lower()
    return not (arg_value == "false" or arg_value == "0" or arg_value == "no")


def excepthook(excType, excValue, tracebackobj):
    print('%s: %s' % (excType, excValue))
    traceback.print_tb(tracebackobj)
    print('Exiting on exception')
    os._exit(1)


def run(input_image_file_names=None,
        output_project_file_name=None,
        dry=False,
        threads=None,
        algorithm=None,
        log_dir=None,
        ignore_errors=False,
        skip_missing=False,
        allow_overwrite=True):
    # time xy-feature out.pto $( (shopt -s nullglob; echo *.jpg *.png) ) "$@" ||exit 1
    if input_image_file_names is None:
        input_image_file_names = list(glob.glob("*.jpg")) + list(
            glob.glob("*.png"))
    if len(input_image_file_names) == 0:
        raise Exception('Requires image file names')

    if output_project_file_name is None:
        output_project_file_name = "out.pto"

    if not threads:
        threads = multiprocessing.cpu_count()
    if not algorithm:
        algorithm = "grid"

    if not log_dir:
        log_dir = "xystitch"
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

    print('post arg')
    print('output project: %s' % output_project_file_name)

    if threads < 1:
        raise Exception('Bad threads')

    if algorithm == "grid":
        engine = GridStitch.from_tagged_file_names(input_image_file_names)
        engine.ignore_errors = ignore_errors

        print('Using %d threads' % threads)
        engine.threads = threads
        engine.skip_missing = skip_missing
    else:
        raise Exception('need an algorithm / engine')

    engine.log_dir = log_dir
    engine.set_output_project_file_name(output_project_file_name)
    engine.set_regular(regular)
    engine.set_dry(dry)

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


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Stitch images quickly into .pto through hints')
    parser.add_argument('--out', default='out.pto', help='Output file name')
    parser.add_argument('--log',
                        default='xystitch',
                        help='Output log file name')
    add_bool_arg(parser, '--grid-only', default=False, help='')
    parser.add_argument('--algorithm', default='grid', help='')
    parser.add_argument('--threads',
                        type=int,
                        default=multiprocessing.cpu_count())
    add_bool_arg(parser, '--overwrite', default=True, help='')
    add_bool_arg(parser, '--regular', default=True, help='')
    # parser.add_argument('--x-step-frac', type=float, default=None, help='image step fraction')
    # parser.add_argument('--y-step-frac', type=float, default=None, help='image step fraction')
    add_bool_arg(parser, '--dry', default=False, help='')
    add_bool_arg(parser, '--skip-missing', default=False, help='')
    add_bool_arg(parser, '--ignore-errors', default=False, help='')
    parser.add_argument('fns', nargs='+', help='File names')
    args = parser.parse_args()

    input_image_file_names = list()
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

    run(input_image_file_names=input_image_file_names,
        output_project_file_name=output_project_file_name,
        dry=args.dry,
        threads=args.threads,
        algorithm=args.algorithm,
        log=args.log,
        ignore_errors=args.ignore_errors,
        allow_overwrite=args.overwrite)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
time xy-pto --xy-opt out.pto
time pano_modify --fov=AUTO --canvas=AUTO -o out.pto out.pto
"""

from xystitch.optimizer2 import XYOptimizer2
from xystitch.pto.project import PTOProject
from xystitch.util import IOTimestamp, IOLog
from xystitch.benchmark import Benchmark
from xystitch.config import config_pto_defaults, config
from xystitch.config import config as xystitch_config
import subprocess
import os
import sys


def run(pto_in=None, pto_out=None):
    if not pto_in:
        pto_in = "out.pto"
    if not pto_out:
        pto_out = pto_in

    print('xyreopt starting')
    print('In: %s' % pto_in)
    print('Out: %s' % pto_out)
    bench = Benchmark()

    pto = PTOProject.from_file_name(pto_in)
    # Make sure we don't accidently override the original
    pto.remove_file_name()

    config_pto_defaults(pto)

    print('Optimizing')
    opt = XYOptimizer2(pto)
    pto = opt.run()

    print('Saving to %s' % pto_out)
    pto.save_as(pto_out)

    subprocess.check_call(
        ["time"] + list(xystitch_config.panotools.pano_modify_cli()) +
        ["--fov=AUTO", "--canvas=AUTO", "-o", pto_out, pto_out])

    bench.stop()
    print('Completed in %s' % bench)

    return {
        "rms_initial": opt.rms_initial,
        "rms_final": opt.rms_final,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Manipulate .pto files')
    parser.add_argument('pto_in',
                        nargs='?',
                        default="out.pto",
                        help='project to work on')
    parser.add_argument('pto_out',
                        nargs='?',
                        help='output file, default to override input')
    args = parser.parse_args()
    pto_in = args.pto_in
    pto_out = args.pto_out

    exist = os.path.exists('xyreopt.log')
    # can easily be multiple invocations, save all data
    _outlog = IOLog(obj=sys, name='stdout', out_fn='xyreopt.log', mode='a')
    _errlog = IOLog(obj=sys, name='stderr', out_fd=_outlog.out_fd)

    _outdate = IOTimestamp(sys, 'stdout')
    _errdate = IOTimestamp(sys, 'stderr')

    if exist:
        _outlog.out_fd.write('\n')
        _outlog.out_fd.write('\n')
        _outlog.out_fd.write('\n')
        _outlog.out_fd.write('*' * 80 + '\n')
        _outlog.out_fd.write('*' * 80 + '\n')
        _outlog.out_fd.write('*' * 80 + '\n')

    run(pto_in, pto_out)


if __name__ == "__main__":
    main()

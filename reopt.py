#!/usr/bin/env python3
"""
time xy-pto --xy-opt out.pto
time pano_modify --fov=AUTO --canvas=AUTO -o out.pto out.pto
"""

from xystitch.optimizer2 import XYOptimizer2
from xystitch.pto.project import PTOProject
from xystitch.util import IOTimestamp, IOLog
from xystitch.benchmark import Benchmark
from xystitch.config import config_pto_defaults
import subprocess
import os
import sys

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Manipulate .pto files')
    parser.add_argument('pto_in', help='project to work on')
    parser.add_argument('pto_out',
                        nargs='?',
                        help='output file, default to override input')
    args = parser.parse_args()
    pto_in = args.pto_in
    pto_out = args.pto_out
    if pto_out is None:
        pto_out = pto_in

    exist = os.path.exists('pr0npto.log')
    # can easily be multiple invocations, save all data
    _outlog = IOLog(obj=sys, name='stdout', out_fn='pr0npto.log', mode='a')
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
    print('pr0npto starting')
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

    subprocess.check_call([
        "time", "pano_modify", "--fov=AUTO", "--canvas=AUTO", "-o", pto_out,
        pto_out
    ])

    bench.stop()
    print('Completed in %s' % bench)

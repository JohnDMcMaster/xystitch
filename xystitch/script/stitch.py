#!/usr/bin/env python3
"""
time xy-pto --xy-opt out.pto
time pano_modify --fov=AUTO --canvas=AUTO -o out.pto out.pto
"""

from xystitch.util import IOTimestamp, IOLog
from xystitch.benchmark import Benchmark
from xystitch.script import feature
from xystitch.script import reopt
from xystitch.script import ts as ts_script
import os
import sys
import shutil
from xystitch.util import add_bool_arg
import glob
import shutil


def run(pto_out=None,
        ts=True,
        ts_rms=None,
        ignore_errors=False,
        skip_missing=False,
        out_ext=None):
    if ts_rms is None:
        ts_rms = 2.0

    if not pto_out:
        pto_out = "out.pto"
    if os.path.exists(pto_out):
        print("Backing up old project file")
        shutil.move(pto_out, pto_out + ".old")

    print('stitch starting')
    bench = Benchmark()

    feature.run(ignore_errors=ignore_errors, skip_missing=skip_missing)

    print("Feature done")
    print("")
    print("")
    print("")
    print("Setting up optimization")
    shutil.copy(pto_out, pto_out + ".unclean.pto")
    reoptj = reopt.run()
    print("Optimization done")
    print("")
    print("")
    print("")

    if not ts:
        print("ts: disabled. Run manually")
    else:
        if reoptj["rms_final"] is None:
            print("Bad RMS. No control points?")
        else:
            print("Checking RMS. Need %0.2f <= %0.2f" %
                  (reoptj["rms_final"], ts_rms))
            if reoptj["rms_final"] <= ts_rms:
                print("RMS: Ok. Run stitch")
                ts_script.run_kwargs(ignore_errors=ignore_errors,
                                     skip_missing=skip_missing,
                                     out_ext=out_ext)
                if glob.glob("single/*"):
                    print("Deleting tiles on single file success")
                    shutil.rmtree("out")
            else:
                print(
                    "RMS: fail. Fix errors or raise RMS threshold and re-run optimizer"
                )

    bench.stop()
    print('Completed in %s' % bench)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Manipulate .pto files')
    parser.add_argument('--pto-out',
                        default="out.pto",
                        help='output file, default to override input')
    add_bool_arg(parser,
                 "--ts",
                 default=True,
                 help="automatically ts if acceptable RMS")
    parser.add_argument(
        '--ts-rms',
        # In general
        # < 1.0 is a perfect stitch
        # < 2.0 is pretty acceptable
        # 5.0 means there is someting pretty wrong
        default=2.0,
        type=float,
        help='If RMS is below this value automatically kick off a tile stitch')
    add_bool_arg(parser, '--ignore-errors', default=False, help='')
    add_bool_arg(parser, '--skip-missing', default=False, help='')
    parser.add_argument(
        '--out-ext',
        default='.jpg',
        help='Select output image extension (and type), .jpg, .png, .tif, etc')
    args = parser.parse_args()

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

    run(pto_out=args.pto_out,
        ts=args.ts,
        ts_rms=args.ts_rms,
        ignore_errors=args.ignore_errors,
        skip_missing=args.skip_missing,
        out_ext=args.out_ext)


if __name__ == "__main__":
    main()

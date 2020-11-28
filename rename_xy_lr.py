#!/usr/bin/python3

from xystitch.util import add_bool_arg
from xystitch.image_coordinate_map import ImageCoordinateMap, icm_flip_lr, icm_save

import argparse
import glob
import os
import shutil
import math


def run(dir_in, dir_out, dry):
    fns_in = []
    for fn in sorted(glob.glob("%s/*.jpg" % dir_in)):
        can_fn = os.path.realpath(fn)
        fns_in.append(can_fn)
    icm = ImageCoordinateMap.from_tagged_file_names(fns_in)
    icm_flip_lr(icm)
    icm_save(icm, dir_out)


def main():
    parser = argparse.ArgumentParser(description='Mirror grid left to right')
    add_bool_arg(parser, '--dry', default=True, help='')
    parser.add_argument('dir_in', help='')
    parser.add_argument('dir_out', help='')
    args = parser.parse_args()

    run(args.dir_in, args.dir_out, dry=args.dry)


if __name__ == "__main__":
    main()

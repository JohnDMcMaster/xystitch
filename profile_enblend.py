#!/usr/bin/env python3

"""
TODO:
-Plot memory as images increase
-Get info from multiple enblend versions
"""

import argparse
import matplotlib.pyplot as plt
import re
import dateutil.parser

def load_enblends(fn):
    """
    2021-04-26T01:31:30.832544 W0: enblend: info: loading next image: /mnt/m10_4/tmp/1169E10C93C87E2C/st_000300x_022706y_8C5A2E7EEC9EBE8E/0000.tif 1/1
    2021-04-26T01:31:33.221719 W0: enblend: info: loading next image: /mnt/m10_4/tmp/1169E10C93C87E2C/st_000300x_022706y_8C5A2E7EEC9EBE8E/0001.tif 1/1
    2021-04-26T01:31:59.259919 W0: enblend: info: loading next image: /mnt/m10_4/tmp/1169E10C93C87E2C/st_000300x_022706y_8C5A2E7EEC9EBE8E/0002.tif 1/1

    2021-04-20T02:45:12.925083: 2021-04-20T02:45:12.925043 w0: enblend: info: loading next image: /mnt/m10_4/tmp/8B2DEF981C116130/st_000427x_011546y_80A42DAC5292D592/0021.tif 1/1
    2021-04-20T02:45:23.960582: 2021-04-20T02:45:23.960543 w0: enblend: info: loading next image: /mnt/m10_4/tmp/8B2DEF981C116130/st_000427x_011546y_80A42DAC5292D592/0022.tif 1/1
    2021-04-20T02:45:34.820427: 2021-04-20T02:45:34.820387 w0: enblend: info: loading next image: /mnt/m10_4/tmp/8B2DEF981C116130/st_000427x_011546y_80A42DAC5292D592/0023.tif 1/1
    """
    for l in open(fn):
        m = re.search(r"([0-9T\.\-\:]+) [wW]0: enblend: info: loading next image", l)
        # m = re.search(r"([0-9T\.\-\:]+) W[0-9]+: enblend: info: loading next image", l)
        if not m:
            continue
        datestr = m.group(1)
        # print(datestr, l)
        dt = dateutil.parser.isoparse(datestr)
        yield dt

def load_enblend_log_net(fn):
    t0 = None
    times = []
    for dt in load_enblends(fn):
        if t0 is None:
            t0 = dt
        t = (dt - t0).total_seconds()
        times.append(t / 60.0)
    assert len(times)
    return list(range(len(times))), times

def load_enblend_log_diff(fn):
    tlast = None
    times = []
    for dt in load_enblends(fn):
        if tlast:
            t = (dt - tlast).total_seconds()
            times.append(t / 60.0)
        tlast = dt
    assert len(times)
    return list(range(len(times))), times


def main():
    parser = argparse.ArgumentParser(description='Help')
    parser.add_argument('--title', default='enblend image performance')
    parser.add_argument('--save', default=None)
    parser.add_argument('--net', action="store_true")
    parser.add_argument('fns', nargs='+', help='file,label')
    args = parser.parse_args()

    for arg in args.fns:
        parts = arg.split(",")
        if len(parts) == 1:
            fn = parts[0]
            label = None
        elif len(parts) == 2:
            fn, label = parts
        else:
            assert 0
        if args.net:
            imgns, ts = load_enblend_log_net(fn)
        else:
            imgns, ts = load_enblend_log_diff(fn)
        print("%s: %u images" % (fn, len(ts)))
        plt.plot(imgns, ts, label = label)
    plt.xlabel('Image #')
    if args.net:
        plt.ylabel('t (min) aggregate')
    else:
        plt.ylabel('t (min) per image')
    plt.title(args.title)
    if label:
        plt.legend()
    if args.save:
        plt.savefig(args.save)
    else:
        plt.show()

if __name__ == "__main__":
    main()

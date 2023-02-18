'''
xystitch
Copyright 2012 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''
'''
[mcmaster@gespenst tile]$ enblend --help
Usage: enblend [options] [--output=IMAGE] INPUT...
Blend INPUT images into a single IMAGE.

INPUT... are image filenames or response filenames.  Response
filenames start with an "@" character.

Common options:
  -V, --version          output version information and exit
  -a                     pre-assemble non-overlapping images
  -h, --help             print this help message and exit
  -l, --levels=LEVELS    number of blending LEVELS to use (1 to 29);
                         negative number of LEVELS decreases maximum
  -o, --output=FILE      write output to FILE; default: "a.tif"
  -v, --verbose[=LEVEL]  verbosely report progress; repeat to
                         increase verbosity or directly set to LEVEL
  -w, --wrap[=MODE]      wrap around image boundary, where MODE is
                         NONE, HORIZONTAL, VERTICAL, or BOTH; default: none;
                         without argument the option selects horizontal wrapping
  -x                     checkpoint partial results
  --compression=COMPRESSION
                         set compression of output image to COMPRESSION,
                         where COMPRESSION is:
                         NONE, PACKBITS, LZW, DEFLATE for TIFF files and
                         0 to 100 for JPEG files

Extended options:
  -b BLOCKSIZE           image cache BLOCKSIZE in kilobytes; default: 2048KB
  -c                     use CIECAM02 to blend colors
  -d, --depth=DEPTH      set the number of bits per channel of the output
                         image, where DEPTH is 8, 16, 32, r32, or r64
  -g                     associated-alpha hack for Gimp (before version 2)
                         and Cinepaint
  --gpu                  use graphics card to accelerate seam-line optimization
  -f WIDTHxHEIGHT[+xXOFFSET+yYOFFSET]
                         manually set the size and position of the output
                         image; useful for cropped and shifted input
                         TIFF images, such as those produced by Nona
  -m CACHESIZE           set image CACHESIZE in megabytes; default: 1024MB

Mask generation options:
  --coarse-mask[=FACTOR] shrink overlap regions by FACTOR to speedup mask
                         generation; this is the default; if omitted FACTOR
                         defaults to 8
  --fine-mask            generate mask at full image resolution; use e.g.
                         if overlap regions are very narrow
  --smooth-difference=RADIUS
                         smooth the difference image prior to seam-line
                         optimization with a Gaussian blur of RADIUS;
                         default: 0 pixels
  --optimize             turn on mask optimization; this is the default
  --no-optimize          turn off mask optimization
  --optimizer-weights=DISTANCEWEIGHT[:MISMATCHWEIGHT]
                         set the optimizer's weigths for distance and mismatch;
                         default: 8:1
  --mask-vectorize=LENGTH
                         set LENGTH of single seam segment; append "%" for
                         relative value; defaults: 4 for coarse masks and
                         20 for fine masks
  --anneal=TAU[:DELTAEMAX[:DELTAEMIN[:KMAX]]]
                         set annealing parameters of optimizer strategy 1;
                         defaults: 0.75:7000:5:32
  --dijkstra=RADIUS      set search RADIUS of optimizer strategy 2; default:
                         25 pixels
  --save-masks[=TEMPLATE]
                         save generated masks in TEMPLATE; default: "mask-%n.tif";
                         conversion chars: %i: mask index, %n: mask number,
                         %p: full path, %d: dirname, %b: basename,
                         %f: filename, %e: extension; lowercase characters
                         refer to input images uppercase to the output image
  --load-masks[=TEMPLATE]
                         use existing masks in TEMPLATE instead of generating
                         them; same template characters as "--save-masks";
                         default: "mask-%n.tif"
  --visualize[=TEMPLATE] save results of optimizer in TEMPLATE; same template
                         characters as "--save-masks"; default: "vis-%n.tif"

Report bugs at <http://sourceforge.net/projects/enblend/>.
'''

from xystitch import execute
from xystitch.execute import CommandFailed
from xystitch.config import config
import fcntl
import time
import sys
import subprocess
import re


def enblend_supports_cache():
    """
    Extra feature: image cache: yes
      - environment variable TMPDIR not set, cache file in default directory "/tmp"
    Hmm maybe should set this var...
    """
    # Errors if you don't have x server, but still returns version
    out = subprocess.check_output("enblend --version -v || true",
                                  encoding="ascii",
                                  shell=True)
    for l in out.split("\n"):
        m = re.match(r"Extra feature: image cache: (.+)", l)
        if not m:
            continue
        return m.group(1) == "yes"
    return False


class EnblendFailed(CommandFailed):
    pass


class Enblend:
    def __init__(self,
                 input_files,
                 output_file,
                 lock=False,
                 pprefix=None,
                 cache_mb=None):
        self.input_files = input_files
        self.output_file = output_file
        self.additional_args = []
        self._lock = lock
        self._lock_fp = None
        self.cache_mb = cache_mb

        self.pprintprefix = pprefix
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def lock(self):
        if not self._lock:
            print('enblend: skipping lock')
            return
        pid_file = '/tmp/xystitch-enblend.pid'
        self._lock_fp = open(pid_file, 'w')
        i = 0
        print('enblend: acquiring lock')
        while True:
            try:
                fcntl.lockf(self._lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except IOError:
                # Can take a while, print every 10 min or so and once at failure
                if i % (10 * 60 * 10) == 0:
                    print(
                        'enblend: Failed to acquire enblend lock, retrying (print every 10 min)'
                    )
                time.sleep(0.1)
            i += 1
        print('enblend: lock acquired')

    def unlock(self):
        if self._lock_fp is None:
            print('Skipping enblend unlock')
            return
        print('Releasing enblend lock')
        self._lock_fp.close()
        self._lock_fp = None

    def run(self):
        args = ["enblend"]
        # Cache is discontinued b/c developers don't consider it safe
        # In some instances a stitch crashes as a result of it
        # However it has such great performance benefit I still use it
        """
        test/simple on "cluster" xy-ts net time
        note: enblend is only part of this => actual effect is larger
        normal:: 7.8 sec net => 5.3 sec
        safer: 11.8 sec net => 9.3 sec
        safest: 6.5 sec net => 4.0 sec
            looks like 4 sec on enblend
        """
        if config.enblend_safer_mode:
            print('Blender: safer mode activated')
            # IIRC this takes more memory but is more likely to succeed
            # Quick test
            # So significant performance impact
            args.append("--fine-mask")
        if config.enblend_safest_mode:
            print('Blender: safest mode activated')
            args.append("--no-optimize")
        if self.cache_mb and enblend_supports_cache(
        ) and not config.enblend_safer_mode and not config.enblend_safest_mode:
            args.append("-m")
            args.append(str(self.cache_mb))
        for arg in self.additional_args:
            args.append(arg)
        for opt in config.enblend_opts().split():
            args.append(opt)
        args += ["-o", self.output_file]
        for f in self.input_files:
            args.append(f)

        self.lock()

        # Prefix w/ version
        execute.prefix(["enblend", "--version"],
                       stdout=self.stdout,
                       stderr=self.stderr,
                       prefix=self.pprintprefix)

        print('Blender: executing %s' % (' '.join(args), ))
        rc = execute.prefix(args,
                            stdout=self.stdout,
                            stderr=self.stderr,
                            prefix=self.pprintprefix)
        if not rc == 0:
            print('')
            print('')
            print('')
            print('Failed to blend')
            print('rc: %d' % rc)
            print(args)
            raise EnblendFailed('failed to remap')

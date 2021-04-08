
'''
xystitch
Copyright 2012 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''
'''
This class takes in a .pto project and does not modify it or any of the perspective parameters it specifies
It produces a series of output images, each a subset within the defined crop area
Pixels on the edges that don't fit nicely are black filled

Crop ranges are not fully inclusive
    ex: 0:255 results in a 255 width output, not 256

Arbitrarily assume that the right and bottom are the ones that aren't



This requires the following to work (or at least well):
-Source images must have some unique portion
    If they don't there is no natural "safe" region that can be blended separately
This works by forming larger tiles and then splitting them into smaller tiles


New strategy
Construct a spatial map using all of the images
Define an input intermediate tile width, height
    If undefined default to 3 * image width/height
    Note however, the larger the better (of course full image is ideal)
Define a safe buffer zone heuristic
    Nothing in this area shared with other tiles will be kept
    It will be re-generated as we crawl along and the center taken out
    
    In my images 1/3 of the image should be unique
    The assumption I'm trying to make is that nona will not try to blend more than one image away
    The default should be 1 image distance
    
Keep a closed set (and open set?) of all of the tiles we have generated
Each time we construct a new stitching frame only re-generate tiles that we actually need
This should simplify a lot of the bookkeeping, especially as things get hairy
At the end check that all times have been generated and throw an error if we are missing any
Greedy algorithm to generate a tile if its legal (and safe)
'''

from xystitch.remapper import Nona
from xystitch.blender import Enblend
from .image_coordinate_map import ImageCoordinateMap
from xystitch.config import config
from xystitch.temp_file import ManagedTempFile
from xystitch.temp_file import ManagedTempDir
from xystitch.pimage import PImage
from xystitch import pimage
from xystitch.benchmark import Benchmark
from xystitch.geometry import ceil_mult
from xystitch.execute import CommandFailed
from xystitch.pto.util import dbg, rm_red_img
from xystitch.util import IOTimestamp

import datetime
import math
import os
import queue
import psutil
import subprocess
import sys
import multiprocessing
import time
import traceback
from PIL import Image


class InvalidClip(Exception):
    pass


class NoTilesGenerated(Exception):
    pass


def pid_memory_recursive(pid, indent=""):
    ret = 0
    try:
        process = psutil.Process(pid)
        children = process.children(recursive=True)
        this = process.memory_info()[0]
        # print("%smem %u: %u" % (indent, pid, this))
        ret += this
        for child in children:
            ret += pid_memory_recursive(child.pid, indent=indent + "  ")
    except psutil.NoSuchProcess:
        pass
    return ret


class PartialStitcher(object):
    def __init__(self, pto, bounds, out, worki, work_run, pprefix):
        self.pto = pto
        self.bounds = bounds
        self.out = out
        self.nona_args = []
        self.enblend_args = []
        self.enblend_lock = False
        self.worki = worki
        self.work_run = work_run
        self.pprefix = pprefix

    def run(self):
        '''
        Phase 1: remap the relevant source image areas onto a canvas
        
        Note that nona will load ALL of the images (one at a time)
        but will only generate output for those that matter
        Each one takes a noticible amount of time but its relatively small compared to the time spent actually mapping images
        '''
        print("")
        print('Supertile phase 1: remapping (nona)')
        if self.out.find('.') < 0:
            raise Exception('Require image extension')
        # Hugin likes to use the base filename as the intermediates, lets do the sames
        out_name_base = self.out[0:self.out.find('.')].split('/')[-1]
        print("out name: %s, base: %s" % (self.out, out_name_base))
        #ssadf
        if out_name_base is None or len(
                out_name_base
        ) == 0 or out_name_base == '.' or out_name_base == '..':
            raise Exception('Bad output file base "%s"' % str(out_name_base))

        # Scope of these files is only here
        # We only produce the single output file, not the intermediates
        managed_temp_dir = ManagedTempDir.get2(
            prefix_mangle='st_%06dx_%06dy_' % (self.bounds[0], self.bounds[1]))
        # without the slash they go into the parent directory with that prefix
        out_name_prefix = managed_temp_dir.file_name + "/"
        '''
        For large projects this was too slow
        Instead, we simply copy the project and manually fix up the relevant portion
        '''
        print('Copying pto')
        pto = self.pto.copy(control_points=False)
        #pto = self.mini_pto.copy()

        print('Cropping...')
        #sys.exit(1)
        pl = pto.panorama_line
        # It is fine to go out of bounds, it will be black filled
        #pl.set_bounds(x, min(x + self.tw(), pto.right()), y, min(y + self.th(), pto.bottom()))
        pl.set_crop(self.bounds)
        # try to fix remapper errors due to excessive overlap
        rm_red_img(pto)
        #print('debug break') ; sys.exit(1)

        print('Preparing remapper...')
        remapper = Nona(pto, out_name_prefix)
        remapper.pprefix = self.pprefix
        remapper.args = self.nona_args
        print('Starting remapper...')
        remapper.remap()
        '''
        Phase 2: blend the remapped images into an output image
        '''
        print("")
        print('Supertile phase 2: blending (enblend) w/ %u images' %
              len(remapper.get_output_files()))
        blender = Enblend(remapper.get_output_files(),
                          self.out,
                          lock=self.enblend_lock)
        blender.pprefix = self.pprefix
        blender.args = self.enblend_args
        blender.run()
        # We are done with these files, they should be nuked
        if not config.keep_temp_files():
            for f in remapper.get_output_files():
                os.remove(f)

        print('Supertile ready!')


class Worker(object):
    def __init__(self, i, tiler, log_fn):
        self.process = multiprocessing.Process(target=self.run)

        self.i = i
        self.qi = multiprocessing.Queue()
        self.qo = multiprocessing.Queue()
        self.running = multiprocessing.Event()
        self.exit = False
        self.log_fn = log_fn
        # Master drains one line at a time to print to screen
        self.master_log_file = None

        self.dry = tiler.dry
        self.ignore_errors = tiler.ignore_errors
        self.st_dir = tiler.st_dir
        self.pto = tiler.pto
        self.enblend_lock = tiler.enblend_lock
        self.nona_args = tiler.nona_args
        self.enblend_args = tiler.enblend_args
        self.st_fns = multiprocessing.Queue()

    def master_log_file_init(self):
        self.master_log_file = open(self.log_fn, 'r')

    def master_log_file_print(self):
        if self.master_log_file:
            while True:
                s = self.master_log_file.readline()
                if not s:
                    break
                print(s.strip())

    def pprefix(self):
        # hack: ocassionally get io
        # use that to interrupt if need be
        if not self.running:
            raise Exception('not running')
        # TODO: put this into queue so we don't drop
        return '%s w%d: ' % (datetime.datetime.utcnow().isoformat(), self.i)

    def start(self):
        self.process.start()
        # Prevents later join failure
        self.running.wait(1)

    def run(self):
        _outlog = None
        try:
            if 1 and self.log_fn:
                print("Worker creating log")
                # _outlog = open(self.log_fn, 'w')
                # Buffer only on lines
                _outlog = open(self.log_fn, 'w', buffering=1)
                sys.stdout = _outlog
                sys.stderr = _outlog

                _outdate = IOTimestamp(sys, 'stdout')
                _errdate = IOTimestamp(sys, 'stderr')
            else:
                print("Working using stdout")

            self.running.set()
            self.exit = False
            messages_rx = 0
            messages_tx = 0
            print('Worker starting')
            while self.running.is_set():
                # print("Check queue, %u rx (q %u), %u tx (q %u)..." % (messages_rx, self.qi.qsize(), messages_tx, self.qo.qsize()))
                try:
                    task = self.qi.get(True, 0.1)
                except queue.Empty:
                    continue

                try:
                    (st_bounds, ) = task

                    print("")
                    print("")
                    print("")
                    print("")
                    print('*' * 80)
                    messages_rx += 1
                    print('task %u rx' % messages_rx)
                    _outlog and _outlog.flush()

                    try:
                        img_fn = self.try_supertile(st_bounds)
                        self.qo.put(('done', (st_bounds, img_fn)))
                        messages_tx += 1
                    except CommandFailed as e:
                        if not self.ignore_errors:
                            raise
                        # We shouldn't be trying commands during dry but just in case should raise?
                        print('WARNING: got exception trying supertile %s' %
                              str(st_bounds))
                        traceback.print_exc()
                        estr = traceback.format_exc()
                        self.qo.put(('exception', (task, e, estr)))
                    print('task done')

                except Exception as e:
                    traceback.print_exc()
                    estr = traceback.format_exc()
                    self.qo.put(('exception', (task, e, estr)))
            print('exiting')
            self.exit = True
        finally:
            print("Worker exiting")
            if _outlog:
                _outlog.flush()
                _outlog.close()
                _outlog = None

    def try_supertile(self, st_bounds):
        '''x0/1 and y0/1 are global absolute coordinates'''
        # First generate all of the valid tiles across this area to see if we can get any useful work done?
        # every supertile should have at least one solution or the bounds aren't good
        x0, x1, y0, y1 = st_bounds

        bench = Benchmark()
        try:
            if self.st_dir:
                # nah...tiff takes up too much space
                dst = os.path.join(self.st_dir,
                                   'st_%06dx_%06dy.jpg' % (x0, y0))
                if os.path.exists(dst):
                    # normally this is a .tif so slight loss in quality
                    # img = PImage.from_file(dst)
                    print('supertile short circuit on already existing: %s' %
                          (dst, ))
                    return dst

            # st_081357x_000587y.jpg
            temp_file = ManagedTempFile.get(None,
                                            '.tif',
                                            prefix_mangle='st_%06dx_%06dy_' %
                                            (x0, y0))

            stitcher = PartialStitcher(self.pto,
                                       st_bounds,
                                       temp_file.file_name,
                                       self.i,
                                       self.running,
                                       pprefix=self.pprefix)
            stitcher.enblend_lock = self.enblend_lock
            stitcher.nona_args = self.nona_args
            stitcher.enblend_args = self.enblend_args

            if self.dry:
                print('dry: skipping partial stitch')
                stitcher = None
            else:
                stitcher.run()

            print("")
            print('phase 3: loading supertile image')
            if self.dry:
                print('dry: skipping loading PTO')
                img_fn = None
            else:
                if self.st_dir:
                    self.st_fns.put(dst)

                    #shutil.copyfile(temp_file.file_name, dst)
                    args = [
                        'convert', '-quality', '90', temp_file.file_name, dst
                    ]
                    print('going to execute: %s' % (args, ))
                    subp = subprocess.Popen(args,
                                            stdout=None,
                                            stderr=None,
                                            shell=False)
                    subp.communicate()
                    if subp.returncode != 0:
                        raise Exception('Failed to copy stitched file')

                    # having some problems that looks like file isn't getting written to disk
                    # monitoring for such errors
                    # remove if I can root cause the source of these glitches
                    for i in range(30):
                        if os.path.exists(dst):
                            break
                        if i == 0:
                            print(
                                'WARNING: soften missing strong blur dest file name %s, waiting a bit...'
                                % (dst, ))
                        time.sleep(0.1)
                    else:
                        raise Exception(
                            'Missing soften strong blur output file name %s' %
                            dst)

                # FIXME: was passing loaded image object
                # Directory should delete on exit
                # otherwise parent can delete it
                #img = PImage.from_file(temp_file.file_name)
                img_fn = temp_file.file_name
                # prevent deletion
                temp_file.file_name = ''

                #print('supertile width: %d, height: %d' % (img.width(), img.height())
                print('Supertile done w/ fn %s' % (img_fn, ))
            return img_fn
        except:
            print('supertile failed at %s' % (bench, ))
            raise


def estimate_wh(pto):
    ws = []
    hs = []
    for i in pto.get_image_lines():
        ws.append(i.width())
        hs.append(i.height())

    #if self.img_width != w or self.img_height != h:
    #    raise Exception('Require uniform input images for size heuristic')
    return int(sum(ws) / len(ws)), int(sum(hs) / len(hs))


# For managing the closed list


class Tiler:
    def __init__(self,
                 pto,
                 out_dir,
                 tile_width=250,
                 tile_height=250,
                 st_scalar_heuristic=4,
                 dry=False,
                 stw=None,
                 sth=None,
                 stp=None,
                 clip_width=None,
                 clip_height=None,
                 log_dir='pr0nts',
                 is_full=False):
        '''
        stw: super tile width
        sth: super tile height
        stp: super tile pixels (auto stw, sth)
        '''
        self.is_full = False
        self.img_width = None
        self.img_height = None
        self.dry = dry
        self.stale_worker = False
        self.st_scalar_heuristic = st_scalar_heuristic
        self.ignore_errors = False
        self.ignore_crop = False
        self.verbose = False
        self.verbosity = 2
        self.stw = stw
        self.sth = sth
        self.clip_width = clip_width
        self.clip_height = clip_height
        self.st_dir = None
        self.nona_args = []
        self.enblend_args = []
        self.threads = 1
        self.workers = None

        self.open_list_rc = None
        self.closed_list_rc = None

        self.st_fns = []
        self.st_limit = float('inf')
        self.log_dir = log_dir
        self.this_tiles_done = 0
        '''
        When running lots of threads, we get stuck trying to get something mapping
        I think this is due to GIL contention
        To work around this, workers do pre-map stuff single threaded (as if they were in the server thread)
        '''
        # TODO: this is a heuristic just for this, uniform input images aren't actually required
        self.img_width, self.img_height = estimate_wh(pto)

        self.pto = pto

        # make absolutely sure that threads will only be doing read only operations
        # pre-parse the project
        self.pto.parse()
        print('Making absolute')
        pto.make_absolute()

        self.out_dir = out_dir
        self.tw = tile_width
        self.th = tile_height

        #out_extension = '.png'
        self.out_extension = '.jpg'

        spl = self.pto.get_panorama_line()
        self.x0 = spl.left()
        self.x1 = spl.right()
        self.y0 = spl.top()
        self.y1 = spl.bottom()
        #print(spl)

        if is_full:
            self.make_full()
        else:
            self.is_full = False

        self.calc_size_heuristic(self.img_width, self.img_height)

        # Auto calc tile parameters based on # super tile pixels?
        if self.is_full:
            print("full: forcing supertile size")
            self.stw = self.width()
            self.sth = self.height()
        elif stp:
            self.calc_stp(stp)

        # These are less related
        # They actually should be set as high as you think you can get away with
        # Although setting a smaller number may have higher performance depending on input size
        if self.stw is None:
            self.stw = self.img_width * self.st_scalar_heuristic
        if self.sth is None:
            self.sth = self.img_height * self.st_scalar_heuristic

        if self.stw <= self.img_width:
            self.clip_width = 0
        if self.sth <= self.img_height:
            self.clip_height = 0

        if not self.is_full:
            self.recalc_step()
        # We build this in run
        self.map = None
        print('Clip width: %d' % self.clip_width)
        print('Clip height: %d' % self.clip_width)
        print('ST width: %d' % self.stw)
        print('ST height: %d' % self.sth)
        if self.stw <= 2 * self.clip_width and self.stw >= self.img_width:
            print('Failed')
            print('  STW: %d' % self.stw)
            print('  Clip W: %d' % self.clip_width)
            print('  W: %d (%d - %d)' %
                  (self.img_width, self.right(), self.left()))
            raise InvalidClip(
                'Clip width %d exceeds supertile width %d after adj: reduce clip or increase ST size'
                % (self.clip_width, self.stw))
        if self.sth <= 2 * self.clip_height and self.sth >= self.img_height:
            raise InvalidClip(
                'Clip height %d exceeds supertile height %d after adj: reduce clip or increase ST size'
                % (self.clip_height, self.sth))
        # assuming clipped on all sides
        stp = self.stw * self.sth
        cstp = (self.stw - 2 * self.clip_width) * (self.sth -
                                                   2 * self.clip_height)
        print("Center ST efficiency: %0.1f%%" % (100.0 * cstp / stp))

    def calc_stp(self, stp):
        if self.stw or self.sth:
            raise ValueError("Can't manually specify width/height and do auto")
        '''
        Given an area and a length and width, find the optimal tile sizes
        such that there are the least amount of tiles but they cover all area
        with each tile being as small as possible
        
        Generally get better results if things remain square
        Long rectangular sections that can fit a single tile easily should
            Idea: don't let tile sizes get past aspect ratio of 2:1
        
        Take the smaller dimension
        '''
        # Maximum h / w or w / h
        aspect_max = 2.0
        w = self.width()
        h = self.height()
        a = w * h
        '''
        w = h / a
        p = w * h = (h / a) * h
        p * a = h**2, h = (p * a)**0.5
        '''
        min_stwh = int((stp / aspect_max)**0.5)
        max_stwh = int((stp * aspect_max)**0.5)
        print('Maximum supertile width/height: %d w/ square @ %d' %
              (max_stwh, int(stp**0.5)))
        # Theoretical number of tiles if we had no overlap
        theoretical_tiles = a * 1.0 / stp
        print('Net area %d (%dw X %dh) requires at least ceil(%g) tiles' % \
                (a, w, h, theoretical_tiles))
        aspect = 1.0 * w / h
        # Why not just run a bunch of sims and take the best...
        if 0:
            '''
            Take a rough shape of the canvas and then form rectangles to match
            '''
            if aspect >= 2.0:
                print('width much larger than height')
            elif aspect <= 0.5:
                print('Height much larger than width')
            else:
                print('Squarish canvas, forming squares')
        self.sweep_st_optimizer(stp, min_stwh, max_stwh)
        self.trim_stwh()

    def sweep_st_optimizer(self, stp, min_stwh, max_stwh):
        # Keep each tile size constant
        print('Sweeping tile size optimizer')
        best_w = None
        best_h = None
        self.best_n = None
        # Get the lowest perimeter among n
        # Errors occur around edges
        best_p = None
        # Arbitrary step at 1000
        # Even for large sets we want to optimize
        # for small sets we don't care
        for check_w in range(min_stwh, max_stwh, 100):
            check_h = stp / check_w
            print('Checking supertile size %dw X %dh (area %d)' %
                  (check_w, check_h, check_w * check_h))
            try:
                tiler = Tiler(pto=self.pto,
                              out_dir=self.out_dir,
                              tile_width=self.tw,
                              tile_height=self.th,
                              st_scalar_heuristic=self.st_scalar_heuristic,
                              dry=True,
                              stw=check_w,
                              sth=check_h,
                              stp=None,
                              clip_width=self.clip_width,
                              clip_height=self.clip_height)
            except InvalidClip as e:
                print('Discarding: invalid clip: %s' % (e, ))
                print()
                continue

            # The area will float around a little due to truncation
            # Its better to round down than up to avoid running out of memory
            n_expected = tiler.expected_sts()
            # XXX: is this a bug or something that I should just skip?
            if n_expected == 0:
                print('Invalid STs 0')
                print()
                continue

            p = (check_w + check_h) * 2
            print('Would generate %d supertiles each with perimeter %d' %
                  (n_expected, p))
            # TODO: there might be some optimizations within this for trimming...
            # Add a check for minimum total mapped area
            if self.best_n is None or self.best_n > n_expected and best_p > p:
                print('Better')
                self.best_n = n_expected
                best_w = check_w
                best_h = check_h
                best_p = p
                if n_expected == 1:
                    print('Only 1 ST: early break')
                    break
            print("")

        if self.best_n is None:
            raise Exception("Failed to find stitch solution")
        print('Best n %d w/ %dw X %dh' % (self.best_n, best_w, best_h))
        if 0:
            print("")
            print('Debug break')
            sys.exit(1)
        self.stw = best_w
        self.sth = best_h

    def msg(self, s, l):
        '''print(message s at verbosity level l'''
        if l <= self.verbosity:
            print(s)

    def expected_sts(self):
        '''Number of expected supertiles'''
        return len(list(self.gen_supertiles()))

    def trim_stwh(self):
        '''
        Supertiles may be larger than the margins
        If so it just slows down stitching with a lot of stuff getting thrown away
        
        Each time a supertile is added we lose one overlap unit
        ideally canvas w = n * stw - (n - 1) * overlap
        Before running this function stw may be oversized
        '''
        self.recalc_step()
        orig_st_area = self.stw * self.sth
        orig_net_area = self.expected_sts() * orig_st_area
        orig_stw = self.stw
        orig_sth = self.sth

        # eliminate corner cases by only trimming when it can do any good
        print('Trimming %d supertiles' % self.best_n)
        if self.best_n <= 1:
            print('Only one ST: not trimming')
            return

        if 0:
            # First one is normal but each additional takes a clip
            w_sts = int(1 + math.ceil(1.0 * (self.width() - self.stw) /
                                      (self.stw - self.super_t_xstep)))
            h_sts = int(1 + math.ceil(1.0 * (self.height() - self.sth) /
                                      (self.sth - self.super_t_ystep)))
            print('%dw X %dh supertiles originally' % (w_sts, h_sts))
            #total_clip_width = self.clip_width *
        else:
            h_sts = 0
            h_extra = 0
            for y in range(self.top(), self.bottom(), self.super_t_ystep):
                h_sts += 1
                y1 = y + self.sth
                if y1 >= self.bottom():
                    h_extra = y1 - self.bottom()
                    break

            w_sts = 0
            w_extra = 0
            for x in range(self.left(), self.right(), self.super_t_xstep):
                w_sts += 1
                x1 = x + self.stw
                if x1 >= self.right():
                    w_extra = x1 - self.right()
                    break
            print('%d width tiles waste %d pixels' % (w_sts, w_extra))
            self.stw = self.stw - w_extra / w_sts
            print('%d height tiles waste %d pixels' % (h_sts, h_extra))
            self.sth = self.sth - h_extra / h_sts
            # Since we messed with the tile width the step needs recalc
            self.recalc_step()

        new_st_area = self.stw * self.sth
        new_net_area = self.expected_sts() * new_st_area
        print('Final supertile trim results:')
        print('  Width %d => %d (%g%% of original)' %
              (orig_stw, self.stw, 100.0 * self.stw / orig_stw))
        print('  Height %d => %d (%g%% of original)' %
              (orig_sth, self.sth, 100.0 * self.sth / orig_sth))
        print('  ST area %d => %d (%g%% of original)' %
              (orig_st_area, new_st_area, 100.0 * new_st_area / orig_st_area))
        print('  Net area %d => %d (%g%% of original)' %
              (orig_net_area, new_net_area,
               100.0 * new_net_area / orig_net_area))

    def make_full(self):
        '''Stitch a single supertile'''
        self.stw = self.width()
        self.sth = self.height()
        self.clip_width = 1
        self.clip_height = 1
        self.super_t_xstep = 1
        self.super_t_ystep = 1
        self.is_full = True

    def recalc_step(self):
        '''
        We won't stitch any tiles in the buffer zone
        We don't stitch on the right to the current supertile and won't stitch to the left on the next supertile
        So, we must take off 2 clip widths to get a safe area
        We probably only have to take off one tw, I haven't thought about it carefully enough
        
        If you don't do this you will not stitch anything in the center that isn't perfectly aligned
        Will get worse the more tiles you create
        '''
        try:
            self.super_t_xstep = self.stw - 2 * self.clip_width - 2 * self.tw
            if self.super_t_xstep <= 0:
                print('parameters', self.sth, self.clip_height, self.th)
                raise InvalidClip("Bad xstep: %s" % self.super_t_xstep)
            self.super_t_ystep = self.sth - 2 * self.clip_height - 2 * self.th
            if self.super_t_ystep <= 0:
                print('parameters', self.sth, self.clip_height, self.th)
                raise InvalidClip("Bad ystep: %s" % self.super_t_ystep)
        except:
            print(self.stw, self.clip_width, self.tw)
            raise

    def calc_size_heuristic(self, image_width, image_height):
        '''
        The idea is that we should have enough buffer to have crossed a safe area
        If you take pictures such that each picture has at least some unique area (presumably in the center)
        it means that if we leave at least one image width/height of buffer we should have an area where enblend is not extending to
        Ultimately this means you lose 2 * image width/height on each stitch
        so you should have at least 3 * image width/height for decent results
        
        However if we do assume its on the center the center of the image should be unique and thus not a stitch boundry
        '''
        if self.clip_width is None:
            self.clip_width = int(image_width * 1.5)
        if self.clip_height is None:
            self.clip_height = int(image_height * 1.5)

    def gen_supertile_tiles(self, st_bounds):
        '''Yield UL coordinates in (y, x) pairs'''
        x0, x1, y0, y1 = st_bounds
        xt0 = ceil_mult(x0, self.tw, align=self.x0)
        xt1 = ceil_mult(x1, self.tw, align=self.x0)
        if xt0 >= xt1:
            print(x0, x1)
            print(xt0, xt1)
            raise Exception('Bad input x dimensions')
        yt0 = ceil_mult(y0, self.th, align=self.y0)
        yt1 = ceil_mult(y1, self.th, align=self.y0)
        if yt0 >= yt1:
            print(y0, y1)
            print(yt0, yt1)
            raise Exception('Bad input y dimensions')

        if self.tw <= 0 or self.th <= 0:
            raise Exception('Bad step values')

        skip_xl_check = False
        skip_xh_check = False
        # If this is an edge supertile skip the buffer check
        if x0 == self.left():
            #print('X check skip (%d): left border' % x0)
            skip_xl_check = True
        if x1 == self.right():
            #print('X check skip (%d): right border' % x1)
            skip_xh_check = True

        skip_yl_check = False
        skip_yh_check = False
        if y0 == self.top():
            #print('Y check skip (%d): top border' % y0)
            skip_yl_check = True
        if y1 == self.bottom():
            #print('Y check skip (%d): bottom border' % y1)
            skip_yh_check = True

        for y in range(yt0, yt1, self.th):
            # Are we trying to construct a tile in the buffer zone?
            if (not skip_yl_check) and y < y0 + self.clip_height:
                if self.verbose:
                    print('Rejecting tile @ y%d, x*: yl clip' % (y))
                continue
            if (not skip_yh_check) and y + self.th >= y1 - self.clip_height:
                if self.verbose:
                    print('Rejecting tile @ y%d, x*: yh clip' % (y))
                continue
            for x in range(xt0, xt1, self.tw):
                # Are we trying to construct a tile in the buffer zone?
                if (not skip_xl_check) and x < x0 + self.clip_width:
                    if self.verbose:
                        print('Rejecting tiles @ y%d, x%d: xl clip' % (y, x))
                    continue
                if (not skip_xh_check) and x + self.tw >= x1 - self.clip_width:
                    if self.verbose:
                        print('Rejecting tiles @ y%d, x%d: xh clip' % (y, x))
                    continue
                yield (y, x)

    def process_image(self, img_fn, im, st_bounds):
        '''
        A tile is valid if its in a safe location
        There are two ways for the location to be safe:
        -No neighboring tiles as found on canvas edges
        -Sufficiently inside the blend area that artifacts should be minimal
        '''
        bench = Benchmark()
        [x0, x1, y0, y1] = st_bounds
        gen_tiles = 0
        print("")
        # TODO: get the old info back if I miss it after yield refactor
        print('Phase 4: chopping up supertile x%u:%u y%u:%u' %
              (x0, x1, y0, y1))
        print("  Supertile: %s" % (img_fn, ))
        self.msg('step(x: %d, y: %d)' % (self.tw, self.th), 3)
        #self.msg('x in xrange(%d, %d, %d)' % (xt0, xt1, self.tw), 3)
        #self.msg('y in xrange(%d, %d, %d)' % (yt0, yt1, self.th), 3)

        # FIXME: causes issues saving .jpg
        # think only in newer ubuntu (ie 20.04 but not 16.04)
        if im.mode == "RGBA":
            im = pimage.rgba2rgb(im)

        for (y, x) in self.gen_supertile_tiles(st_bounds):
            # If we made it this far the tile can be constructed with acceptable enblend artifacts
            row = self.y2row(y)
            col = self.x2col(x)

            # Did we already do this tile?
            if self.is_done_rc(row, col):
                # No use repeating it although it would be good to diff some of these
                if self.verbose:
                    print('Rejecting tile x%d, y%d / r%d, c%d: already done' %
                          (x, y, row, col))
                continue

            # note that x and y are in whole pano coords
            # we need to adjust to our frame
            # row and col on the other hand are used for global naming
            self.make_tile(im, x - x0, y - y0, row, col)
            gen_tiles += 1
        bench.stop()
        print('Generated %d new tiles for a total of %d / %d in %s' %
              (gen_tiles, len(
                  self.closed_list_rc), self.net_expected_tiles, str(bench)))
        if gen_tiles == 0:
            raise NoTilesGenerated("Didn't generate any tiles")
        # temp_file should be automatically deleted upon exit
        # WARNING: not all are tmp files, some may be recycled supertiles

    def get_name(self, row, col):
        out_dir = ''
        if self.out_dir:
            out_dir = '%s/' % self.out_dir
        return '%sy%03d_x%03d%s' % (out_dir, row, col, self.out_extension)

    def make_tile(self, im, x, y, row, col):
        '''Make a tile given an image, the upper left x and y coordinates in that image, and the global row/col indices'''
        if self.dry:
            if self.verbose:
                print('Dry: not making tile w/ x%d y%d r%d c%d' %
                      (x, y, row, col))
            return
        xmin = x
        ymin = y
        width, height = im.size
        xmax = min(xmin + self.tw, width)
        ymax = min(ymin + self.th, height)
        nfn = self.get_name(row, col)

        if self.verbose:
            print('Subtile %s: (x %d:%d, y %d:%d)' %
                  (nfn, xmin, xmax, ymin, ymax))
        subimage = pimage.subimage(im, xmin, xmax, ymin, ymax)
        '''
        Images must be padded
        If they aren't they will be stretched in google maps
        '''
        if subimage.size[0] != self.tw or subimage.size[1] != self.th:
            dbg('WARNING: %s: expanding partial tile (%d X %d) to full tile size'
                % (nfn, subimage.size[0], subimage.size[1]))
            print("WARNING temp")
            subimage = pimage.set_canvas_size(subimage, self.tw, self.th)
        # http://www.pythonware.com/library/pil/handbook/format-jpeg.htm
        # JPEG is a good quality vs disk space compromise but beware:
        # The image quality, on a scale from 1 (worst) to 95 (best).
        # The default is 75.
        # Values above 95 should be avoided;
        # 100 completely disables the JPEG quantization stage.
        if subimage.mode != 'RGB':
            subimage = subimage.convert('RGB')
        subimage.save(nfn, quality=95)
        self.mark_done_rc(row, col)

    def x2col(self, x):
        col = int((x - self.x0) / self.tw)
        if col < 0:
            print("ERROR", x, self.x0, self.tw)
            raise Exception("Can't have negative col")
        return col

    def y2row(self, y):
        ret = int((y - self.y0) / self.th)
        if ret < 0:
            print("ERROR", y, self.y0, self.th)
            raise Exception("can't have negative row")
        return ret

    def is_done_rc(self, row, col):
        assert 0 <= row < self.rows() and 0 <= col < self.cols(
        ), "bad tile %ur %uc w/ %u rows %u cols" % (row, col, self.rows(),
                                                    self.cols())
        return (row, col) in self.closed_list_rc

    def mark_done_rc(self, row, col, current=True):
        assert 0 <= row < self.rows() and 0 <= col < self.cols(
        ), "bad tile %ur %uc w/ %u rows %u cols" % (row, col, self.rows(),
                                                    self.cols())
        # Some tiles may solve multiple times
        if (row, col) in self.open_list_rc:
            self.closed_list_rc.add((row, col))
            self.open_list_rc.remove((row, col))
            if current:
                self.this_tiles_done += 1
        # but it should be in at least one of the sets
        else:
            assert (
                row, col
            ) in self.closed_list_rc, "Completed bad tile %ur %uc w/ %u rows %u cols" % (
                row, col, self.rows(), self.cols())

    def n_tiles(self):
        return self.rows() * self.cols()

    def dump_open_list(self):
        print('Open list:')
        i = 0
        for (row, col) in self.open_list_rc:
            print('  r%d c%d' % (row, col))
            i += 1
            if i > 10:
                print('Break on large open list')
                break

    def rows(self):
        return int(math.ceil(1.0 * self.height() / self.th))

    def cols(self):
        return int(math.ceil(1.0 * self.width() / self.tw))

    def height(self):
        return abs(self.top() - self.bottom())

    def width(self):
        return abs(self.right() - self.left())

    def left(self):
        return self.x0

    def right(self):
        return self.x1

    def top(self):
        return self.y0

    def bottom(self):
        return self.y1

    def optimize_step(self):
        '''
        TODO: even out the steps, we can probably get slightly better results
        
        The ideal step is to advance to the next area where it will be legal to create a new 
        Slightly decrease the step to avoid boundary conditions
        Although we clip on both side we only have to get rid of one side each time
        '''
        #txstep = self.stw - self.clip_width - 1
        #tystep = self.sth - self.clip_height - 1
        pass

    def gen_supertiles(self, verbose=None):
        if verbose is None:
            verbose = self.verbose
        # 0:256 generates a 256 width pano
        # therefore, we don't want the upper bound included

        if verbose:
            print('M: Generating supertiles from y(%d:%d) x(%d:%d)' %
                  (self.top(), self.bottom(), self.left(), self.right()))
            print("Dry: %u" % self.dry)
        #row = 0
        y_done = False
        for y in range(self.top(), self.bottom(), self.super_t_ystep):
            y0 = y
            y1 = y + self.sth
            if y1 >= self.bottom():
                y_done = True
                y0 = max(self.top(), self.bottom() - self.sth)
                y1 = self.bottom()
                if self.verbose:
                    print(
                        'M: Y %d:%d would have overstretched, shifting to maximum height position %d:%d'
                        % (y, y + self.sth, y0, y1))

            #col = 0
            x_done = False
            for x in range(self.left(), self.right(), self.super_t_xstep):
                x0 = x
                x1 = x + self.stw
                # If we have reached the right side align to it rather than truncating
                # This makes blending better to give a wider buffer zone
                if x1 >= self.right():
                    x_done = True
                    x0 = max(self.left(), self.right() - self.stw)
                    x1 = self.right()
                    if self.verbose:
                        print(
                            'M: X %d:%d would have overstretched, shifting to maximum width position %d:%d'
                            % (x, x + self.stw, x0, x1))

                yield (x0, x1, y0, y1)

                #col += 1
                if x_done:
                    break
            #row +=1
            if y_done:
                break
        if verbose:
            print('M: All supertiles generated')

    def n_supertile_tiles(self, st_bounds):
        return len(list(self.gen_supertile_tiles(st_bounds)))

    def should_try_supertile(self, st_bounds):
        #print('M: checking supertile for existing tiles with %d candidates' % (
        #    self.n_supertile_tiles(st_bounds)))

        solves = 0
        net = 0
        for (y, x) in self.gen_supertile_tiles(st_bounds):
            # If we made it this far the tile can be constructed with acceptable enblend artifacts
            row = self.y2row(y)
            col = self.x2col(x)

            #print('Checking (r%d, c%d)' % (row, col))
            # Did we already do this tile?
            if not self.is_done_rc(row, col):
                solves += 1
            net += 1
        return (solves, net)

    def seed_merge(self):
        '''Add all already generated tiles to the closed list'''
        icm = ImageCoordinateMap.from_dir_tagged_file_names(self.out_dir)
        # may be incomplete, but it shouldn't be larger
        assert icm.rows <= self.rows() and icm.cols <= self.cols(
        ), "%u rows, %u cols but icm %u rows, %u cols" % (
            self.rows(), self.cols(), icm.rows, icm.cols)
        already_done = 0
        for (col, row) in icm.gen_set():
            self.mark_done_rc(row, col, False)
            already_done += 1
        print('Map seeded with %d already done tiles' % already_done)

    def wkill(self):
        print('Shutting down workers (dry: %s)' % self.dry)
        for worker in self.workers:
            worker.running.clear()
        print('Waiting for workers to exit...')
        for i, worker in enumerate(self.workers):
            worker.process.join(1)
            if worker.process.is_alive():
                print('  W%d: failed to join' % i)
                self.stale_worker = True
            else:
                print('  W%d: stopped' % i)

    def calc_expected_tiles(self):
        x_tiles_ideal = 1.0 * self.width() / self.tw
        x_tiles = math.ceil(x_tiles_ideal)
        y_tiles_ideal = 1.0 * self.height() / self.th
        y_tiles = math.ceil(y_tiles_ideal)
        self.net_expected_tiles = x_tiles * y_tiles
        ideal_tiles = x_tiles_ideal * y_tiles_ideal
        print('M: Ideal tiles: %0.3f x, %0.3f y tiles => %0.3f net' %
              (x_tiles_ideal, y_tiles_ideal, ideal_tiles))
        print('M: Expecting to generate x%d, y%d => %d basic tiles' %
              (x_tiles, y_tiles, self.net_expected_tiles))

    def core_dump(self, prefix=""):
        print("Writing state %s" % prefix)
        if prefix:
            prefix += "_"

        with open(os.path.join(self.log_dir, prefix + 'open_list.txt'),
                  "w") as f:
            for (row, col) in self.open_list_rc:
                f.write("%sr,%sc\n" % (row, col))

        with open(os.path.join(self.log_dir, prefix + 'closed_list.txt'),
                  "w") as f:
            for (row, col) in self.closed_list_rc:
                f.write("%sr,%sc\n" % (row, col))

        with open(os.path.join(self.log_dir, prefix + 'state.txt'), "w") as f:
            print("stw %u, sth %u" % (self.stw, self.sth), file=f)
            print("clip_width %u, clip_height %u" %
                  (self.clip_width, self.clip_height),
                  file=f)
            print("mem_worker_max %0.3f GB" % (self.mem_worker_max / 1e9, ),
                  file=f)
            print("mem_net_last %0.3f GB" % (self.mem_net_last / 1e9, ),
                  file=f)
            print("mem_net_max %0.3f GB" % (self.mem_net_max / 1e9, ), file=f)

        tile_freqs = dict()
        for st_bounds in self.gen_supertiles():
            for (tile_y, tile_x) in self.gen_supertile_tiles(st_bounds):
                tile_freqs[(tile_y, tile_x)] = tile_freqs.get(
                    (tile_y, tile_x), 0) + 1

        with open(os.path.join(self.log_dir, prefix + 'supertiles.txt'),
                  "w") as f:
            maxfreq = 0
            for st_bounds in self.gen_supertiles():
                x0, x1, y0, y1 = st_bounds
                st_bounds = tuple(st_bounds)
                is_closed = st_bounds in self.closed_sts
                print("st %ux0 %ux1 %uy0 %uy1 %uc" %
                      (x0, x1, y0, y1, is_closed),
                      file=f)
                for (tile_y, tile_x) in self.gen_supertile_tiles(st_bounds):
                    is_open = (tile_y, tile_x) in self.open_list_rc
                    is_closed = (tile_y, tile_x) in self.closed_list_rc
                    freq = tile_freqs[(tile_y, tile_x)]
                    maxfreq = max(freq, maxfreq)
                    print("    tile %ux %uy o%u c%u f%u" %
                          (tile_x, tile_y, is_open, is_closed, freq),
                          file=f)
            print("Max tile freq: %u" % maxfreq)

    def calc_vars(self):
        # in form (row, col)
        self.open_list_rc = set()
        self.closed_list_rc = set()
        for row in range(self.rows()):
            for col in range(self.cols()):
                self.open_list_rc.add((row, col))
        self.closed_sts = set()

    def profile(self):
        mem_net = 0
        for worker in self.workers:
            # mem_worker = worker.process.memory_info().rss
            mem_worker = pid_memory_recursive(worker.process.pid)
            self.mem_worker_max = max(self.mem_worker_max, mem_worker)
            mem_net += mem_worker
        self.mem_net_max = max(self.mem_net_max, mem_net)
        self.mem_net_last = mem_net

    def print_worker_logs_init(self):
        for worker in self.workers:
            worker.master_log_file_init()

    def print_worker_logs(self):
        for worker in self.workers:
            worker.master_log_file_print()

    def run(self):
        self.mem_net_last = 0
        self.mem_net_max = 0
        self.mem_worker_max = 0
        """
        if not self.dry:
            self.dry = True
            print("")
            print("")
            print("")
            print('***BEGIN DRY RUN***')
            self.run()
            print('***END DRY RUN***')
            print("")
            print("")
            print("")
            self.dry = False
        """

        self.calc_vars()
        self.worker_failures = 0

        print('Input images width %d, height %d' %
              (self.img_width, self.img_height))
        print('Output to %s' % self.out_dir)
        print('Super tile width %d, height %d from scalar %d' %
              (self.stw, self.sth, self.st_scalar_heuristic))
        print('Super tile x step %d, y step %d' %
              (self.super_t_xstep, self.super_t_ystep))
        print('Supertile clip width %d, height %d' %
              (self.clip_width, self.clip_height))

        if not self.ignore_crop and self.pto.get_panorama_line().getv(
                'S') is None:
            raise Exception('Not cropped.  Set ignore crop to force continue')
        '''
        if we have a width of 256 and 1 pixel we need total size of 256
        If we have a width of 256 and 256 pixels we need total size of 256
        if we have a width of 256 and 257 pixel we need total size of 512
        '''
        print('Tile width: %d, height: %d' % (self.tw, self.th))
        print('Net size: %d width (%d:%d) X %d height (%d:%d) = %d MP' %
              (self.width(), self.left(), self.right(), self.height(),
               self.top(), self.bottom(),
               self.width() * self.height() / 1000000))
        print('Output image extension: %s' % self.out_extension)

        bench = Benchmark()

        if os.path.exists(self.out_dir):
            self.seed_merge()

        if not self.dry:
            # Scrub old dir if we don't want it
            if os.path.exists(self.out_dir):
                print("WARNING: merging out into existing output")
            else:
                os.mkdir(self.out_dir)
            if os.path.exists(self.st_dir):
                print("WARNING: merging st into existing output")
            else:
                os.mkdir(self.st_dir)

        self.n_expected_sts = len(list(self.gen_supertiles(verbose=True)))
        print('M: Generating %d supertiles' % self.n_expected_sts)

        self.calc_expected_tiles()

        if self.is_full:
            print('M: full => forcing 1 thread ')
            self.threads = 1
        print('M: Initializing %d workers' % self.threads)
        self.workers = []
        for ti in range(self.threads):
            print('Bringing up W%02d' % ti)
            # print(to individual log files if many threaded to avoid garbling stream
            # can still conflict with master, but mostly safe...
            if self.threads == 1:
                print("Logging workers to foreground")
                log_fn = None
            else:
                log_fn = os.path.join(self.log_dir, 'w%02d.log' % ti)
            w = Worker(ti, self, log_fn)
            self.workers.append(w)
            w.start()

        print("")
        print("")
        print("")
        print('S' * 80)
        print('M: Serial end')
        print('P' * 80)
        n_closed = len(self.closed_list_rc)
        n_open = len(self.open_list_rc)
        n_tiles = self.n_tiles()
        print("closed list %u / %u tiles" % (n_closed, n_tiles))
        print("open list %u / %u tiles" % (n_open, n_tiles))
        self.core_dump("begin")
        self.print_worker_logs_init()
        assert n_closed <= n_tiles
        assert n_open <= n_tiles

        try:
            #temp_file = 'partial.tif'
            self.n_supertiles = 0
            st_gen = self.gen_supertiles()

            all_allocated = False
            last_progress = time.time()
            last_print = time.time()
            pair_submit = 0
            pair_complete = 0
            idle = False
            while not (all_allocated and pair_complete == pair_submit):
                progress = False
                self.profile()
                # Check for completed jobs
                for wi, worker in enumerate(self.workers):
                    # print("worker %u qo size %u" % (wi, worker.qo.qsize()))
                    try:
                        # out = worker.qo.get(False)
                        out = worker.qo.get_nowait()
                    except queue.Empty:
                        continue

                    # FIXME
                    # Why aren't W0 tasks coming back?
                    # assert wi != 0

                    pair_complete += 1
                    what = out[0]
                    progress = True

                    if what == 'done':
                        (st_bounds, img_fn) = out[1]
                        print('MW%d: done w/ submit %d, complete %d' %
                              (wi, pair_submit, pair_complete))
                        self.closed_sts.add(tuple(st_bounds))
                        # Dry run
                        if img_fn is None:
                            im = None
                        else:
                            im = Image.open(img_fn)
                        # hack
                        # ugh remove may be an already existing supertile (not a temp file)
                        #os.remove(img_fn)
                        try:
                            self.process_image(img_fn, im, st_bounds)
                        except NoTilesGenerated:
                            print("WARNING: image did not generate tiles %s" %
                                  img_fn)
                    elif what == 'exception':
                        if not self.ignore_errors:
                            for worker in self.workers:
                                worker.running.clear()
                            # let stdout clear up
                            # (only moderately effective)
                            time.sleep(1)

                        #(_task, e) = out[1]
                        print('!' * 80)
                        print('M: ERROR: MW%d failed w/ exception' % wi)
                        (_task, _e, estr) = out[1]
                        print('M: Stack trace:')
                        for l in estr.split('\n'):
                            print(l)
                        print('!' * 80)
                        if not self.ignore_errors:
                            raise Exception('M: shutdown on worker failure')
                        print('M WARNING: continuing despite worker failure')
                        self.worker_failures += 1
                    else:
                        print('M: %s' % (out, ))
                        raise Exception('M: internal error: bad task type %s' %
                                        what)

                    self.st_limit -= 1
                    if self.st_limit == 0:
                        print('Breaking on ST limit reached')
                        break

                # Any workers need more work?
                for wi, worker in enumerate(self.workers):
                    if all_allocated:
                        break
                    if worker.qi.empty():
                        while True:
                            try:
                                st_bounds = next(st_gen)
                            except StopIteration:
                                print('M: all tasks allocated')
                                all_allocated = True
                                break

                            progress = True

                            [x0, x1, y0, y1] = st_bounds
                            self.n_supertiles += 1
                            (st_solves,
                             st_net) = self.should_try_supertile(st_bounds)
                            print(
                                'M: check st %u (x(%d:%d) y(%d:%d)) want %u / %u tiles'
                                % (self.n_supertiles, x0, x1, y0, y1,
                                   st_solves, st_net))
                            if not st_solves:
                                print(
                                    'M WARNING: skipping supertile %d as it would not generate any new tiles'
                                    % self.n_supertiles)
                                continue

                            print('*' * 80)
                            #print('W%d: submit %s (%d / %d)' % (wi, repr(pair), pair_submit, n_pairs)
                            print(
                                "Creating supertile %d / %d with x%d:%d, y%d:%d"
                                % (self.n_supertiles, self.n_expected_sts, x0,
                                   x1, y0, y1))
                            print('W%d: submit' % (wi, ))

                            worker.qi.put((st_bounds, ))
                            pair_submit += 1
                            break

                def print_mem():
                    print("mem_net_last %0.3f GB" %
                          (self.mem_net_last / 1e9, ))
                    print("  mem_net_max %0.3f GB" %
                          (self.mem_net_max / 1e9, ))
                    print("  mem_worker_max %0.3f GB" %
                          (self.mem_worker_max / 1e9, ))

                if time.time() - last_print > 5 * 60:
                    print_mem()
                    last_print = time.time()

                if progress:
                    last_progress = time.time()
                    self.core_dump()
                    idle = False
                else:
                    # Prioritize master tasks, only print workers when idle
                    self.print_worker_logs()
                    if not idle:
                        print(
                            'M Server thread idle. dry %s, all %u, complete %u / %u'
                            % (self.dry, all_allocated, pair_complete,
                               pair_submit))
                        print_mem()
                        last_print = time.time()
                        #print(len(self.workers))
                        #print(self.workers[0].qo.qsize())
                        #print(self.workers[1].qo.qsize())
                    idle = True
                    # can take some time, but should be using smaller tiles now
                    if time.time() - last_progress > 4 * 60 * 60:
                        print('M WARNING: server thread stalled')
                        last_progress = time.time()
                        time.sleep(0.1)

            print("All pairs allocated and complete w/ %u failures" %
                  self.worker_failures)
            bench.stop()
            print(
                'M Processed %d supertiles to generate %d new (%d total) tiles in %s'
                % (self.n_expected_sts, self.this_tiles_done,
                   len(self.closed_list_rc), str(bench)))
            tiles_s = self.this_tiles_done / bench.delta_s()
            print('M %f tiles / sec, %f pix / sec' %
                  (tiles_s, tiles_s * self.tw * self.th))

            if len(self.closed_list_rc) != self.net_expected_tiles:
                print('M ERROR: expected to do %d basic tiles but did %d' %
                      (self.net_expected_tiles, len(self.closed_list_rc)))
                self.dump_open_list()
                raise Exception(
                    'State mismatch: expected %u basic tiles but open %u, closed %u, %u worker failures'
                    % (self.net_expected_tiles, len(self.open_list_rc),
                       len(self.closed_list_rc), self.worker_failures))

            # Gather up supertile filenames generated by workers
            # xxx: maybe we should tell slaves the file they should use?
            # Used by singlify?
            for worker in self.workers:
                while True:
                    try:
                        st_fn = worker.st_fns.get(False)
                    except queue.Empty:
                        break
                    self.st_fns.append(st_fn)

        finally:
            print("Preparing to shut down")
            print("    all_allocated: %s" % (all_allocated, ))
            print("    pair_complete: %s" % (pair_complete, ))
            print("    pair_submit: %s" % (pair_submit, ))
            print("    worker_failures: %s" % (self.worker_failures, ))
            print("    mem_worker_max %0.3f GB" %
                  (self.mem_worker_max / 1e9, ))
            print("    mem_net_max %0.3f GB" % (self.mem_net_max / 1e9, ))
            self.wkill()
            self.core_dump("final")
            self.workers = None

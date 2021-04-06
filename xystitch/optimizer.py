#!/usr/bin/env python
'''
xystitch
Copyright 2011 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''
'''
This file is used to optimize the size of an image project
It works off of the following idea:
-In the end all images must lie on the same focal plane to work as intended
-Hugin likes a default per image FOV of 51 degrees since thats a typical camera FOV
-With a fixed image width, height, and FOV as above we can form a natural focal plane
-Adjust the project focal plane to match the image focal plane


Note the following:
-Ultimately the project width/height determines the output width/height
-FOV values are not very accurate: only 1 degree accuracy
-Individual image width values are more about scaling as opposed to the total project size than their output width?
    Hugin keeps the closest 

A lot of this seems overcomplicated for my simple scenario
Would I be better off 

Unless I make the algorithm more advanced by correctly calculating all images into a focal plane (by taking a reference)
it is a good idea to at least assert that all images are in the same focal plane
'''

from xystitch import execute
from xystitch import microscopej
from xystitch.pto.util import img_cpls, PImage, ImageCoordinateMap
from xystitch.benchmark import Benchmark
from xystitch import statistics
from xystitch.config import config

import math

class NoRMS(Exception):
    pass

def debug(s=''):
    pass


'''
Convert output to PToptimizer form



http://wiki.panotools.org/PTOptimizer
    # The script must contain:
    # one 'p'- line describing the output image (eg Panorama)
    # one 'i'-line for each input image
    # one or several 'v'- lines listing the variables to be optimized.
    # the 'm'-line is optional and allows you to specify modes for the optimization.
    # one 'c'-line for each pair of control points



p line
    Remove E0 R0
        Results in message
            Illegal token in 'p'-line [69] [E] [E0 R0 n"PSD_mask"]
            Illegal token in 'p'-line [48] [0] [0 R0 n"PSD_mask"]
            Illegal token in 'p'-line [82] [R] [R0 n"PSD_mask"]
            Illegal token in 'p'-line [48] [0] [0 n"PSD_mask"]
    FOV must be < 180
        v250 => v179
        Results in message
            Destination image must have HFOV < 180
i line
    Must have FOV
        v51
        Results in message
            Field of View must be positive
    Must have width, height
        w3264 h2448
        Results in message
            Image height must be positive
    Must contain the variables to be optimized
        make sure d and e are there
        reference has them equal to -0, 0 seems to work fine



Converting back
Grab o lines and get the d, e entries
    Copy the entries to the matching entries on the original i lines
Open questions
    How does FOV effect the stitch?
'''


def prepare_pto(pto, reoptimize=True):
    '''Simply and modify a pto project enough so that PToptimizer will take it'''
    print('Stripping project')
    if 0:
        print(pto.get_text())
        print("")
        print("")
        print("")

    def fix_pl(pl):
        pl.remove_variable('E')
        pl.remove_variable('R')
        v = pl.get_variable('v')
        if v == None or v >= 180:
            print('Manipulating project field of view')
            pl.set_variable('v', 179)

    def fix_il(il):
        v = il.get_variable('v')
        if v == None or v >= 180:
            il.set_variable('v', 51)

        # panotools seems to set these to -1 on some ocassions
        if il.get_variable('w') == None or il.get_variable('h') == None or int(
                il.get_variable('w')) <= 0 or int(il.get_variable('h')) <= 0:
            img = PImage.from_file(il.get_name())
            il.set_variable('w', img.width())
            il.set_variable('h', img.height())

        for v in 'd e'.split():
            if il.get_variable(v) == None or reoptimize:
                il.set_variable(v, 0)
                #print 'setting var'

        nv = {}
        for k, v in il.variables.items():
            if k in [
                    'w', 'h', 'f', 'Va', 'Vb', 'Vc', 'Vd', 'Vx', 'Vy', 'd',
                    'e', 'g', 't', 'v', 'Vm', 'n'
            ]:
                nv[k] = v
        il.variables = nv

    fix_pl(pto.get_panorama_line())

    for il in pto.image_lines:
        fix_il(il)
        #print il
        #sys.exit(1)

    if 0:
        print("")
        print("")
        print('prepare_pto final:')
        print(pto)
        print("")
        print("")
        print('Finished prepping for PToptimizer')
    #sys.exit(1)


def merge_pto(ptoopt, pto):
    '''Take a resulting pto project and merge the coordinates back into the original'''
    '''
    o f0 r0 p0 y0 v51 d0.000000 e0.000000 u10 -buf 
    ...
    o f0 r0 p0 y0 v51 d-12.584355 e-1706.852324 u10 +buf -buf 
    ...
    o f0 r0 p0 y0 v51 d-2179.613104 e16.748410 u10 +buf -buf 
    ...
    o f0 r0 p0 y0 v51 d-2213.480518 e-1689.955438 u10 +buf 

    merge into
    

    # image lines
    #-hugin  cropFactor=1
    i f0 n"c0000_r0000.jpg" v51 w3264 h2448 d0 e0
    #-hugin  cropFactor=1
    i f0 n"c0000_r0001.jpg" v51 w3264 h2448  d0 e0
    #-hugin  cropFactor=1
    i f0 n"c0001_r0000.jpg" v51  w3264 h2448  d0 e0
    #-hugin  cropFactor=1
    i f0 n"c0001_r0001.jpg" v51 w3264 h2448 d0 e0
    
    note that o lines have some image ID strings before them but position is probably better until I have an issue
    '''

    # Make sure we are going to manipulate the data and not text
    pto.parse()

    base_n = len(pto.get_image_lines())
    opt_n = len(ptoopt.get_optimizer_lines())
    if base_n != opt_n:
        raise Exception(
            'Must have optimized same number images as images.  Base pto has %d and opt has %d'
            % (base_n, opt_n))
    opts = list()
    print()
    for i in range(len(pto.get_image_lines())):
        il = pto.get_image_lines()[i]
        ol = ptoopt.optimizer_lines[i]
        for v in 'd e'.split():
            val = ol.get_variable(v)
            debug('Found variable val to be %s' % str(val))
            il.set_variable(v, val)
            debug('New IL: ' + str(il))
        debug()


class PTOptimizer:
    def __init__(self, project):
        self.project = project
        self.debug = False
        # In practice I tend to get around 25 so anything this big signifies a real problem
        self.rms_error_threshold = 250.0
        # If set to true will clear out all old optimizer settings
        # If PToptimizer gets old values in it will use them as a base
        self.reoptimize = True

    def verify_images(self):
        first = True
        for i in self.project.get_image_lines():
            if first:
                self.w = i.width()
                self.h = i.height()
                self.v = i.fov()
                first = False
            else:
                if self.w != i.width() or self.h != i.height(
                ) or self.v != i.fov():
                    print(i.text)
                    print('Old width %d, height %d, view %d' % (self.w, self.h,
                                                                self.v))
                    print('Image width %d, height %d, view %d' % (
                        i.width(), i.height(), i.fov()))
                    raise Exception('Image does not match')

    def run(self):
        '''
        The base Hugin project seems to work if you take out a few things:
        Eb1 Eev0 Er1 Ra0 Rb0 Rc0 Rd0 Re0 Va1 Vb0 Vc0 Vd0 Vx-0 Vy-0
        So say generate a project file with all of those replaced
        
        In particular we will generate new i lines
        To keep our original object intact we will instead do a diff and replace the optimized things on the old project
        
        
        Output is merged into the original file and starts after a line with a single *
        Even Hugin wpon't respect this optimization if loaded in as is
        Gives lines out like this
        
        o f0 r0 p0 y0 v51 a0.000000 b0.000000 c0.000000 g-0.000000 t-0.000000 d-0.000000 e-0.000000 u10 -buf 
        These are the lines we care about
        
        C i0 c0  x3996.61 y607.045 X3996.62 Y607.039  D1.4009 Dx-1.15133 Dy0.798094
        Where D is the magnitutde of the distance and x and y are the x and y differences to fitted solution
        
        There are several other lines that are just the repeats of previous lines
        '''
        bench = Benchmark()

        # The following will assume all of the images have the same size
        self.verify_images()

        # Copy project so we can trash it
        project = self.project.copy()
        prepare_pto(project, self.reoptimize)

        pre_run_text = project.get_text()
        if 0:
            print("")
            print("")
            print('PT optimizer project:')
            print(pre_run_text)
            print("")
            print("")

        # "PToptimizer out.pto"
        args = ["PToptimizer"]
        args.append(project.get_a_file_name())
        #project.save()
        rc = execute.without_output(args)
        if rc != 0:
            fn = '/tmp/pr0nstitch.optimizer_failed.pto'
            print("")
            print("")
            print('Failed rc: %d' % rc)
            print('Failed project save to %s' % (fn, ))
            try:
                open(fn, 'w').write(pre_run_text)
            except:
                print('WARNING: failed to write failure')
            print("")
            print("")
            raise Exception('failed position optimization')
        # API assumes that projects don't change under us
        project.reopen()
        '''
        Line looks like this
        # final rms error 24.0394 units
        '''
        rms_error = None
        for l in project.get_comment_lines():
            if l.find('final rms error') >= 00:
                rms_error = float(l.split()[4])
                break
        print('Optimize: RMS error of %f' % rms_error)
        # Filter out gross optimization problems
        if self.rms_error_threshold and rms_error > self.rms_error_threshold:
            raise Exception("Max RMS error threshold %f but got %f" %
                            (self.rms_error_threshold, rms_error))

        if self.debug:
            print('Parsed: %s' % str(project.parsed))

        if self.debug:
            print("")
            print("")
            print("")
            print('Optimized project:')
            print(project)
            #sys.exit(1)
        print('Optimized project parsed: %d' % project.parsed)

        print('Merging project...')
        merge_pto(project, self.project)
        if self.debug:
            print(self.project)

        bench.stop()
        print('Optimized project in %s' % bench)


'''
Calculate average x/y position
NOTE: x/y deltas are positive right/down
But global coordinates are positive left,up
Return positive left/up convention to match global coordinate system
'''


def il_pair_deltas(cpl_index, l_il, r_il):
    # lesser line
    l_ili = l_il.get_index()
    # Find matching control points
    cps_x = []
    cps_y = []
    for cpl in cpl_index.get((l_ili, r_il), []):
        # compute distance
        # note: these are relative coordinates to each image
        # and strictly speaking can't be directly compared
        # however, because the images are the same size the width/height can be ignored
        cps_x.append(cpl.getv('x') - cpl.getv('X'))
        cps_y.append(cpl.getv('y') - cpl.getv('Y'))
    for cpl in cpl_index.get((r_il, l_ili), []):
        cps_x.append(cpl.getv('X') - cpl.getv('x'))
        cps_y.append(cpl.getv('Y') - cpl.getv('y'))

    # Possible that no control points due to failed stitch
    # or due to edge case
    if len(cps_x) == 0:
        return None
    else:
        # XXX: actually, we might be better doing median or something like that
        return (1.0 * sum(cps_x) / len(cps_x), 1.0 * sum(cps_y) / len(cps_y))


def pto2icm(pto):
    fns = []
    for il in pto.get_image_lines():
        fns.append(il.get_name())
    return ImageCoordinateMap.from_tagged_file_names(fns)


def cpl_im_abs(cpl, n_il, N_il):
    """
    Return absolute (x, y), (X, Y) for n, N
    Relative to image center since thats the normal global cooridnate system

    NOTE: x/y deltas are positive right/down
    But global coordinates are positive left,up
    Additionally deltas are relative to image edge while global coordinate are relative to center
    Return positive left/up convention to match global coordinate system
    """

    width = n_il.width()
    assert width == N_il.width()
    height = n_il.height()
    assert height == N_il.height()
    #n_il, N_il = N_il, n_il
    n_xy = (n_il.getv('d') - (cpl.getv('x') - width / 2),
            n_il.getv('e') - (cpl.getv('y') - height / 2))
    N_xy = (N_il.getv('d') - (cpl.getv('X') - width / 2),
            N_il.getv('e') - (cpl.getv('Y') - height / 2))
    return (n_xy, N_xy)


def gen_cps(pto, icm=None):
    """
    For every control point yield
    ((n_fn, N_fn), (nx, ny), (Nx, Ny))
    Where x and y are global coordinates
    """

    if icm is None:
        icm = pto2icm(pto)

    for cpl in pto.control_point_lines:
        n_il = pto.image_lines[cpl.get_variable('n')]
        n_fn = n_il.get_name()
        N_il = pto.image_lines[cpl.get_variable('N')]
        N_fn = N_il.get_name()
        n_xy, N_xy = cpl_im_abs(cpl, n_il, N_il)
        yield cpl, ((n_fn, N_fn), n_xy, N_xy)


def set_il_by_points(il, points):
    """
    Set image based on neighboring image (control point) distances
    As of 2020-10-23 control points are aggregated into image sets
    Typically there are 1-2 existing images at a time, but in theory there could be 4
    Could throw out outliers but probably doesn't buy a lot
    """

    points_x = [p[0] for p in points]
    xpos = 1.0 * sum(points_x) / len(points_x)
    il.set_x(xpos)

    points_y = [p[1] for p in points]
    ypos = 1.0 * sum(points_y) / len(points_y)
    il.set_y(ypos)

    return xpos, ypos


def get_neighbor_distances(closed_set, pairsx, pairsy, x, y, order):
    """
    Create a set of estimates for an image based on known neighboring image distances
    """

    # see what we can gather from
    # list of [xcalc, ycalc]
    points = []

    # X
    # left
    # do we have a fixed point to the left?
    o = closed_set.get((x - order, y), None)
    if o:
        d = pairsx.get((x - order + 1, y), None)
        # and a delta to get to it?
        if d:
            dx, dy = d
            points.append((o[0] - dx * order, o[1] - dy * order))
    # right
    o = closed_set.get((x + order, y), None)
    if o:
        d = pairsx.get((x + order, y), None)
        if d:
            dx, dy = d
            points.append((o[0] + dx * order, o[1] + dy * order))

    # Y
    o = closed_set.get((x, y - order), None)
    if o:
        d = pairsy.get((x, y - order + 1), None)
        if d:
            dx, dy = d
            points.append((o[0] - dx * order, o[1] - dy * order))
    o = closed_set.get((x, y + order), None)
    if o:
        d = pairsy.get((x, y + order), None)
        if d:
            dx, dy = d
            points.append((o[0] + dx * order, o[1] + dy * order))

    return points


def attach_image_adjacent(project,
                          icm,
                          closed_set,
                          pairsx,
                          pairsy,
                          order=1,
                          verbose=False):
    """
    Starting with closed_set, look for images adjacent to images in closed_set
    and attach them
    order: how far away to search for a matching image
    """
    iters = 0
    while True:
        iters += 1
        print(('Iters %d' % iters))
        fixes = 0
        # no status prints here, this loop is very quick
        # FIXME: should start in center and work out
        # this probably introduces a lot of bias as currently done
        for y in range(icm.height()):
            for x in range(icm.width()):
                if (x, y) in closed_set:
                    continue
                img = icm.get_image(x, y)
                # Skip missing images
                if img is None:
                    continue

                points = get_neighbor_distances(closed_set, pairsx, pairsy, x,
                                                y, order)

                # Nothing useful?
                if len(points) == 0:
                    continue

                if verbose:
                    print('  %03dX, %03dY: setting' % (x, y))
                    for p in points:
                        print('    ', p)

                # use all available anchor points from above
                il = project.img_fn2il[img]
                xpos, ypos = set_il_by_points(il, points)
                closed_set[(x, y)] = (xpos, ypos)
                fixes += 1
        print(('Iter fixes: %d' % fixes))
        if fixes == 0:
            print('Break on stable output')
            break
    print(('%d iters' % iters))
    print(("Closed set: %u / %u" %
          (len(closed_set), icm.width() * icm.height())))


def closest_solved_cr(icm, closed_set, cin, rin, xbase, xorder, ybase, yorder):
    for ccheck, rcheck in iter_center_cr(icm, cin, rin):
        if ccheck % xorder != xbase or rcheck % yorder != ybase:
            continue
        if (ccheck, rcheck) in closed_set:
            return (ccheck, rcheck)
    raise Exception("Failed to find a solved image to interpolate from")


def filter_pairs_order(pairsx, pairsy, xbase, xorder, ybase, yorder):
    pairsx2 = dict()
    for k, v in list(pairsx.items()):
        col, row = k
        # if col % xorder == xbase and row % yorder == ybase:
        if row % yorder == ybase:
            pairsx2[k] = v
    print(("filter pairsx %u => %u" % (len(pairsx), len(pairsx2))))

    pairsy2 = dict()
    for k, v in list(pairsy.items()):
        col, row = k
        # if col % xorder == xbase and row % yorder == ybase:
        if col % xorder == xbase:
            pairsy2[k] = v
    print(("filter pairsy %u => %u" % (len(pairsy), len(pairsy2))))

    return pairsx2, pairsy2


def attach_image_linear(project, icm, closed_set, pairsx, pairsy, xbase,
                        xorder, ybase, yorder):
    '''
    Last ditch effort to solve an image
    Find the closest solved image (even if far away)
    and do linear approximation to its position
    
    XXX: could find several close images to improve accuracy?
    '''

    print(('Linear approximation x=range(%u, w+1, %u), y=range(%u, h+1, %u)' %
          (xbase, xorder, ybase, yorder)))
    """
    Filter out any pairs that aren't in our linear set
    Closest image may be further away but it will be using the same linear model
    """
    pairsx, pairsy = filter_pairs_order(pairsx, pairsy, xbase, xorder, ybase,
                                        yorder)

    def avg(vals, s):
        vals = [x for x in vals if x is not None]
        vals = [s(val) for val in vals]
        if len(vals) == 0:
            return None
        return sum(vals) / len(vals)

    pairsx_avg = (avg(list(pairsx.values()),
                      lambda x: x[0]), avg(list(pairsx.values()), lambda x: x[1]))
    print(('pairsx: %s' % (pairsx_avg, )))
    pairsy_avg = (avg(list(pairsy.values()),
                      lambda x: x[0]), avg(list(pairsy.values()), lambda x: x[1]))
    print(('pairsy: %s' % (pairsy_avg, )))

    # Only anchor to cleanly solved images
    closed_set_orig = set(closed_set)
    fixes = set()
    for r in range(ybase, icm.height(), yorder):
        for c in range(xbase, icm.width(), xorder):
            if (c, r) in closed_set:
                continue
            img = icm.get_image(c, r)
            # Skip missing images
            if img is None:
                continue

            anch_c, anch_r = closest_solved_cr(icm, closed_set_orig, c, r,
                                               xbase, xorder, ybase, yorder)
            anch_x, anch_y = closed_set[(anch_c, anch_r)]

            # ship it: "all working image programs have an even number of sign errors"
            xpos = anch_x - (c - anch_c) * pairsx_avg[0] - (
                r - anch_r) * pairsy_avg[0]
            ypos = anch_y - (c - anch_c) * pairsx_avg[1] - (
                r - anch_r) * pairsy_avg[1]
            print((
                'Interpolate %s (c%u, r%u) @ %0.1fx, %0.1fy => (%0.1fx, %0.1fy)'
                % (img, anch_c, anch_r, anch_x, anch_y, xpos, ypos)))
            # use all available anchor points from above
            il = project.img_fn2il[img]
            il.set_x(xpos)
            il.set_y(ypos)
            closed_set[(c, r)] = (xpos, ypos)
            fixes.add((c, r))
    print(("Closed set %u => %u (%u fixes)" %
          (len(closed_set_orig), len(closed_set), len(fixes))))


def compute_u_sd(icm, pairs, xbase, xorder, ybase, yorder):
    print('Computing stat')
    pointsx = []
    pointsy = []
    for y in range(ybase, icm.height(), yorder):
        for x in range(xbase, icm.width(), xorder):
            # Missing image
            try:
                d = pairs[(x, y)]
            except KeyError:
                continue
            # No control points
            if d is None:
                continue
            dx, dy = d
            pointsx.append(dx)
            pointsy.append(dy)

    if len(pointsx) <= 1:
        print("WARNING: insufficient data to compute u/sd")
        return None

    x_sd = statistics.stdev(pointsx)
    x_u = statistics.mean(pointsx)
    print(('X mean: %0.3f' % x_u))
    print(('X SD:   %0.3f' % x_sd))

    y_sd = statistics.stdev(pointsy)
    y_u = statistics.mean(pointsy)
    print(('Y mean: %0.3f' % y_u))
    print(('Y SD:   %0.3f' % y_sd))

    return x_u, x_sd, y_u, y_sd


def remove_u_sd(icm, pairs, stdev, xbase, xorder, ybase, yorder, x_u, x_sd,
                y_u, y_sd):
    '''
        x_thresh = abs(x_u) + abs(x_sd) * stdev
        y_thresh = abs(y_u) + abs(y_sd) * stdev
        print 'X thresh: %0.3f' % x_thresh
        print 'Y thresh: %0.3f' % y_thresh
        '''
    x_min = x_u - x_sd * stdev
    x_max = x_u + x_sd * stdev
    print(('X : %0.3f to %0.3f' % (x_min, x_max)))
    y_min = y_u - y_sd * stdev
    y_max = y_u + y_sd * stdev
    print(('Y : %0.3f to %0.3f' % (y_min, y_max)))

    removed = 0
    npairs = 0
    for y in range(ybase, icm.height(), yorder):
        for x in range(xbase, icm.width(), xorder):
            # Missing image
            try:
                d = pairs[(x, y)]
            except KeyError:
                continue
            # No control points
            if d is None:
                continue
            npairs += 1
            dx, dy = d
            if (dx < x_min or dx > x_max) or (dy < y_min or dy > y_max):
                print('Ignoring x%d y%d: fail %0.1f < %0.1f dx < %0.1f and %0.1f < %0.1f dy < %0.1f' % (
                    x, y, x_min, dx, x_max, y_min, dy, y_max))
                pairs[(x, y)] = None
                removed += 1
    print(('Removed %d / %d pairs' % (removed, npairs)))


def check_pair_outlier_u_sd(icm, pairs, xbase, xorder, ybase, yorder, stdev=3):
    """
    xorder, yorder: how many rows/cols to group together
    """

    print((
        'Checking for outliers by u/sd, x=range(%u, w+1, %u), y=range(%u, h+1, %u)'
        % (xbase, xorder, ybase, yorder)))
    val = compute_u_sd(icm, pairs, xbase, xorder, ybase, yorder)
    if not stdev or val is None:
        print('stdev filter: none')
    else:
        x_u, x_sd, y_u, y_sd = val
        print(('stdev filter: %0.3f' % stdev))
        remove_u_sd(icm, pairs, stdev, xbase, xorder, ybase, yorder, x_u, x_sd,
                    y_u, y_sd)


def iter_center(icm, cent_col=None, cent_row=None, deltas=None):
    """
    Generate points starting from center and working outward
    Attempts to minimize errors caused by longer stretches
    """

    # Try center first, then work outward
    # Center should propagate the lowest error
    if cent_col is None:
        cent_col = icm.width() // 2
    if cent_row is None:
        cent_row = icm.height() // 2
    if deltas is None:
        deltas = max(icm.width() // 2, icm.height() // 2) + 1
    for delta in range(deltas):
        """
        Find the smaller delta and work generally outword
        Negative is generated first => do both positive before increasing number
        """

        xmin = max(0, cent_col - delta)
        ymin = max(0, cent_row - delta)
        xmax = min(icm.width(), cent_col + delta + 1)
        ymax = min(icm.height(), cent_row + delta + 1)
        for y in range(ymin, ymax):
            for x in range(xmin, xmax):
                if x == cent_col - delta or x == cent_col + delta or y == cent_row - delta or y == cent_row + delta:
                    yield x, y


def iter_center_cr(icm, col, row):
    # FIXME: optimize
    deltas = max(icm.width(), icm.height())
    return iter_center(icm, cent_col=col, cent_row=row, deltas=deltas)

def iter_center_cr_max(icm, col, row, xydelta):
    for acol, arow in iter_center_cr(icm, col, row):
        if abs(col - acol) > xydelta or abs(row - arow) > xydelta:
            return
        yield acol, arow

def anchor(project, icm, use_cr=None):
    '''
    Chose an anchor image to stitch project
    The image is located in the given project and the (col, row) is returned
    Exception thrown if an anchor can't be chosen
    (happens if no control points)
    '''

    ret = []

    def try_anch(anch_c, anch_r):
        # Image must exist
        img = icm.get_image(anch_c, anch_r)
        if img is None:
            return False
        # Must be linked to at least one other image
        il = project.img_fn2il[img]
        cpls = img_cpls(project, il.get_index())
        if len(cpls) == 0:
            return False
        # Only anchor if control points
        print(('Chose anchor image: %s' % img))
        ret.append((anch_c, anch_r))
        anch_il = project.img_fn2il[img]
        anch_il.set_x(0.0)
        anch_il.set_y(0.0)
        return True

    if use_cr:
        col, row = use_cr
        assert try_anch(col, row), "Bad anchor given"
        return (col, row)

    for col, row in iter_center(icm):
        if try_anch(col, row):
            return (col, row)
    raise Exception('Couldnt find anchor image (no control points?)')


def index_cpls(project):
    """
    ret[(n, N)] = [list of cpls]
    """
    ret = {}
    for cpl in project.control_point_lines:
        ret.setdefault((cpl.getv('n'), cpl.getv('N')), []).append(cpl)
    return ret


def icm_il_pairs(project, icm):
    # dictionary of results so that we can play around with post-processing result
    # This step takes by far the longest in the optimization process
    pairsx = {}
    pairsy = {}
    cpl_index = index_cpls(project)
    # start with simple algorithm where we just sweep left/right
    for y in range(0, icm.height()):
        print('Calc delta with Y %d / %d' % (y + 1, icm.height()))
        for x in range(0, icm.width()):
            img = icm.get_image(x, y)
            # Skip missing images
            if img is None:
                continue
            il = project.img_fn2il[img]
            ili = il.get_index()
            if x > 0:
                img = icm.get_image(x - 1, y)
                if img:
                    pairsx[(x, y)] = il_pair_deltas(cpl_index,
                                                    project.img_fn2il[img],
                                                    ili)
                else:
                    pairsx[(x, y)] = None
            if y > 0:
                img = icm.get_image(x, y - 1)
                if img:
                    pairsy[(x, y)] = il_pair_deltas(cpl_index,
                                                    project.img_fn2il[img],
                                                    ili)
                else:
                    pairsy[(x, y)] = None
    return pairsx, pairsy


def xy_opt(project,
           icm,
           verbose=False,
           stdev=None,
           anchor_cr=None,
           should_check_poor_opt=True):
    '''
    FIXME: implementation is extremely inefficient
    Change to do a single pass on control points, indexing results
    See pr0ncp for example

    Generates row/col to use for initial image placement
    spiral pattern outward from center
    
    Assumptions:
    -All images must be tied together by at least one control point
    
    NOTE:
    If we produce a bad mapping ptooptimizer may throw away our hint
    
    FIXME: the term "order" is overloaded here
    Split and/or make consistent
    '''
    # reference position
    #xc = icm.width() / 2
    #yc = icm.height() / 2
    project.build_image_fn_map()

    def printd(s):
        if verbose:
            print(s)

    try:
        rms_this = get_rms(project)
        if rms_this is not None:
            print(('Pre-opt: exiting project RMS error: %f' % rms_this))
    except NoRMS:
        pass

    # NOTE: algorithm will still run with missing control points to best of its ability
    # however, its expected that user will only run it on copmlete data sets
    if verbose:
        fail = False
        counts = {}
        for cpl in project.get_control_point_lines():
            n = cpl.getv('n')
            counts[n] = counts.get(n, 0) + 1
            N = cpl.getv('N')
            counts[N] = counts.get(N, 0) + 1
        print('Control point counts:')
        for y in range(0, icm.height()):
            for x in range(0, icm.width()):
                img = icm.get_image(x, y)
                if img is None:
                    continue
                il = project.img_fn2il[img]
                ili = il.get_index()
                count = counts.get(ili, 0)
                print(('  %03dX, %03dY: %d' % (x, y, count)))
                if count == 0:
                    print('    ERROR: no control points')
                    fail = True
        if fail:
            raise Exception('One or more images do not have control points')

    # (x, y) keyed dict gives the delta to the left or up
    # That is, (0, 0) is not included
    pairsx, pairsy = icm_il_pairs(project, icm)

    if verbose:
        print('Delta map')
        for y in range(0, icm.height()):
            for x in range(0, icm.width()):
                print('  %03dX, %03dY' % (x, y))

                p = pairsx.get((x, y), None)
                if p is None:
                    print('    X: none')
                else:
                    print('    X: %0.3fx, %0.3fy' % (p[0], p[1]))

                p = pairsy.get((x, y), None)
                if p is None:
                    print('    Y: none')
                else:
                    print('    Y: %0.3fx, %0.3fy' % (p[0], p[1]))

    print("")
    # Remove anything that is grossly outside of expected overlap
    check_pair_outlier_overlap(icm, pairsx, pairsy)
    """
    Today serpentine pattern left/right
    As a result rows alterate pattern due to backlash
    So group outliers by alternating rows
    This means we need to check first for even rows and then for odd rows
    Removing these now means regression later won't use them
    """
    print("")
    # Serpentine even rows
    check_pair_outlier_u_sd(icm,
                            pairsx,
                            xbase=0,
                            xorder=1,
                            ybase=0,
                            yorder=2,
                            stdev=stdev)
    print("")
    # Serpentine odd rows
    check_pair_outlier_u_sd(icm,
                            pairsy,
                            xbase=0,
                            xorder=1,
                            ybase=1,
                            yorder=2,
                            stdev=stdev)
    print("")

    # Chose an image in the center to attach other images to
    anch_c, anch_r = anchor(project, icm, use_cr=anchor_cr)
    closed_set = {(anch_c, anch_r): (0.0, 0.0)}

    print("")
    print("")
    # Attach images to neighbors starting in middle and working outward
    # For a healthy stitch this should attach all images
    print('First pass: adjacent images')
    attach_image_adjacent(project,
                          icm,
                          closed_set,
                          pairsx,
                          pairsy,
                          order=1,
                          verbose=verbose)
    """
    print("")
    print("")
    # If an image couldn't be connected directly, guess based on nearby data?
    print('Second pass: adjacent adjacent images')
    attach_image_adjacent(
        project, icm, closed_set, pairsx, pairsy, order=2, verbose=verbose)
    """

    print("")
    print("")
    # Serpentine even rows
    attach_image_linear(project,
                        icm,
                        closed_set,
                        pairsx,
                        pairsy,
                        xbase=0,
                        xorder=1,
                        ybase=0,
                        yorder=2)
    print("")
    print("")
    # Serpentine odd rows
    attach_image_linear(project,
                        icm,
                        closed_set,
                        pairsx,
                        pairsy,
                        xbase=0,
                        xorder=1,
                        ybase=1,
                        yorder=2)

    print("")
    print("")
    # critical image => couldn't locate
    print('Checking for critical images')
    for y in range(icm.height()):
        for x in range(icm.width()):
            if (x, y) in closed_set:
                continue
            img = icm.get_image(x, y)
            # Skip missing images
            if img is None:
                continue
            print(('  WARNING: un-located image %s' % img))
            # actually should locate all images with current algorithm
            assert 0

    print("")
    print("")
    if should_check_poor_opt:
        print('Checking for poorly optimized images')
        check_poor_opt(project, icm)
    else:
        print('Checking for poorly optimized images skipped')

    print("")
    print("")
    if verbose:
        print('Final position optimization:')
        for y in range(icm.height()):
            for x in range(icm.width()):
                p = closed_set.get((x, y))
                if p is None:
                    print(('  % 3dX, % 3dY: none' % (x, y)))
                else:
                    print(('  % 3dX, % 3dY: %6.1fx, %6.1fy' %
                          (x, y, p[0], p[1])))

    rms_this = get_rms(project)
    print(('Pre-opt: final RMS error: %f' % rms_this))

    # internal use only
    return closed_set


def iter_rms(project):
    for cpl in project.control_point_lines:
        n = cpl.get_variable('n')
        imgn = project.image_lines[n]
        N = cpl.get_variable('N')
        imgN = project.image_lines[N]

        # global coordinates (d/e) are positive upper left
        # but image coordinates (x/X//y/Y) are positive down right
        # wtf?
        # invert the sign so that the math works out
        try:
            dx2 = ((imgn.getv('d') - cpl.getv('x')) -
                   (imgN.getv('d') - cpl.getv('X')))**2
            dy2 = ((imgn.getv('e') - cpl.getv('y')) -
                   (imgN.getv('e') - cpl.getv('Y')))**2
        # Abort RMS if not all variables defined
        except TypeError:
            raise NoRMS("Missing variable (%s, %s, %s)" % (imgn.text, imgN.text, cpl.text))

        if 0:
            print('iter')
            print(('  ', imgn.text))
            print(('  ', imgN.text))
            print(('  ', imgn.getv('d'), cpl.getv('x'), imgN.getv('d'),
                  cpl.getv('X')))
            print(('  %f vs %f' % ((imgn.getv('d') + cpl.getv('x')),
                                  (imgN.getv('d') + cpl.getv('X')))))
            print(('  ', imgn.getv('e'), cpl.getv('y'), imgN.getv('e'),
                  cpl.getv('Y')))
            print(('  %f vs %f' % ((imgn.getv('e') + cpl.getv('y')),
                                  (imgN.getv('e') + cpl.getv('Y')))))

        rms_this = math.sqrt(dx2 + dy2)
        yield cpl, n, imgn, N, imgN, rms_this 

def get_rms(project):
    '''Calculate the root mean square error between control points'''
    rms = 0.0
    for _cpl, _n, _imgn, _N, _imgN, rms_this in iter_rms(project):
        rms += rms_this
    return rms / len(project.control_point_lines)


def check_poor_opt(project, icm=None):
    """
    Remove images that got moved to a position well outside of expected image position
    based on linear regression of image positions
    """

    ox, oy = microscopej.load_parameters()
    ox *= config.imgw
    oy *= config.imgh
    # First order tolerance
    # ie x change in x direction
    tol_1 = ox + config.poor_opt_thresh()
    # Second order tolernace
    # ie x change in y direction
    tol_2 = config.poor_opt_thresh()

    def ildiff(imgl, imgr):
        '''
        return l - r as dx, dy
        '''
        ill = project.img_fn2il[imgl]
        ilr = project.img_fn2il[imgr]
        dx = ill.x() - ilr.x()
        dy = ill.y() - ilr.y()
        return dx, dy

    def check(refr, refc):
        ret = True
        img = icm.get_image(refc, refr)
        # Skip missing imagesx
        if img is None:
            return True

        # Global coordinates positive upper left
        # icm positive upper
        if refc > 0:
            imgl = icm.get_image(refc - 1, refr)
            if imgl:
                dx, dy = ildiff(imgl, img)
                # Expected delta vs actual
                got = abs(dx - ox)
                if got > tol_1:
                    print(('%s-%s: x-x tolerance 1 %d > expect %d' %
                          (img, imgl, got, tol_1)))
                    ret = False
                got = abs(dy)
                if got > tol_2:
                    print(('%s-%s: y-y tolerance 2 %d > expect %d' %
                          (img, imgl, got, tol_2)))
                    ret = False
        if refr > 0:
            imgl = icm.get_image(refc, refr - 1)
            if imgl:
                dx, dy = ildiff(imgl, img)
                # Expected delta vs actual
                got = abs(dx)
                if got > tol_2:
                    print(('%s-%s: x-x tolerance 2 %d > expect %d' %
                          (img, imgl, got, tol_2)))
                    ret = False
                got = abs(dy - oy)
                if got > tol_1:
                    print(('%s-%s: y-y tolerance 1 %d > expect %d' %
                          (img, imgl, got, tol_1)))
                    ret = False
        return ret

    fails = 0
    for refr in range(icm.height()):
        for refc in range(icm.width()):
            if not check(refr, refc):
                fails += 1
    if fails:
        print(('WARNING: %d suspicious optimization result(s)' % fails))
    else:
        print('OK')


def check_pair_outlier_overlap(icm, pairsx, pairsy):
    """
    Verify images move in roughly an XY grid
    Invalid an image if it goes more than 10% out of expected overlap
    That is, when moving x should roughly move 70% in X and roughly 0% in Y
    But tolerate 60 to 80% in X and -10 to +10% in Y

    TODO: make threshold configurable
    Also consider breaking into more specific dxdy type limits
    """

    print('Checking for outliers by overlap')
    #return

    # FIXME: calculate from actual image size + used overlap
    # Use an expected max angle

    # x, y ideal overlap as fraction
    ox_frac, oy_frac = microscopej.load_parameters()
    # Convert to pixels
    ox_pix = config.imgw * ox_frac
    oy_pix = config.imgh * oy_frac

    thresh = config.overlap_outlier_thresh()
    # First order tolerance
    # ie x change in x direction
    tolx_1 = ox_pix + config.imgw * thresh
    # Keep same tolerance for X and Y
    # x is wider => larger
    toly_1 = oy_pix + config.imgw * thresh
    # Second order tolernace
    # ie x change in y direction
    tol_2 = config.imgw * thresh

    fails = 0
    # x, y
    npairs = [0, 0]

    def check(refc, refr):
        ret = True
        pairx = pairsx.get((refc, refr), None)
        if pairx is not None:
            npairs[0] += 1
            dx, dy = pairx
            img = icm.get_image(refc, refr)
            imgl = icm.get_image(refc - 1, refr)
            got = abs(dx - ox_pix)
            if got > tolx_1:
                print('%s-%s: x-x tolerance 1 %d > expect %d' % (img, imgl,
                                                                 got, tolx_1))
                ret = False
                pairsx[(refc, refr)] = None
                pairsy[(refc, refr)] = None
            got = abs(dy)
            if got > tol_2:
                print('%s-%s: y-y tolerance 2 %d > expect %d' % (img, imgl,
                                                                 got, tol_2))
                ret = False
                pairsx[(refc, refr)] = None
                pairsy[(refc, refr)] = None
        pairy = pairsy.get((refc, refr), None)
        if pairy is not None:
            npairs[1] += 1
            dx, dy = pairy
            img = icm.get_image(refc, refr)
            imgl = icm.get_image(refc, refr - 1)
            got = abs(dx)
            if got > tol_2:
                print('%s-%s: x-x tolerance 2 %d > expect %d' % (img, imgl,
                                                                 got, tol_2))
                ret = False
                pairsx[(refc, refr)] = None
                pairsy[(refc, refr)] = None
            got = abs(dy - oy_pix)
            if got > toly_1:
                print('%s-%s: y-y tolerance 1 %d > expect %d' % (img, imgl,
                                                                 got, toly_1))
                ret = False
                pairsx[(refc, refr)] = None
                pairsy[(refc, refr)] = None
        return ret

    for refr in range(icm.height()):
        for refc in range(icm.width()):
            if not check(refc, refr):
                fails += 1

    if fails:
        print((
            'WARNING: removed %d / (%dx %dy) suspicious optimization result(s)'
            % (fails, npairs[0], npairs[1])))
    else:
        print('OK')


class XYOptimizer:
    def __init__(self, project):
        self.project = project
        self.debug = False
        self.icm = None
        self.stdev = None

    def verify_images(self):
        first = True
        for i in self.project.get_image_lines():
            if first:
                self.w = i.width()
                self.h = i.height()
                self.v = i.fov()
                first = False
            else:
                if self.w != i.width() or self.h != i.height(
                ) or self.v != i.fov():
                    print(i.text)
                    print(('Old width %d, height %d, view %d' %
                          (self.w, self.h, self.v)))
                    print(('Image width %d, height %d, view %d' %
                          (i.width(), i.height(), i.fov())))
                    raise Exception('Image does not match')

    def run(self, anchor_cr=None, check_poor_opt=True):
        bench = Benchmark()

        # The following will assume all of the images have the same size
        self.verify_images()

        fns = []
        # Copy project so we can trash it
        project = self.project.copy()
        for il in project.get_image_lines():
            fns.append(il.get_name())
        self.icm = ImageCoordinateMap.from_tagged_file_names(fns)

        print(('Verbose: %d' % self.debug))
        print(('working direclty on %s' % self.project.get_a_file_name()))
        xy_opt(self.project,
               self.icm,
               verbose=self.debug,
               stdev=self.stdev,
               anchor_cr=anchor_cr,
               should_check_poor_opt=check_poor_opt)

        bench.stop()
        print(('Optimized project in %s' % bench))

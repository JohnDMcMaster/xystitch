'''
xystitch
Copyright 2011 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''

from xystitch.image_coordinate_map import ImageCoordinateMap
from xystitch.optimizer import get_rms
try:
    import scipy
    from scipy import polyfit
except ImportError:
    scipy = None
import numpy as np


def remove_outliers(floats, stdevs=2):
    # https://stackoverflow.com/questions/11686720/is-there-a-numpy-builtin-to-reject-outliers-from-a-list
    data = np.array(floats)
    return [
        float(x)
        for x in data[abs(data - np.mean(data)) < stdevs * np.std(data)]
    ]


def outlier_average(floats, stdevs=2):
    """
    Return an outlier of given values, removing outlier values
    """
    floats = remove_outliers(floats, stdevs=stdevs)
    return sum(floats) / len(floats)


def regress_row(icm, pto, rows, selector, allow_missing=False):
    # Discard the constants, we will pick a reference point later
    slopes = []
    for row in rows:
        '''
		For each column find a y position error
		y = col * c0 + c1
		'''
        cols = []
        deps = []
        for col in range(icm.width()):
            fn = icm.get_image(col, row)
            if fn is None:
                if allow_missing:
                    continue
                raise Exception('c%d r%d not in map' % (col, row))
            il = pto.get_image_by_fn(fn)
            if il is None:
                raise Exception('Could not find %s in map' % fn)
            cols.append(col)
            selected = selector(il)
            if selected is None:
                raise Exception(
                    'Reference image line is missing x/y position: %s' % il)
            deps.append(selected)
        if len(cols) == 0:
            if not allow_missing:
                raise Exception('No matches')
            continue

        if 0:
            print('Fitting polygonomial')
            print(cols)
            print(deps)

        # Find x/y given a col
        (c0, _c1) = polyfit(cols, deps, 1)
        slopes.append(c0)
    if len(slopes) == 0:
        if not allow_missing:
            raise Exception('No matches')
        # No dependence
        return 0.0
    return outlier_average(slopes)


def regress_col(icm, pto, cols, selector, allow_missing=False):
    # Discard the constants, we will pick a reference point later
    slopes = []
    for col in cols:
        '''
		For each row find an y position
		y = row * c0 + c1
		'''
        rows = []
        deps = []
        for row in range(icm.height()):
            fn = icm.get_image(col, row)
            if fn is None:
                if allow_missing:
                    continue
                raise Exception('c%d r%d not in map' % (col, row))
            il = pto.get_image_by_fn(fn)
            if il is None:
                raise Exception('Could not find %s in map' % fn)
            rows.append(row)
            deps.append(selector(il))

        if len(rows) == 0:
            if not allow_missing:
                raise Exception('No matches')
            continue
        (c0, _c1) = polyfit(rows, deps, 1)
        slopes.append(c0)
    if len(slopes) == 0:
        if not allow_missing:
            raise Exception('No matches')
        # No dependence
        return 0.0
    return outlier_average(slopes)


def calculate_derivatives(r_orders, pto, icm, allow_missing):
    """
    Return
    """
    x_dcs = []
    x_drs = []
    y_dcs = []
    y_drs = []
    for r_order in range(r_orders):
        # Given a column find x (primary x)
        x_dcs.append(
            regress_row(icm, pto, range(r_order, icm.height(), r_orders),
                        lambda x: x.x(), allow_missing))
        x_drs.append(
            regress_col(icm, pto, range(icm.width()), lambda x: x.x(),
                        allow_missing))
        # Given a row find y (primary y)
        y_dcs.append(
            regress_row(icm, pto, range(r_order, icm.height(), r_orders),
                        lambda x: x.y(), allow_missing))
        y_drs.append(
            regress_col(icm, pto, range(icm.width()), lambda x: x.y(),
                        allow_missing))
    return x_dcs, x_drs, y_dcs, y_drs


def calc_constants(r_orders,
                   icm,
                   pto,
                   x_dcs,
                   x_drs,
                   y_dcs,
                   y_drs,
                   allow_missing=False):
    """
    Calculate constant pixel offset for given derivatives
    """
    c_orders = 1
    c_order = 0
    assert len(x_dcs) == r_orders
    assert len(x_drs) == r_orders
    assert len(y_dcs) == r_orders
    assert len(y_drs) == r_orders

    ref_fns = pto.get_file_names()

    x_cs = []
    y_cs = []
    # Only calculate relative to central area
    for r_order in range(r_orders):
        this_x_cs = []
        this_y_cs = []
        candidates = 0
        for col in range(icm.width()):
            for row in range(r_order, icm.height(), r_orders):
                candidates += 1
                fn = icm.get_image(col, row)
                if not fn in ref_fns:
                    continue
                if fn is None:
                    if not allow_missing:
                        raise Exception('Missing item')
                    continue
                il = pto.get_image_by_fn(fn)
                if il is None:
                    raise Exception('%s should have been in ref' % fn)
                try:
                    # x = c0 * c + c1 * r + c2
                    row_order = row % r_orders
                    # range() above should make this match
                    assert row_order == r_order
                    if row_order == r_order:
                        cur_x = cur_x = il.x(
                        ) - x_dcs[row_order] * col - x_drs[row_order] * row
                        this_x_cs.append(cur_x)

                    # y = c3 * c + c4 * r + c5
                    col_order = col % c_orders
                    # hard coded for now
                    assert col_order == c_order
                    if col_order == c_order:
                        cur_y = il.y(
                        ) - y_dcs[col_order] * col - y_drs[col_order] * row
                        this_y_cs.append(cur_y)

                except:
                    print()
                    print(il)
                    print(x_dcs, x_drs, y_dcs, y_drs)
                    print(col, row)
                    print()

                    raise

        this_x_cs2 = outlier_average(this_x_cs)
        this_y_cs2 = outlier_average(this_y_cs)
        # print('Order %u x solutions: %u raw => %u w/o outlier' % (r_order, len(this_x_cs), len(this_x_cs2)))
        # print('Order %u y solutions: %u raw => %u w/o outlier' % (r_order, len(this_y_cs), len(this_y_cs2)))
        x_cs.append(this_x_cs2)
        y_cs.append(this_y_cs2)
    return (x_cs, y_cs)


def rms_errorl(l):
    return (sum([(i - sum(l) / len(l))**2 for i in l]) / len(l))**0.5


def rms_error_diff(l1, l2):
    if len(l1) != len(l2):
        raise ValueError("Lists must be identical")
    return (sum([(l2[i] - l1[i])**2 for i in range(len(l1))]) / len(l1))**0.5


def detect_scan_dir(x_cs, y_cs):
    c2_rms = rms_errorl(x_cs)
    c5_rms = rms_errorl(y_cs)
    print('RMS offset error x%g y%g' % (c2_rms, c5_rms))
    if c2_rms > c5_rms:
        print('x offset varies most, expect left-right scanning')
    else:
        print('y offset varies most, expect top-bottom scanning')


def print_ref_constants(orders, x_dcs, x_drs, x_cs_ref, y_dcs, y_drs,
                        y_cs_ref):
    #x_drs = [c1 + 12 for c1 in x_drs]
    # Print the solution matrx for debugging
    for cur_order in range(orders):
        # XXX: if we really cared we could center these up
        # its easier to just run the centering algorithm after though if one cares
        print('Reference order %d solution:' % cur_order)
        print('  x = %g c + %g r + %g' %
              (x_dcs[cur_order], x_drs[cur_order], x_cs_ref[cur_order]))
        print('  y = %g c + %g r + %g' %
              (y_dcs[cur_order], y_drs[cur_order], y_cs_ref[cur_order]))


def print_constants(r_orders, x_dcs, x_drs, x_cs, y_dcs, y_drs, y_cs):
    """
    x_dc: the value of x as c changes (ie d/dx)
    x_dr: the value of x as r changes (ie d/dy)
    x_c: constant offset at c=0, r=0
    """
    # Print the solution matrx for debugging
    for r_order in range(r_orders):
        # XXX: if we really cared we could center these up
        # its easier to just run the centering algorithm after though if one cares
        print('Row oder=%u solution:' % r_order)
        print('  x = %g c + %g r + %g' %
              (x_dcs[r_order], x_drs[r_order], x_cs[r_order]))
        print('  y = %g c + %g r + %g' %
              (y_dcs[r_order], y_drs[r_order], y_cs[r_order]))


'''
def check_rms_error(r_orders, icm, pto, x_dcs, x_drs, y_dcs, y_drs, allow_missing):
    """
    Calculate and print solution RMS error
    """
    # c_orders = 1
    print('Verifying reference solution matrix....')
    # Entire reference is assumed to be good always, no border
    (x_cs_ref, y_cs_ref) = calc_constants(r_orders, icm, pto, x_dcs, x_drs, y_dcs,
                                        y_drs, allow_missing)
    print_ref_constants(r_orders, x_dcs, x_drs, x_cs_ref, y_dcs, y_drs, y_cs_ref)
    calc_ref_xs = []
    calc_ref_ys = []
    ref_xs = []
    ref_ys = []
    print('Errors:')
    for col in range(icm.width()):
        for row in range(icm.height()):
            fn = icm.get_image(col, row)
            if fn is None:
                continue
            il = pto.get_image_by_fn(fn)
            # col_eo = col % c_orders
            row_eo = row % r_orders
            x_calc = x_dcs[row_eo] * col + x_drs[row_eo] * row + x_cs_ref[row_eo]
            y_calc = y_dcs[row_eo] * col + y_drs[row_eo] * row + y_cs_ref[row_eo]
            calc_ref_xs.append(x_calc)
            calc_ref_ys.append(y_calc)
            x_orig = il.x()
            y_orig = il.y()
            ref_xs.append(x_orig)
            ref_ys.append(y_orig)
            print('  c%d r%d: x%g y%g (x%g, y%g)' %
                  (col, row, x_calc - x_orig, y_calc - y_orig, x_orig, y_orig))
            if col > 0:
                fn_old = icm.get_image(col - 1, row)
                if fn_old:
                    il_old = pto.get_image_by_fn(fn_old)
                    print('    dx: %g' % (il.x() - il_old.x()))
                    if col > 1:
                        """
                        x1' = x1 - x0
                        x2' = x2 - x1
                        x2'' = x2' - x1' = (x2 - x1) - (x1 - x0) = x2 - 2 x1 + x0
                        """
                        fn_old2 = icm.get_image(col - 2, row)
                        if fn_old2:
                            il_old2 = pto.get_image_by_fn(fn_old2)
                            print('    dx2: %g' %
                                  (il.x() - 2 * il_old.x() + il_old2.x()))
            if row > 0:
                fn_old = icm.get_image(col, row - 1)
                if fn_old:
                    il_old = pto.get_image_by_fn(fn_old)
                    print('    dy: %g' % (il.y() - il_old.y()))
                    if row > 1:
                        fn_old2 = icm.get_image(col, row - 2)
                        if fn_old2:
                            il_old2 = pto.get_image_by_fn(fn_old2)
                            print('    dy2: %g' %
                                  (il.y() - 2 * il_old.y() + il_old2.y()))
    x_ref_rms_error = rms_error_diff(calc_ref_xs, ref_xs)
    y_ref_rms_error = rms_error_diff(calc_ref_ys, ref_ys)
    print('Reference RMS error x%g y%g' % (x_ref_rms_error, y_ref_rms_error))
'''


def place_images(pto, icm_real, r_orders, allow_missing, x_dcs, x_drs, x_cs,
                 y_dcs, y_drs, y_cs):
    '''
    We have the solution matrix now so lets roll
    '''
    for col in range(0, icm_real.width()):
        for row in range(0, icm_real.height()):
            fn = icm_real.get_image(col, row)
            il = pto.get_image_by_fn(fn)

            if fn is None:
                if not allow_missing:
                    raise Exception('Missing item')
                continue

            # col_eo = col % orders
            row_eo = row % r_orders

            # FIRE!
            # take the dot product
            x = x_dcs[row_eo] * col + x_drs[row_eo] * row + x_cs[row_eo]
            y = y_dcs[row_eo] * col + y_drs[row_eo] * row + y_cs[row_eo]
            # And push it out
            #print '%s: c%d r%d => x%g y%d' % (fn, col, row, x, y)
            il.set_x(x)
            il.set_y(y)


def linear_reoptimize(pto, allow_missing=False, r_orders=2):
    '''
    Change XY positions to match the trend in a linear XY positioned project (ex from XY stage).
    pto must have all images in pto_

    r_orders: how many rows to break groups into
    intended to compensate for some stitches using serpentine
    left vs right is different solution

    Ultimately trying to form this equation
    x = x_dc * c + x_dr * r + x_c
    y = y_dc * c + y_dr * r + y_c
    where these are actually arrays due to orders 

    Our model should be like this:
    -Each axis will have some degree of backlash.  This backlash will create a difference between adjacent rows / cols
    -Axes may not be perfectly adjacent
        The naive approach would give:
            x = c * dx + xc
            y = r * dy + yc
        But really we need this:
            x = c * dx + r * dx/dy + xc
            y = c * dy/dx + r * dy + yc
        Each equation can be solved separately
        Need 3 points to solve each and should be in the expected direction of that line
        
        
    Perform a linear regression on each row/col?
    Might lead to very large y = mx + b equations for the column math
    '''

    if scipy is None:
        raise Exception('Re-optimizing requires scipi')

    if r_orders == 0:
        raise Exception('Can not have order 0')
    # this is probably fine, just not tested for a long time
    # assert r_orders == 2, "fixme"
    '''
	Phase 1: calculate linear system
	'''
    # Start by building an image coordinate map so we know what x and y are
    pto.parse()
    icm = ImageCoordinateMap.from_tagged_file_names(pto.get_file_names())
    x_dcs, x_drs, y_dcs, y_drs = calculate_derivatives(r_orders, pto, icm,
                                                       allow_missing)

    # is this print actually useful?
    '''
    if 0:
        print()
        # Calculate RMS error of proposed solution
        check_rms_error(r_orders, icm, pto, x_dcs, x_drs, y_dcs, y_drs, allow_missing)
    '''
    '''
	The reference project might not start at 0,0
	Therefore scan through to find some good starting positions so that we can calc each point
	in the final project
	'''
    print()
    print('Anchoring solution...')
    (x_cs, y_cs) = calc_constants(r_orders, icm, pto, x_dcs, x_drs, y_dcs,
                                  y_drs, allow_missing)
    print_constants(r_orders, x_dcs, x_drs, x_cs, y_dcs, y_drs, y_cs)

    # detect_scan_dir(x_cs, y_cs)
    place_images(pto, icm, r_orders, allow_missing, x_dcs, x_drs, x_cs, y_dcs,
                 y_drs, y_cs)

    rms_this = get_rms(pto)
    print(('iopt: final RMS error: %f' % rms_this))

    return x_dcs, x_drs, x_cs, y_dcs, y_drs, y_cs

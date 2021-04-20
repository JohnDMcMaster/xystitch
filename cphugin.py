#!/usr/bin/env python3
'''
pr0nhugin: allows editing a reduced project to speed up hugin editing
Copyright 2012 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''

import argparse
from xystitch.pto.project import PTOProject
from xystitch.image_coordinate_map import ImageCoordinateMap, get_row_col
import subprocess
import shutil
from xystitch.optimizer import iter_rms, iter_center_cr_max
from xystitch.pto.util import center, optimize_xy_only


def worst_image(project):
    images = {}

    for _cpl, n, _imgn, N, _imgN, rms_this in iter_rms(project):
        images[n] = images.get(n, 0.0) + rms_this
        images[N] = images.get(N, 0.0) + rms_this

    worst_n = None
    worst_rms = None
    for imn, rms in list(images.items()):
        if worst_rms is None or rms > worst_rms:
            worst_n = imn
            worst_rms = rms
    return worst_n, rms


def main():
    parser = argparse.ArgumentParser(
        description='create tiles from unstitched images')
    # +/- 2 => 5 x 5 => 25 images
    # +/- 3 => 7 x 7 => 49 images
    parser.add_argument('--xydelta', default=3, type=int, help='border size')
    parser.add_argument('pto',
                        default='out.pto',
                        nargs='?',
                        help='pto project')
    args = parser.parse_args()

    pto_orig = PTOProject.from_file_name(args.pto)

    print("Finding worst image optimization")
    n, rms = worst_image(pto_orig)
    print(("got", n, rms))
    il = pto_orig.image_lines[n]
    fn = il.get_name()
    refrow, refcol = get_row_col(fn)
    print((fn, refcol, refrow))

    img_fns = []
    for il in pto_orig.get_image_lines():
        img_fns.append(il.get_name())
    icm = ImageCoordinateMap.from_tagged_file_names(img_fns)

    # Delete all ils not in our ROI
    pto_orig.build_image_fn_map()
    ils_keep = set()
    for col, row in iter_center_cr_max(icm, refcol, refrow, args.xydelta):
        im = icm.get_image(col, row)
        if im is None:
            continue
        ils_keep.add(pto_orig.img_fn2il[im])
    ils_del = set(pto_orig.image_lines) - ils_keep
    print(("%s - %s image lines, keeping %s" %
           (len(pto_orig.image_lines), len(ils_del), len(ils_keep))))

    # Reduced .pto
    pto_red = pto_orig.copy()

    print(('Deleting %d / %d images' %
           (len(ils_del), icm.width() * icm.height())))
    pto_red.del_images(ils_del)
    print((len(pto_orig.image_lines), len(pto_red.image_lines)))

    print("Centering...")
    center(pto_red)
    print("Set XY var optimization mode...")
    optimize_xy_only(pto_red)

    # p w25989 h25989 f0 v165 n"TIFF_m c:LZW" E0.0 R0 S"514,25955,8128,32815"
    pto_red.get_panorama_line().uncrop()

    print("Saving preliminary project...")
    pto_red_fn = pto_orig.file_name.replace('.pto', '_sm.pto')
    pto_red.save_as(pto_red_fn, is_new_filename=True)
    print("Fitting FOV")
    subprocess.check_call("pano_modify --fov=AUTO --canvas=AUTO -o %s %s" %
                          (pto_red_fn, pto_red_fn),
                          shell=True)

    print(('Opening temp file %s' % pto_red.file_name))
    subp = subprocess.Popen(['hugin', pto_red.file_name], shell=False)
    subp.communicate()
    print(('Hugin exited with code %d' % subp.returncode))

    red_orig_ncpls = len(pto_red.control_point_lines)
    pto_red.reopen()
    red_new_ncpls = len(pto_red.control_point_lines)

    # Filter control point lines
    # Delete all control points associated with subproject
    # Then import all new control points
    print("Deleting stale control points")

    # Convert image lines to indices
    iln_keep = set()
    orig_ncpls = len(pto_orig.control_point_lines)
    for iln, il in enumerate(pto_orig.image_lines):
        if il in ils_keep:
            iln_keep.add(iln)

    # Filter out any control point lines that were within our ROI
    cpls_new = []
    for cpl in pto_orig.control_point_lines:
        n = cpl.get_variable("n")
        N = cpl.get_variable("N")
        if not (n in iln_keep and N in iln_keep):
            cpls_new.append(cpl)
    # Shift into main object, discarding munged cpls
    print(("cpl filtering %u => %u" %
           (len(pto_orig.control_point_lines), len(cpls_new))))
    pto_orig.control_point_lines = cpls_new

    red_fn2il = pto_red.build_image_fn_map()
    red_il2fn = dict([(v, k) for k, v in list(red_fn2il.items())])
    red_il2i = pto_red.build_il2i()
    red_i2il = dict([(v, k) for k, v in list(red_il2i.items())])

    full_fn2il = pto_orig.build_image_fn_map()
    full_il2i = pto_orig.build_il2i()

    def iln_red2orig(nred):
        fn = red_il2fn[red_i2il[nred]]
        return full_il2i[full_fn2il[fn]]

    # Now add new cpls in
    # Be very careful translating image indices
    print("Adding new control points")
    for cpl in pto_red.control_point_lines:
        n = cpl.get_variable("n")
        n2 = iln_red2orig(n)
        cpl.set_variable('n', n2)
        N = cpl.get_variable("N")
        N2 = iln_red2orig(N)
        cpl.set_variable('N', N2)
        # print("cpl n=%u N=%u => n=%u N=%u" % (n, N, n2, N2))
        cpl.project = pto_orig
        pto_orig.control_point_lines.append(cpl)

    print(("image lines", len(pto_orig.image_lines), len(pto_red.image_lines)))

    print('Saving final project')
    # small backup in case something went wrong
    shutil.copy(pto_orig.file_name, 'cphugin_old.pto')
    pto_orig.save_as(pto_orig.file_name)

    new_ncpls = len(pto_orig.control_point_lines)
    print(("roi %u => %u cpls" % (red_orig_ncpls, red_new_ncpls)))
    print(("pto %u => %u cpls" % (orig_ncpls, new_ncpls)))

    print('Done!')


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from PIL import Image
from xystitch.pto.project import PTOProject
from xystitch.pto.util import iter_output_image_positions

# /usr/local/lib/python2.7/dist-packages/PIL/Image.py:2210: DecompressionBombWarning: Image size (941782785 pixels) exceeds limit of 89478485 pixels, could be decompression bomb DOS attack.
#   DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None


def run(pto_fn, fn_out):
    pto = PTOProject.from_file_name(pto_fn)

    pano_w = pto.panorama_line.width()
    pano_h = pto.panorama_line.height()
    xmin = None
    ymin = None
    mode = None
    images = 0
    for fn, x, y, r in iter_output_image_positions(pto):
        if not mode:
            with Image.open(fn) as im:
                mode = im.mode
            xmin = x
            ymin = y
        else:
            xmin = min(x, xmin)
            ymin = min(y, ymin)
        images += 1
    print("Pano size: %uw x %uh" % (pano_w, pano_h))
    print("Image mode: %s" % (mode, ))
    print("xmin: %d" % (xmin, ))
    print("ymin: %d" % (ymin, ))
    im_dst = Image.new(mode, (pano_w, pano_h))

    imi = 0
    for fn, x, y, r in reversed(sorted(iter_output_image_positions(pto))):
        imi += 1
        dstx = x - xmin
        dsty = y - ymin
        print("Image %u / %u %s: x=%u, y=%u, r=%0.1f" %
              (imi, images, fn, dstx, dsty, r))
        with Image.open(fn) as im:
            imr = im.rotate(r)
            im_dst.paste(imr, (int(dstx), int(dsty)))

    im_dst.save(fn_out, quality=95)
    print('Done!')


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Quick merge assuming simple rectilinear projection")
    parser.add_argument('--pto-in',
                        default="out.pto",
                        help='input .pto file name (default: out.pto)')
    parser.add_argument('image_out', help='output image file name')
    args = parser.parse_args()
    run(args.pto_in, args.image_out)


if __name__ == "__main__":
    main()

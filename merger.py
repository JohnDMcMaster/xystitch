#!/usr/bin/env python3
from PIL import Image
from xystitch.pto.project import PTOProject
from xystitch.pto.util import iter_output_image_positions
from PIL import ImageFont, ImageDraw 
import os
from xystitch.image_coordinate_map import get_row_col
from xystitch.util import add_bool_arg


# /usr/local/lib/python2.7/dist-packages/PIL/Image.py:2210: DecompressionBombWarning: Image size (941782785 pixels) exceeds limit of 89478485 pixels, could be decompression bomb DOS attack.
#   DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None


def get_font(size):
    """
    import cv2
    font_path = os.path.join(cv2.__path__[0],'qt','fonts','DejaVuSans.ttf')
    return ImageFont.truetype(font_path, size=128)
    """
    return ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf", size, encoding="unic")

def run(pto_fn, fn_out, label=True, alpha=True):
    pto = PTOProject.from_file_name(pto_fn)

    pano_w = pto.panorama_line.width()
    pano_h = pto.panorama_line.height()
    xmin = None
    ymin = None
    src_mode = None
    images = 0
    src_wh = None
    for fn, x, y, r in iter_output_image_positions(pto):
        if not src_mode:
            with Image.open(fn) as im:
                src_mode = im.mode
                src_wh = im.size
            xmin = x
            ymin = y
        else:
            xmin = min(x, xmin)
            ymin = min(y, ymin)
        images += 1
    if alpha:
        assert src_mode == "RGB"
        dst_mode = "RGBA"
    else:
        dst_mode = src_mode
    print("Pano size: %uw x %uh" % (pano_w, pano_h))
    print("Image mode: %s => %s" % (src_mode, dst_mode))
    print("xmin: %d" % (xmin, ))
    print("ymin: %d" % (ymin, ))
    im_dst = Image.new(dst_mode, (pano_w, pano_h))

    imi = 0
    for fn, x, y, r in reversed(sorted(iter_output_image_positions(pto))):
        imi += 1
        dstx = x - xmin
        dsty = y - ymin
        print("Image %u / %u %s: x=%u, y=%u, r=%0.1f" %
              (imi, images, fn, dstx, dsty, r))
        draw = None
        if label:
            draw = ImageDraw.Draw(im_dst)
            font = get_font(int(im.size[0] * 0.05))
            font_fill = (255, 0, 0)
        with Image.open(fn) as im:
            imr = im.rotate(r)
            if alpha:
                # Red alternates left/right
                # Green alternates up/down
                row, col = get_row_col(fn)
                if row % 2 == 0:
                    tint = (255 * ((col + 0) % 2), 255 * ((col + 1) % 2), 255, 32)
                else:
                    tint = (255 * ((col + 1) % 2), 255 * ((col + 0) % 2), 255, 32)
                im_mask = Image.new("RGBA", src_wh, tint)
                imr.paste(im_mask, (0, 0), im_mask)
                imr.putalpha(127)
                im_dst.paste(imr, (int(dstx), int(dsty)), imr)
            else:
                im_dst.paste(imr, (int(dstx), int(dsty)))
            if label:
                desc = fn.replace(".jpg", "")
                # font = ImageFont.load_default()
                # quick scale to something that "looked about right"
                draw.text((dstx + imr.size[0] * 0.4, dsty + imr.size[1] * 0.45), desc, fill=font_fill, font=font)
                # imr.save("merger/test.jpg")
                # return

    if alpha:
        im_dst = im_dst.convert("RGB")
    im_dst.save(fn_out, quality=95)
    print('Done!')


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Quick merge assuming simple rectilinear projection")
    parser.add_argument('--pto-in',
                        default="out.pto",
                        help='input .pto file name (default: out.pto)')
    add_bool_arg(parser, "--label", default=False)
    add_bool_arg(parser, "--alpha", default=False)
    parser.add_argument('image_out', help='output image file name')
    args = parser.parse_args()
    run(args.pto_in, args.image_out, label=args.label, alpha=args.alpha)


if __name__ == "__main__":
    main()

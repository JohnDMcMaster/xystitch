import json
import os
import multiprocessing
from psutil import virtual_memory
from .util import mksize

class Config:
    def __init__(self, fn=None):
        if fn is None:
            fn = Config.get_default_fn()
        if os.path.exists(fn):
            js = open(fn).read()
        else:
            js = "{}"
        self.json = json.loads(js)

        self.imgw = None
        self.imgh = None
        # Defaults if nothing is specified
        self.step_frac_x = 0.7
        self.step_frac_y = 0.7

    @staticmethod
    def get_default_fn():
        return os.getenv('HOME') + '/' + '.xyrc'

    def getx(self, ks, default=None):
        root = self.json
        for k in ks.split('.'):
            if k in root:
                root = root[k]
            else:
                return default
        return root

    def get(self, k, default=None):
        if k in self.json:
            return self.json[k]
        else:
            return default

    def keep_temp_files(self):
        return self.get('keep_temp', 0)

    def overlap_threshold(self):
        """
        Minimum overlap in a ST an image needs to be to be kept

        Works around enblend issue where it fails hard if it can't use an image
        Threshold was set to 0.25 for a long time given target overlap was 0.30
        Maybe this is no longer required?
        """
        return float(self.get('overlap_threshold', 0.00))

    def temp_base(self):
        return self.get('temp_base', "/tmp/ts_")

    def enblend_opts(self):
        return self.getx('enblend.opts', "")

    def max_mem(self):
        ret = self.get('mem', None)
        if ret is None:
            # Evidently this is physical memory
            ret =int(virtual_memory().total * 0.75)
        return ret

    def st_max_pix(self):
        """
        Supertiles are slower as they get larger
        Set this to as large of a value you can tolerate to get the best possible quality
        600MP seems to be a good compromise on my images at least
        But set to something high by default
        """
        return mksize(self.getx('ts.st_max_pix', "1g"))

    def poor_opt_thresh(self):
        # FIXME:
        # 1) should be derived from image size
        # 2) should be configurable
        return int(os.getenv('XY_OPT_THRESH', "175"))

    def set_step_frac(self, x, y):
        self.step_frac_x = x
        self.step_frac_y = y

    def default_step_frac_x(self):
        """
        Fraction of image not overlapping ("overlap inverse")
        """
        env = os.getenv('XY_STEP_FRAC_X', None)
        if env is None:
            env = os.getenv('XY_STEP_FRAC', None)
        if env is not None:
            return float(env)
        return self.step_frac_x

    def default_step_frac_y(self):
        """
        Fraction of image not overlapping ("overlap inverse")
        """
        env = os.getenv('XY_STEP_FRAC_Y', None)
        if env is None:
            env = os.getenv('XY_STEP_FRAC', None)
        if env is not None:
            return float(env)
        return self.step_frac_y

    def overlap_outlier_thresh(self):
        """
        Throw out images that differ by more than given fraction vs expected overlap
        """
        return float(os.getenv('XY_OVERLAP_OUTLIER_THRESH', "0.10"))

    def ts_threads(self):
        """tile stitcher threads"""
        ret = self.getx('ts.threads', 0)
        if ret:
            return ret
        else:
            # Assume hyperthreading?
            return multiprocessing.cpu_count()


config = Config()


def config_pto_defaults(pto):
    imw = None
    imh = None
    for il in pto.get_image_lines():
        if imw is None:
            imw = il.width()
        else:
            assert imw == il.width()
        if imh is None:
            imh = il.width()
        else:
            assert imh == il.width()
    config.imgw = imw
    config.imgh = imh

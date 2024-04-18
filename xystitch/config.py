import json
import os
import multiprocessing
from psutil import virtual_memory
from .util import mksize

import shutil
import subprocess


def find_panotools_exe(config, configk, exe_name, flatpak_name):
    exe = config.get(configk)
    if exe is not None:
        return tuple(exe)

    if 1:
        exe = shutil.which(exe_name)
        if exe is not None:
            return (exe, )

    # flatpak run --command=enfuse net.sourceforge.Hugin --help
    # bwrap: execvp align_image_stackD: No such file or directory
    # bad command => returns 1
    # good command => returns 0
    command = [
        "flatpak", "run", f"--command={flatpak_name}", "net.sourceforge.Hugin",
        "--help"
    ]
    try:
        process = subprocess.Popen(command,
                                   stderr=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        _stdout, _stderr = process.communicate()
        exit_code = process.wait()
        if exit_code == 0:
            return ("flatpak", "run", "--filesystem=host",
                    f"--command={flatpak_name}", "net.sourceforge.Hugin")
    # FIME: catch the specific exception for command not found
    except:
        pass
    return None


class PanotoolsConfig:
    def __init__(self, j=None):
        self.j = j

        self._hugin_cli = None
        self._enblend_cli = None
        self._enfuse_cli = None
        self._align_image_stack_cli = None
        self._pano_modify_cli = None

    def hugin_cli(self):
        if self._hugin_cli:
            return self._hugin_cli
        self._hugin_cli = find_panotools_exe(self.j, "hugin_cli", "hugin",
                                             "hugin")
        return self._hugin_cli

    def enblend_cli(self):
        if self._enblend_cli:
            return self._enblend_cli
        self._enblend_cli = find_panotools_exe(self.j, "enblend_cli",
                                               "enblend", "enblend")
        return self._enblend_cli

    def enfuse_cli(self):
        """
        flatpak run --command=enfuse net.sourceforge.Hugin --help
        """
        if self._enfuse_cli:
            return self._enfuse_cli
        self._enfuse_cli = find_panotools_exe(self.j, "enfuse_cli", "enfuse",
                                              "enfuse")
        return self._enfuse_cli

    def align_image_stack_cli(self):
        if self._align_image_stack_cli:
            return self._align_image_stack_cli
        self._align_image_stack_cli = find_panotools_exe(
            self.j, "align_image_stack_cli", "align_image_stack",
            "align_image_stack")
        return self._align_image_stack_cli

    def pano_modify_cli(self):
        if self._pano_modify_cli:
            return self._pano_modify_cli
        self._pano_modify_cli = find_panotools_exe(self.j, "pano_modify_cli",
                                                   "pano_modify",
                                                   "pano_modify")
        return self._pano_modify_cli


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

        # Use options that are slow but will generate a stitch
        self.enblend_safer_mode = False
        self.enblend_safest_mode = False

        self.panotools = PanotoolsConfig(self.json.get("panotools", {}))

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
            ret = int(virtual_memory().total * 0.75)
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

    def set_enblend_safer_mode(self, enblend_safer_mode):
        self.enblend_safer_mode = enblend_safer_mode

    def set_enblend_safest_mode(self, enblend_safest_mode):
        self.enblend_safest_mode = enblend_safest_mode


"""
{
    "optics": {
        "rotation_cw": 0.0,
        "um_per_pixel": 0.9356893588659003
    },
    "motion": {
        "backlash": 0.05,
        "repeatability_u": 2.0,
        "repeatability_std": 1.5
    }
}

FIXME: deal with per axis config a bit better
For now assume all axes are the same but keep the interface per axis
"""


class UscopeCalibration:
    def __init__(self, j=None, axes=set("xyz")):
        self.j = j
        self.axes = axes

    def get_optics_rotation_ccw(self):
        """
        Get the amount the image needs to be rotated CCW in order to give a square image

        Example
        If the camera is rotated -3 degrees CCW (3 degrees CW), a +3 degree correction CCW is needed
        This value will be +3 degrees
        See Image.rotate()
        """
        ret = self.j.get("optics", {}).get("rotation_ccw")
        if not ret:
            return None
        else:
            return float(ret)

    def get_optics_um_per_pixel(self):
        ret = self.j.get("optics", {}).get("um_per_pixel")
        if ret is None:
            return None
        else:
            return float(ret)

    '''
    not currently used here
    def get_motion_backlash(self, axes=None):
        """
        Return a dict with value for each axis
        """
        ret = self.j.get("motion", {}).get("backlash")
        if not ret:
            return None
        else:
            return float(ret)
    '''

    def get_motion_repeatability_u(self):
        """
        Return a dict with value for each axis
        """
        ret = self.j.get("motion", {}).get("repeatability_u")
        if not ret:
            return None
        else:
            val = float(ret)
            return dict([(axis, val) for axis in self.axes])

    def get_motion_repeatability_std(self):
        """
        Return a dict with value for each axis
        """
        ret = self.j.get("motion", {}).get("repeatability_std")
        if not ret:
            return None
        else:
            val = float(ret)
            return dict([(axis, val) for axis in self.axes])

    def get_motion_repeatibility_u_std(self):
        """
        return like
        {
            "x": {"u": 2.0, "std": 1.0},
            "y": {"u": 2.5, "std": 1.5},
        }
        Or None if insufficient info

        Intended use is to reject points likely not within expected distribution
        """
        us = self.get_motion_repeatability_u()
        stds = self.get_motion_repeatability_std()
        if us is None and stds is None:
            return None
        elif us is None or stds is None:
            raise ValueError("Inconsistent distribution. Require u + std")
        ret = {}
        for axis in self.axes():
            ret[axis] = {"u": us[axis], "std": stds[axis]}
        return ret


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

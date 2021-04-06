import os
import json
from xystitch.config import config


def load_scanj_v1(j):
    x_overlap = j['overlap']
    y_overlap = j['overlap']
    return x_overlap, y_overlap


def load_scanj_v2(j):
    x_overlap = j['computed']['x']['overlap']
    y_overlap = j['computed']['y']['overlap']
    return x_overlap, y_overlap


def load_outj_v1(j):
    x_overlap = j['x']['overlap']
    y_overlap = j['y']['overlap']
    return x_overlap, y_overlap


def load_outj_v2(j):
    """
    This is the first format that was thought out in any meaningful way
    """
    x_overlap = j['planner']['x']['overlap']
    y_overlap = j['planner']['y']['overlap']
    return x_overlap, y_overlap


def load_parameters():
    # Fraction *not* shared between images
    x_overlap = config.default_step_frac_x()
    y_overlap = config.default_step_frac_y()
    if os.path.exists('scan.json'):
        j = json.load(open('scan.json'))
        if 'p' in j:
            x_overlap, y_overlap = load_scanj_v2(j)
        elif 'overlap' in j:
            x_overlap, y_overlap = load_scanj_v1(j)
        else:
            raise Exception("Unknown scan.json format")
    # Newer file
    # Decided want to keep scan.json verbatim
    if os.path.exists('out.json'):
        j = json.load(open('out.json', 'r'))
        if 'x' in j and 'overlap' in j['x']:
            x_overlap, y_overlap = load_outj_v1(j)
        elif 'planner' in j:
            x_overlap, y_overlap = load_outj_v2(j)
        else:
            raise Exception("Unknown out.json format")
    print("Image step fraction:'")
    print(('  X: %g' % (x_overlap, )))
    print(('  Y: %g' % (y_overlap, )))
    return x_overlap, y_overlap

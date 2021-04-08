'''
This file is part of pr0ntools
Misc utilities
Copyright 2010 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''
import datetime
import math
import os
import shutil
import sys
import re

# In Python2 bytes_data is a string, in Python3 it's bytes.
# The element type is different (string vs int) and we have to deal
# with that when printing this number as hex.
if sys.version_info[0] == 2:
    myord = ord
else:
    myord = lambda x: x

def tobytes(buff):
    if type(buff) is str:
        #return bytearray(buff, 'ascii')
        return bytearray([myord(c) for c in buff])
    elif type(buff) is bytearray or type(buff) is bytes:
        return buff
    else:
        assert 0, type(buff)


def tostr(buff):
    if type(buff) is str:
        return buff
    elif type(buff) is bytearray or type(buff) is bytes:
        return ''.join([chr(b) for b in buff])
    else:
        assert 0, type(buff)

def rjust_str(s, nchars):
    '''right justify string, space padded to nchars spaces'''
    return ('%% %ds' % nchars) % s


def mean_stddev(data):
    '''mean and standard deviation'''
    mean = sum(data) / float(len(data))
    varience = sum([(x - mean)**2 for x in data])
    stddev = math.sqrt(varience / float(len(data) - 1))
    return (mean, stddev)


def now():
    return datetime.datetime.utcnow().isoformat()


def msg(s=''):
    print(('%s: %s' % (now(), s)))


def logwt(d, fn, shift_d=True, shift_f=False, stampout=True):
    '''Log with timestamping'''

    if shift_d:
        try_shift_dir(d)
        print("mkdir", d)
        os.mkdir(d)


    fn_can = os.path.join(d, fn)
    outlog = IOLog(obj=sys, name='stdout', out_fn=fn_can, shift=shift_f)
    errlog = IOLog(obj=sys, name='stderr', out_fd=outlog.out_fd)

    # Add stamps after so that they appear in output logs
    outdate = None
    errdate = None
    if stampout:
        outdate = IOTimestamp(sys, 'stdout')
        errdate = IOTimestamp(sys, 'stderr')

    return (outlog, errlog, outdate, errdate)


def try_shift_dir(d):
    if not os.path.exists(d):
        return
    i = 0
    while True:
        dst = d + '.' + str(i)
        if os.path.exists(dst):
            i += 1
            continue
        shutil.move(d, dst)
        break


# Print timestamps in front of all output messages
class IOTimestamp(object):
    def __init__(self, obj=sys, name='stdout'):
        self.obj = obj
        self.name = name

        self.fd = obj.__dict__[name]
        obj.__dict__[name] = self
        self.nl = True

    def __del__(self):
        if self.obj:
            self.obj.__dict__[self.name] = self.fd

    def flush(self):
        self.fd.flush()

    def write(self, data):
        parts = data.split('\n')
        for i, part in enumerate(parts):
            if i != 0:
                self.fd.write('\n')
            # If last bit of text is just an empty line don't append date until text is actually written
            if i == len(parts) - 1 and len(part) == 0:
                break
            if self.nl:
                self.fd.write('%s: ' % datetime.datetime.utcnow().isoformat())
            self.fd.write(part)
            # Newline results in n + 1 list elements
            # The last element has no newline
            self.nl = i != (len(parts) - 1)


# Log file descriptor to file
class IOLog(object):
    def __init__(self,
                 obj=sys,
                 name='stdout',
                 out_fn=None,
                 out_fd=None,
                 mode='a',
                 shift=False):
        if out_fd:
            self.out_fd = out_fd
        else:
            # instead of jamming logs together, shift last to log.txt.1, etc
            if shift and os.path.exists(out_fn):
                i = 0
                while True:
                    dst = out_fn + '.' + str(i)
                    if os.path.exists(dst):
                        i += 1
                        continue
                    shutil.move(out_fn, dst)
                    break

            hdr = mode == 'a' and os.path.exists(out_fn)
            self.out_fd = open(out_fn, mode)
            if hdr:
                self.out_fd.write('*' * 80 + '\n')
                self.out_fd.write('*' * 80 + '\n')
                self.out_fd.write('*' * 80 + '\n')
                self.out_fd.write('Log rolled over\n')

        self.obj = obj
        self.name = name

        self.fd = obj.__dict__[name]
        obj.__dict__[name] = self
        self.nl = True

    def __del__(self):
        if self.obj:
            self.obj.__dict__[self.name] = self.fd

    def flush(self):
        self.fd.flush()

    def write(self, data):
        self.fd.write(data)
        self.out_fd.write(data)


def add_bool_arg(parser, yes_arg, default=False, **kwargs):
    dashed = yes_arg.replace('--', '')
    dest = dashed.replace('-', '_')
    parser.add_argument(yes_arg,
                        dest=dest,
                        action='store_true',
                        default=default,
                        **kwargs)
    parser.add_argument('--no-' + dashed,
                        dest=dest,
                        action='store_false',
                        **kwargs)


def size2str(d):
    if d < 1000:
        return '%g' % d
    if d < 1000**2:
        return '%gk' % (d / 1000.0)
    if d < 1000**3:
        return '%gm' % (d / 1000.0**2)
    return '%gg' % (d / 1000.0**3)


def mksize(s):
    # To make feeding args easier
    if s is None:
        return None

    m = re.match(r"(\d*)([A-Za-z]*)", s)
    if not m:
        raise ValueError("Bad size string %s" % s)
    num = int(m.group(1))
    modifier = m.group(2)
    '''
    s: square
    k: 1000
    K: 1024
    m: 1000 * 1000
    M: 1024 * 1024
    ...
    '''
    for mod in modifier:
        if mod == 'k':
            num *= 1000
        elif mod == 'K':
            num *= 1024
        elif mod == 'm':
            num *= 1000 * 1000
        elif mod == 'M':
            num *= 1024 * 1024
        elif mod == 'g':
            num *= 1000 * 1000 * 1000
        elif mod == 'G':
            num *= 1024 * 1024 * 1024
        elif mod == 's':
            num *= num
        else:
            raise ValueError('Bad modifier %s on number string %s', mod, s)
    return num


def mem2pix(mem):
    # Rough heuristic from some of my trials (1 GB => 51 MP)
    return mem * 51 / 1000
    # Maybe too aggressive, think ran out at 678 MP / 18240 MB => 37 MP?
    # Maybe its a different error
    # ahah: I think it was disk space and I had misinterpreted it as memory
    # since the files got deleted after the run it wasn't obvious
    #return mem * 35 / 1000

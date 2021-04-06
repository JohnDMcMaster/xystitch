'''
xystitch
Copyright 2011 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''

import os
import shutil
from xystitch.temp_file import ManagedTempFile
from xystitch.execute import Execute
from . import line


class CommentLine(line.Line):
    def __init__(self, text, project):
        line.Line.__init__(self, text, project)

    def prefix(self):
        return '#'

    @staticmethod
    def from_line(line, pto_project):
        ret = CommentLine()
        ret.text = line
        return ret

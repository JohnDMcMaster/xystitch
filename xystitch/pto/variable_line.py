'''
xystitch
Copyright 2011 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''

import os
import shutil
from xystitch.temp_file import ManagedTempFile
from xystitch.execute import Execute
from xystitch.pto.line import Line


class VariableLine(Line):
    def __init__(self, text, project):
        self.image = None
        Line.__init__(self, text, project)

    def prefix(self):
        return 'v'

    def variable_print_order(self):
        return list(['d', 'e', 'p', 'r', 'x', 'y', 'v', 'Ra', 'Rb'])

    def key_variables(self):
        return set()

    def int_variables(self):
        ret = set('deprxyv')
        ret.add('Ra')
        ret.add('Rb')
        ret.add('Rc')
        ret.add('Rd')
        ret.add('Re')
        ret.add('Vb')
        ret.add('Vc')
        ret.add('Vd')
        ret.add('Eev')
        ret.add('TrX')
        ret.add('TrY')
        return ret

    def float_variables(self):
        return set()

    def string_variables(self):
        return set()

    def x(self):
        '''Get image index corresponding to x optimization'''
        return self.get_variable('d')

    def y(self):
        '''Get image index corresponding to y optimization'''
        return self.get_variable('e')

    def index(self):
        '''Check optimization variables for consistency and return the image index'''
        # Note that these can both be None
        x = self.x()
        y = self.y()
        if x is None:
            return y
        if y is None:
            return x
        if x != y:
            raise Exception("Variables don't match")
        return x

    @staticmethod
    def from_line(line, project):
        return VariableLine(line, project)

    def update(self):
        # Update to the correct indices
        if not self.image:
            # See if we can parse it then
            image_index = None
            # All index should be consistent
            for k, v in self.variables.items():
                if image_index is None:
                    image_index = v
                else:
                    if not image_index == v:
                        raise Exception("index mismatch")
            # Maybe one of those dumb (useless I think) empty v lines Hugin puts out
            if image_index is None:
                # In this case, there is nothing to update
                return None
            self.image = self.project.i2img(image_index)

            # Since we just parsed, we should already be in sync
            return

        for k in self.variables:
            self.set_variable(k, self.image.get_index())

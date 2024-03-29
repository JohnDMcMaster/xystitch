'''
xystitch
Copyright 2011 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''

from xystitch.temp_file import ManagedTempFile
import os.path
import subprocess


class Merger:
    def __init__(self, ptos):
        self.ptos = ptos

    def run(self):
        from xystitch.pto.project import PTOProject
        '''Take in a list of pto files and merge them into pto'''
        pto_temp_file = ManagedTempFile.get(None, ".pto")

        args = ["pto_merge"]
        args.append("--output=%s" % pto_temp_file)

        for pto in self.ptos:
            args.append(pto.get_a_file_name())

        # print('MERGING: %s' % (args, ))

        rc = subprocess.run(args,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            shell=False,
                            encoding="ascii").returncode

        # go go go
        if not rc == 0:
            print()
            print()
            print()
            #print 'Output:'
            #print output
            print('rc: %d' % rc)
            if rc == 35072:
                # ex: empty projects seem to cause this
                print('Out of memory, expect malformed project file')
            raise Exception('failed pto_merge')

        if not os.path.exists(str(pto_temp_file)):
            raise Exception('Output file missing: %s' % (pto_temp_file, ))

        return PTOProject.from_temp_file(pto_temp_file)

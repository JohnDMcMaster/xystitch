# xystitch

This code is useful, but old and crusty. Don't look under the hood :)

Core utilities in typical usage order:
* xy-stitch: high level .pto creation workflow (xy-feature + xy-pto)
  * xy-feature: create features
  * xy-pto: tweak pto and optimize it
* xy-hugin: work on a reduced .pto for faster cropping and rotation
  * Or just use hugin if your project is small enough
* xy-ts: stitch image into output .jpgs such as tiles and/or one large .jpg

Misc utilities:
* xy-outlier: print and remove control point outliers
* xy-cp: similar to outlier, but operates on image RMS
* xy-stack: stack image sets using Zerene Stacker. Used for distorted chips
* xy-stitch-aj uses older algorithm that gave early good results


# Quick start

Tested on:
  * Ubuntu 20.04
  * python 2.7.18


    cd ~
    git clone https://github.com/JohnDMcMaster/xystitch.git
    cd xystitch
    sudo python setup.py develop
    cd test/simple
    XY_OVERLAP_OUTLIER_THRESH=0.3 xy-stitch

Now open in Hugin:

    xy-hugin out.pto
 
Now:
1. Click on "preview panorama"
1. Go to crop tab and set crop
1. Save project (ctrl-S or file => save)
1. Close both windows


    xy-ts

If you'd like to see stitch progress, in a new window do "tail -f pr0nts/w00.log"

Output files:
  * single/: final .jpg, if its possible to make
  * st/: "supertiles,", the intermediate partial stitches
  * out/: tiles. Can be fed into pr0nmap utility
  * pr0nstitch/: log files


# Config

Used for advanced operations like setting enblend max memory. Sample config file:
```
$ cat ~/.pr0nrc
{
	"keep_temp":1,
	"pr0nts": {
		"mem":"6144m"
	},
	"enblend": {
		"opts":"-m 6144"
	},
	"temp_base": "/tmp"
}
```


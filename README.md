# xystitch

This code is useful, but old and crusty. Don't look under the hood :)

Core utilities in typical usage order:
* xy-stitch: high level .pto creation workflow (xy-feature + xy-pto)
  * xy-feature: create features
  * xy-pto: tweak pto and optimize it
* xy-hugin: open reduced .pto for faster cropping and rotation
  * Or just use hugin if your project is small enough
* xy-ts: stitch image into output .jpgs such as tiles and/or one large .jpg

Misc utilities:
* xy-cphugin: open reduced .pto to tweak control points around poorly optimized areas
* xy-outlier: print and remove control point outliers
* xy-cp: similar to outlier, but operates on image RMS
* xy-stack: stack image sets using Zerene Stacker. Used for distorted chips
* xy-stitch-aj uses older algorithm that gave early good results


# Quick start

Tested on:
  * Ubuntu 20.04
  * python 3.8.5


Install:

```
# Misc requirements
sudo apt install hugin-tools enblend imagemagick

# Do one of these:
# Option 1: install from pip
sudo pip3 install xystitch
# Option 2: install from git
cd ~
git clone https://github.com/JohnDMcMaster/xystitch.git
cd xystitch
sudo python3 setup.py install
```

Now try a small stitch:

```
wget https://siliconpr0n.org/media/xystitch/2020-11-27_stitch_test.tar
tar -xf 2020-11-27_stitch_test.tar
cd 2020-11-27_stitch_test
# Perform feature recognition and place images on a global position grid
# On my carbon X1 (gen 4) this took ~10 sec
xy-stitch
```

Now open in Hugin to rotate and crop the image (optional):

```
xy-hugin out.pto
```
 
Now:
1. Click on "
view panorama"
1. Go to crop tab and set crop
1. Save project (ctrl-S or file => save)
1. Close both windows

```
# On my carbon X1 (gen 4) this took ~45 sec
xy-ts
```

If you'd like to see stitch progress, in a new window do "tail -f pr0nts/w00.log"

Output files:
  * single/: final .jpg, if its possible to make
  * st/: "supertiles,", the intermediate partial stitches
  * out/: tiles. Can be fed into pr0nmap utility
  * pr0nstitch/: log files



# User guide

WARNING: there are several hard coded values in the framework right now.
Please see "config" section to work around them until fixed.

Image file name
  * Name files like c012_r345.jpg to put an image at col=12, row=345
  * c000_r000.jpg is the first image
  * xy-feature can tolerate missing images by adding "--skip-missing"
  * There are several utlities to rename files into compliant form
    * Ex: rename_xy.py interpolates a manually taken image set with irregular columns into a grid layout

Stitch failures
  * Commands can fail if they out of memory
    * You will hopefully get a legible error message when this happens, even if nona/enblend is not by itself
    * Try reducing number of threads
    * Try reducing supertile size and/or use config file to increase their memory
    * Do you have enough disk space?
  * nona may fail if images have too much overlap and/or are cropped too close to effectively use an image
    * Consider making crop large
    * Try stitching with a different (usually larger is better) supertile size
    * xystitch tries hard to work around this but doesn't always succeed
    * I take images w/ about 30% overlap

Sample performance data: https://docs.google.com/spreadsheets/d/1zUHiHdVTUtuGzdpsjj1qhKfYHIgDBVzwJIBZmqQP_4c/edit?usp=sharing


# Main config

Environment variables (see xystitch/config.py):
  * XY_STEP_FRAC_X, XY_STEP_FRAC_Y (or XY_STEP_FRAC): fraction of image that is stepped to move to next
    * Default: 0.70, but a scan specific config file, if present, will take preference over this variable
    * Ex: default of 0.70 means 30% overlap to adjacent image
      * If there is an image on each side 40% of the image (in the center) will be unique
    * This constant name / application needs review for clarity
  * XY_OVERLAP_OUTLIER_THRESH: throw out images that differ by more than given fraction vs expected overlap
    * Default: 0.10 (ie 10%) means that with default 0.70 overlap, a step size of 60% to 80% is acceptable

Main config file used for advanced operations like setting enblend max memory. Sample config file:
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

# Importing sequentially named files

Files must be named to have upper left origin and 0 indexed rows/columns.
rename_xy.py can be used to import files named sequentially, such as a DSLR might take

Munge order:
  * Apply column markers (--cols or --endrows)
  * Remove rows/columns (--rm-even-row etc)
  * Apply layout

Supported layouts:
  * lr-ud: images start at left and go right
  * rl-ud: iamges start at right and go left
  * serp-lr-ud: images start at top, go left and go right, then right and go left. Rinse and repeat
  * serp-rl-ud: images start at top, go right and go left, then left and go right. Rinse and repeat
  * serp-lr-du: like serp-lr-ud, but start from bottom instead of top
  * serp-rl-du: like serp-rl-ud, but start from bottom instead of top


# Scan config

This file is output by pyuscope. It is used to automatically load scan parameters and shouldn't be required

TODO: add a link to config and/or describe options digested here


# Ubuntu 20.04 notes

enblend
  * Enblend no longer accepts -m. Removed from .pr0nrc

nona
  * Memory usage different vs ubuntu 16.04: memory no longer increases linearly but goes up and down
  * Slower? Or am I just doing larger images now

Had to adjust magick limits. Not carefully thought out but I'm using the values below

```
/etc/ImageMagick-6/policy.xml

<policy domain="resource" name="memory" value="16GiB"/>
<policy domain="resource" name="map" value="32GiB"/>
<policy domain="resource" name="width" value="128KP"/>
<policy domain="resource" name="height" value="128KP"/>
<!-- <policy domain="resource" name="list-length" value="128"/> -->
<policy domain="resource" name="area" value="16GB"/>
<policy domain="resource" name="disk" value="32GiB"/>
```

# Version history


v0.0.0 (2020-01-28)
  * Import old project from pr0ntools repository

v1.0.0 (2020-11-27)
  * First official release
  * Adopt xy- prefix

v1.1.0 (2021-03-06)
  * Python3
  * Fix optimizer RMS crash bug
  * Print worker status in master
  * Remove pr0ntools reference

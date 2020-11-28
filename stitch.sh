#!/bin/bash
# High level wrapper script to create base .pto from .jpgs
# Runs feature recognition and optimizes global position

time (

if [ -f out.pto ] ; then
   mv out.pto out_old.pto
fi

echo
echo
echo '**********************************'
time xy-feature out.pto $( (shopt -s nullglob; echo *.jpg *.png) ) "$@" ||exit 1

if cat stitch_failures.json |grep '"critical_images": 0'
then
    echo 'No stitch failures'
else
	echo 'WARNING: one or more images could not match features'
	# used to exit when missing images was a bigger deal
	# now that using (quick) pre-optimizer might as well
	# make a best effort
	#exit 1
fi

echo
echo
echo '**********************************'
echo 'No failures, optimizing'
time xy-pto --xy-opt out.pto

# fit to screen
time pano_modify --fov=AUTO --canvas=AUTO -o out.pto out.pto

echo
echo
# Considered adding pr0nhugin or similar here
# But doesnt fit well into my flow
echo 'Done!  Open with Hugin to adjust size and rotate'
)

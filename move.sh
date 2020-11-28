#!/usr/bin/env bash

if [ $(ls single/ |wc -l) -eq 1 ] ; then
    mkdir raw
    mv *.* raw

    if [ $(ls raw/ |wc -l) -eq 1 ] ; then
        mv raw/* single/out.jpg
    fi

    if [ $(ls single/ |wc -l) -eq 1 ] ; then
        echo "Single output image detected: renaming"
        mv single/* single/$(basename $PWD).jpg
    fi

    echo "Cleaning up files"
    mv pr0nstitch* pr0nts* raw/
    rm -rf out st
fi


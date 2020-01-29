# xystitch

This code is useful, but old and crusty. Don't look under the hood :)

Main utilities:
* pr0nauto: high level stitching workflow
* pr0nstitch: create features
* pr0npto: tweak pto and optimize it
* pr0nhugin: work on a reduced .pto for cropping, rotation
* pr0nts: stitch image into tiles for map rendering
* pr0nsingle: stitch one large single image
* outlier: print and remove control point outliers
* pr0ncp: similar to above, but operates on image RMS

Sample config file:
```
$ cat ~/.pr0nrc
{
	"keep_temp":1,
	"pr0nts": {
		"mem":"6144m"
	},
	"enblend": {
		"opts":"-m 6144"
	}
}
```


#!/usr/bin/env python3

import os
import argparse
import sys
import glob
import shutil
import subprocess
'''
zs should look something like:
#!/usr/bin/env bash
/home/mcmaster/document/software/zerene_stacker/ZereneStacker/run.sh "$@"

run.sh:
#!/bin/bash
appdir="$( cd "$( dirname "$0" )" && pwd )"
exten="$appdir"/JREextensions
chmod +x "${appdir}/jre/bin/java"
"${appdir}/jre/bin/java" -Xmx1024m -classpath "${appdir}/ZereneStacker.jar:${exten}/AppleShell.jar:${exten}/jai_codec.jar:${exten}/jai_core.jar:${exten}/jai_imageio.jar:${exten}/jdom.jar:${exten}/metadata-extractor-2.4.0-beta-1.jar" com.zerenesystems.stacker.gui.MainFrame "$@"
'''


def run(img_dir_in, fn_out):
    img_dir_in = os.path.realpath(img_dir_in)
    fn_out = os.path.realpath(fn_out)
    print("Stack in:", img_dir_in)
    print("Stack out:", fn_out)
    out_tmp_dir = '/tmp/xystitch-stack'
    print('Out temp dir: %s' % out_tmp_dir)
    # can't be in an image input dir or it will be tried to process as an image
    # in_xml_fn = os.path.join(tmp_dir, 'in.xml')
    in_xml_fn = out_tmp_dir + '_in.xml'
    print('in XML: %s' % in_xml_fn)
    """
    Application is really picky and blocks in GUI on bad input
    try to suss out common issues before launching
    """
    if not os.path.isdir(img_dir_in):
        raise ValueError("need dir in")
    if not glob.glob(img_dir_in + "/*.jpg"):
        raise ValueError("need .jpg in input dir")

    if os.path.exists(out_tmp_dir):
        shutil.rmtree(out_tmp_dir)
    os.mkdir(out_tmp_dir)
    """
    There are two ways to provide a batch script:
    
    Place the script file anywhere, and specify its location using the arguments –batchScript pathname
    Place the script file in the same folder as input images, and name it specifically “ZereneBatch.xml”.
    """

    #<OutputImagesDesignatedFolder value="%(out_dir)s" />
    # <BatchFileChooser.LastDirectory value="%(in_dir)s" />
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<ZereneStackerBatchScript>
  <WrittenBy value="Zerene Stacker 1.04 Build T2022-04-21-0715" />
  <BatchQueue>
    <Batches length="1">
      <Batch>
        <Sources length="1">
          <Source value="''' + img_dir_in + '''" />
        </Sources>
        <ProjectDispositionCode value="101" />
        <Tasks length="1">
          <Task>
            <OutputImageDispositionCode value="5" />
            <OutputImagesDesignatedFolder value="''' + out_tmp_dir + '''" />
            <Preferences>
              <AcquisitionSequencer.BacklashMillimeters value="0.22" />
              <AcquisitionSequencer.CommandLogging value="false" />
              <AcquisitionSequencer.DistancePerStepperRotation value="1.5875" />
              <AcquisitionSequencer.EndPosition value="0" />
              <AcquisitionSequencer.HighPrecisionHoldingTorque value="10" />
              <AcquisitionSequencer.LowPrecisionHoldingTorque value="0" />
              <AcquisitionSequencer.MaximumMmPerSecond value="2.0" />
              <AcquisitionSequencer.MicrostepsPerRotation value="3200" />
              <AcquisitionSequencer.MovementRampTime value="2.0" />
              <AcquisitionSequencer.NumberOfSteps value="5" />
              <AcquisitionSequencer.PrecisionThreshold value="0.05" />
              <AcquisitionSequencer.PrerunMillimeters value="0.0" />
              <AcquisitionSequencer.RPPIndicatorLeft value="-100.0" />
              <AcquisitionSequencer.RPPIndicatorRight value="+100.0" />
              <AcquisitionSequencer.SettlingTime value="3.0" />
              <AcquisitionSequencer.ShortcutParamsOnStartup value="true" />
              <AcquisitionSequencer.ShutterActivationsPerStep value="1" />
              <AcquisitionSequencer.ShutterAfterTime value="2.0" />
              <AcquisitionSequencer.ShutterBetweenTime value="1.0" />
              <AcquisitionSequencer.ShutterPulseTime value="0.3" />
              <AcquisitionSequencer.StartPosition value="0" />
              <AcquisitionSequencer.StepSize value="0.1" />
              <AcquisitionSequencer.StepSizeAdjustmentFactor value="1.0" />
              <AcquisitionSequencer.StepSizesFile value="" />
              <AcquisitionSequencer.SwapBackAndFwdButtons value="false" />
              <AlignmentControl.AddNewFilesAsAlreadyAligned value="false" />
              <AlignmentControl.AlignmentSettingsChanged value="false" />
              <AlignmentControl.AllowRotation value="true" />
              <AlignmentControl.AllowScale value="true" />
              <AlignmentControl.AllowShiftX value="true" />
              <AlignmentControl.AllowShiftY value="true" />
              <AlignmentControl.AutoTSVFile value="false" />
              <AlignmentControl.BrightnessSettingsChanged value="false" />
              <AlignmentControl.CorrectBrightness value="true" />
              <AlignmentControl.ForceAllAlignAgainstFirst value="false" />
              <AlignmentControl.MaxRelDegRotation value="20" />
              <AlignmentControl.MaxRelPctScale value="20" />
              <AlignmentControl.MaxRelPctShiftX value="20" />
              <AlignmentControl.MaxRelPctShiftY value="20" />
              <AlignmentControl.Order.Automatic value="true" />
              <AlignmentControl.Order.NarrowFirst value="true" />
              <AlignmentControl.UseMaximumPrecisionRules value="false" />
              <AllowReporting.UsageStatistics value="false" />
              <ColorManagement.CopyICCProfileExternally value="false" />
              <ColorManagement.DebugPrintProfile value="false" />
              <ColorManagement.InputOption value="Use_EXIF_and_DCF_rules" />
              <ColorManagement.InputOption.AssumedProfile value="sRGB IEC61966-2.1" />
              <ColorManagement.ManageZSDisplays value="false" />
              <ColorManagement.ManageZSDisplaysHasChanged value="false" />
              <ColorManagement.OutputOption value="CopyInput" />
              <DOFCalculator.COCWidth value="" />
              <DOFCalculator.COCWidthPixels value="" />
              <DOFCalculator.DOFClassic value="" />
              <DOFCalculator.DOFWaveOptics value="" />
              <DOFCalculator.EffectiveAperture value="" />
              <DOFCalculator.Lambda value="" />
              <DOFCalculator.LensAperture value="" />
              <DOFCalculator.LensApertureType value="" />
              <DOFCalculator.LensPupilRatio value="" />
              <DOFCalculator.LensPupilRatioDirection value="" />
              <DOFCalculator.Magnification value="" />
              <DOFCalculator.RecommendationText value="" />
              <DOFCalculator.SensorPixelWidth value="" />
              <DOFCalculator.SensorWidth value="" />
              <DOFCalculator.SensorWidthPixels value="" />
              <DOFCalculator.StepOverlapFraction value="" />
              <DOFCalculator.StepOverlapPercentage value="" />
              <DOFCalculator.StepSizeSuggested value="" />
              <DOFCalculator.SubjectWidth value="" />
              <DOFCalculator.ToleranceForOptimality value="" />
              <DefectMap.AvoidEdgeStreaks value="false" />
              <DefectMap.CurrentMapImageFilePath value="" />
              <DefectMap.InfillAllFrames value="true" />
              <DefectMap.PropagateGoodPixels value="false" />
              <DefectMap.UseDefectMask value="false" />
              <DepthMapControl.AlgorithmIdentifier value="1" />
              <DepthMapControl.CachePass1Info value="false" />
              <DepthMapControl.ContrastThresholdLevel value="8.461692E-6" />
              <DepthMapControl.ContrastThresholdPercentile value="30.0" />
              <DepthMapControl.EstimationRadius value="10" />
              <DepthMapControl.ExternalMaskColorRGBA value="80,0,0,128" />
              <DepthMapControl.ExternalMaskFile value="" />
              <DepthMapControl.SaveDepthMapImage value="false" />
              <DepthMapControl.SaveDepthMapImageDirectory value="{project}/DepthMaps" />
              <DepthMapControl.SaveUsedPixelImages value="false" />
              <DepthMapControl.SmoothingRadius value="5" />
              <DepthMapControl.ThresholdMaskColorRGBA value="0,0,0,255" />
              <DepthMapControl.UseFixedContrastThresholdLevel value="false" />
              <DepthMapControl.UseFixedContrastThresholdPercentile value="false" />
              <DepthMapControl.UsedPixelFractionThreshold value="0.5" />
              <FileIO.IgnoreEXIFOrientation value="false" />
              <FileIO.SortNewFilesInReverseOrder value="false" />
              <FileIO.UseExternalTIFFReader value="false" />
              <Interpolator.RenderingSelection value="Interpolator.Spline4x4" />
              <Interpolator.ShowAdvanced value="false" />
              <Multiprocessing.SelectedNumberOfCores value="12" />
              <Multiprocessing.UseAllCores value="true" />
              <OriginalSourceFilesFolder.Path value="" />
              <OutputImageNaming.Template value="{datetime:YYYY-MM-dd-hh.mm.ss} ZS {method}" />
              <Precrop.LimitsString value="" />
              <Precrop.Selected value="false" />
              <Prerotation.Degrees value="0" />
              <Prerotation.EXIFtag.ignore value="false" />
              <Prerotation.Selected value="false" />
              <Presize.UserSetting.Scale value="1.0" />
              <Presize.UserSetting.Selected value="false" />
              <Presize.Working.Scale value="1.0" />
              <PyramidControl.GritSuppressionMethod value="1" />
              <PyramidControl.RetainOnlyUDRImage value="false" />
              <PyramidControl.RetainUDRImage value="false" />
              <PyramidControl.UseAllChannels value="false" />
              <ResetSelected.InputOutput value="false" />
              <ResetSelected.Multiprocessing value="false" />
              <ResetSelected.StackShot value="false" />
              <ResetSelected.Stacking value="false" />
              <RetouchingBrush.Hardness value="0.5" />
              <RetouchingBrush.ShowBrushes value="false" />
              <RetouchingBrush.Type value="Details" />
              <RetouchingBrush.Width value="10" />
              <SaveImage.BitsPerColor value="8" />
              <SaveImage.CompressionQuality value="0.75" />
              <SaveImage.CompressionType value="none" />
              <SaveImage.DefaultFolderStrategy value="WithSource" />
              <SaveImage.FileType value="jpg" />
              <SaveImage.FolderPathLastUsed value="''' + out_tmp_dir + '''" />
              <SaveImage.PropagateEXIF value="false" />
              <SaveImage.RescaleImageToAvoidOverflow value="false" />
              <SkewSequence.NumberOfOutputImages value="3" />
              <SkewSequence.Selected value="false" />
              <SkewSequence.ShiftXPct.Limit1 value="-3.0" />
              <SkewSequence.ShiftXPct.Limit2 value="3.0" />
              <SkewSequence.ShiftYPct.Limit1 value="0.0" />
              <SkewSequence.ShiftYPct.Limit2 value="0.0" />
              <SkewSequence.UseConicalPath value="false" />
              <Slabbing.DisposalOfOutputImages value="3" />
              <Slabbing.FramesPerOverlap value="3" />
              <Slabbing.FramesPerSlab value="10" />
              <Slabbing.OutputImageNaming.Template value="Slab {outseq} {method}" />
              <Slabbing.SaveImage.BitsPerColor value="16" />
              <Slabbing.SaveImage.CompressionQuality value="9" />
              <Slabbing.SaveImage.CompressionType value="none" />
              <Slabbing.SaveImage.FileType value="tif" />
              <Slabbing.SaveImage.PropagateEXIF value="false" />
              <Slabbing.SaveImage.RescaleImageToAvoidOverflow value="false" />
              <Slabbing.StackingOperation value="PMax" />
              <StackingControl.FrameSkipFactor value="1" />
              <StackingControl.FrameSkipSelected value="false" />
              <StereoCalculator.AngleOffAxis value="" />
              <StereoCalculator.Magnification value="" />
              <StereoCalculator.NumberOfFrames value="" />
              <StereoCalculator.SensorWidth value="" />
              <StereoCalculator.ShiftPercentageInX value="" />
              <StereoCalculator.StackDepth value="" />
              <StereoCalculator.StackWidth value="" />
              <StereoCalculator.StepSize value="" />
              <StereoOrdering.LeftRightIndexSeparation value="1" />
              <WatchDirectoryOptions.AcceptViaDelay value="false" />
              <WatchDirectoryOptions.AcceptViaDelaySeconds value="2.0" />
            </Preferences>
            <TaskIndicatorCode value="1" />
          </Task>
        </Tasks>
      </Batch>
    </Batches>
  </BatchQueue>
</ZereneStackerBatchScript>'''

    open(in_xml_fn, 'w').write(xml + '\n\n')

    # Launches in the background
    # args = ['/opt/ZereneStacker/ZereneStacker']
    args = [
        "java",
        "-Xmx32086m",
        "-DjavaBits=64bitJava",
        "-Dlaunchcmddir=/home/mcmaster/.ZereneStacker",
        "-classpath",
        "/opt/ZereneStacker/ZereneStacker.jar:/opt/ZereneStacker/JREextensions/*",
        "com.zerenesystems.stacker.gui.MainFrame",
    ]
    """
    https://www.zerenesystems.com/cms/stacker/docs/batchapi
    -noSplashScreen -exitOnBatchScriptCompletion -runMinimized
    is suggested
    -runMinimized makes the program start with its user interface iconified (appearing only on the taskbar)
        which doesn't apply under linux



    Undocumented options
    -wasRestarted
    """
    args = args + [
        "-noSplashScreen",
        "-exitOnBatchScriptCompletion",
        "-runMinimized",
        "-showProgressWhenMinimized=false",
    ]

    args.append("-batchScript")
    args.append(in_xml_fn)
    print(" ".join(args))
    # return
    subprocess.check_call(args, shell=False)

    print("Finding output...")
    # '/tmp/xystitch-stack/2023-02-17-06.10.43 ZS PMax.jpg'
    outfns = glob.glob(os.path.join(out_tmp_dir, '*.jpg'))
    if len(outfns) != 1:
        print(outfns)
        raise Exception('Missing output image')
    print("mv %s => %s" % (outfns[0], fn_out))
    shutil.move(outfns[0], fn_out)
    shutil.rmtree(out_tmp_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Stack CNC output dirs into output dir')
    parser.add_argument(
        'img_dir_in',
        help='join images in input directories to form stacked output dir')
    parser.add_argument(
        'fn_out',
        nargs="?",
        help='join images in input directories to form stacked output dir')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    dir_in = args.img_dir_in
    if dir_in[-1] == "/":
        dir_in = dir_in[:-1]
    fn_out = args.fn_out
    if not fn_out:
        fn_out = dir_in + ".jpg"

    run(dir_in, fn_out)

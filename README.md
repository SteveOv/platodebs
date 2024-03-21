# platodebs 

## POC for a catalogue pipeline for PLATO dEB candidates

A simple set code for investigating the variability of detached eclipsing
binary systems (dEBs) within _TESS_ lightcurves.

## Installation

This code base was developed on Kubuntu 23.10 within the context of
an [Anaconda 3](https://www.anaconda.com/) conda environment named **platodebs**. 
This environment is configured to support _Python 3.7_, 
the [STAR SHADOW](https://github.com/LucIJspeert/star_shadow) lightcurve analysis
tool and any libraries upon which the code is dependent.

To set up the **platodebs** conda environment, having first cloned this GitHub repo, 
open a Terminal, navigate to _this_ local directory and run the following command;
```sh
$ conda env create -f environment.yaml
```
You will need to activate the **platodebs** environment whenever you wish to
run any of these modules. Use the following command;
```sh
$ conda activate platodebs
```
#### Alternative: using a venv

If you prefer not to use a conda environment the following venv setup works
although I haven't tested it as thoroughly and it doesn't have as tight control
over versioning. Again, from this directory run;
```sh
$ python -m venv .platodebs
```
```sh
$ source .platodebs/bin/activate
```
You can then use pip to install the following list of packages;
```
numpy
scipy
numba
h5py
astropy
matplotlib
arviz
corner

lightkurve
ipykernel
ipympl
jupyter

git+https://github.com/LucIJspeert/star_shadow@1.1.7b
```
or create a requirements.txt file, copy the list into it and then run;
```sh
$ pip install -r requirements.txt
```

#### First run to test the environment and JIT STAR SHADOW

In either case, having set up and activated the environment, run the following
which acts as a test of the environment and will get numba to do its JIT magic
on the STAR SHADOW code;
```sh
$ python run_first_use.py
```

## Usage

The code is split into three distinct stages which may be run separately and repeated if necessary.
Each stage is dependent on a targets file (which has been set up for `./tessebs_extra.csv`) and
the output from the previous stage. The target file contains the list of targets, their expected
orbital period, sky position and any information on prioritization.

The stages and STAR SHADOW each save milestone information as they progress and can resume from
the last milestone if a restart is required. 


#### Downloading target fits from MAST
The first stage is to download the target fits files from MAST.
```sh
$ python download_fits.py
```
Currently this does not take any command line argumnts, with its basic parameters set within
the module. These are:
```Python
input_file = Path(".") / "tessebs_extra.csv"
target_filter = []      # optional list(str) of values to match against the input csv's Star column
mission = "TESS"        # MAST search criteria - see Lightkurve docs
author = "SPOC"
exptime = "short"
overwrite = False       # whether to "re-download" each target
```

A target's fits files are downloaded and saved to the `./catalogue/download/{tic}` directory.
This stage saves a target.json file alongside each target's downloaded fits files as a milestone.
Subsequent stages may refer to the json file to confirm the target download has been completed.
You will need to delete the json file or the whole containing folder if you want to force this
module to re-aquire data for a specific target. Alternatively, use a `target_filter` and set
`overwrite = True` to force the re-acquisition of a subset of target (however existing files
are not actively deleted so, if not overwritten, may affect subsequent analysis).

#### Performing the STAR_SHADOW analysis
To get STAR_SHADOW to analyse any targets with a completed download run:
```sh
$ python perform_analysis.py
```
Again, there are no command line arguments but the following parameters control the process:
```Python
input_file = Path(".") / "tessebs_extra.csv"
target_filter = []      # list of index (Star) values to filter the input to
overwrite = False
pool_size = 4
```
The STAR SHADOW analysis can be very time consuming, especially if there are a large number
of fits files for a target. Two strategies have been adopted to reduce the overall elapsed
time taken to complete this step;
1. targets may be analysed in parallel, up to a the maximim indicated by `pool_size`
2. analysis is carried out on a subset of the fits files downloaded for a target
    - this will be at least 5 and is increased for targets with longer orbital periods
(limited by the number of sectors observed)
    - the targets fits are ranked by their `PDC_TOT` metric with the top(N) being used
        - fits where the `PDC_NOI` > 0.99 are heavily penalized as these are often solely noise

This module does not directly save its own milestones, however STAR SHADOW does and these
are used to handle failure and resumption. The milestones, log and analysis output is written
to the `./catalogue/analysis/{tic}_analysis/` directory for each target. The final output
of the analysis for a target, `{tic}_analysis_summary.csv`, contains a list of the system
characteristics resulting from the analysis and will be used by the subsequent stage.

Again, to re-run analyses either delete the corresponding analysis directories or use
a `target_filter` list and set `overwrite = True`.

#### Processing analysis results
If a target's STAR SHADOW analysis completes successfully we can use its output to proces
the lightcurves. The following will process any targets where analysis summaries are found:
```sh
$ python process_results.py ./tessebs_extra.csv
```
This supports the following optional command line arguments:
- the optional first argument is the input csv file holding the target data. 
Must have Star and Period columns. Defaults to ./tessebs_extra.csv
- `-t`/`--targets`: an optional list of target Star value to filter the input csv on
- `-fc`/`--flux-column`: the flux column to read. Wither sap_flux or pdcsap_flux (default)
- `-qb`/`--quality-bitmask`: optional quality bitmask with which to filter observations
    - See [Lightkurve: read()](http://docs.lightkurve.org/reference/api/lightkurve.io.read.html)
for possible string and numeric values. Defaults to 'default'
- `-p`/`--plot`: save plots of the lightcurves. If a directory is also given the plots
will be saved within this, otherwise they will be saved within ./catalogue/plots

For each target, where an analysis summary is found, the following is carried out:
1. The analysis summary is parsed for period, eclipse timing and eclipse duration data
2. For each fits/sector for the target
    1. the lightcurve is loaded and the `flux_column` is normalized
    2. an eclipse mask is created based from the timings in the analysis results
    3. a flattened copy of the lightcurve is made, using the eclipse mask
        - See [Lightkurve: flatten()](http://docs.lightkurve.org/reference/api/lightkurve.LightCurve.flatten.html)
    4. the flattened lightcurve is subtracted from the normalized one to find the residual variability
    5. **TODO**: a variability metric is calculated
    6. optionally, the three lightcurves and the eclipse mask are plotted to a single figure
        - these are saved to `{plot_to}/TIC{tic}/TIC_{tic}_{sector}.png`

There is also a convenience jupyter notebook, `process_target_results.ipynb`, which replicates
this process for a single target except that the plots are rendered interactively. This can be
run from within the **platodebs** conda environment with:
```sh
$ jupyter notebook process_target_results.ipynb
```
This has similar parameters to `process_results.py` except that a single `target` must be given
rather than an optional `target_filter` list.

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
Each stage is dependent on a targets file (which defaults to `./tessebs_extra.csv`) and
the output from the previous stage. The target file contains the list of targets, their expected
orbital period, sky position and any information on prioritization.

The stages and STAR SHADOW each save milestone information as they progress and can resume from
the last milestone if a restart is required. 


#### Downloading target fits from MAST
The first stage is to download the target fits files from MAST with:
```sh
$ python download_fits.py
```

This supports the following command line arguments:
- the optional first argument is the input csv file holding the target data. 
Must have Star and Period columns. Defaults to ./tessebs_extra.csv
- `-t`/`--targets`: an optional list of target Star values to filter the input csv on
- `-m`/`--mission`: the mission search criterion. Defaults to TESS
- `-a`/`--author`: the author search criterion. Defaults to SPOC
- `-e`/`--exptime`: the exposure time search criterion. May be a string or int (seconds)
value. Defaults to short
    - see [Lightkurve: search_lightcurve()](http://docs.lightkurve.org/reference/api/lightkurve.search_lightcurve.html)
    for possible string and numeric values
- `-o`/`--overwrite`: forces (re-)download of the target files

For example:
```sh
$ python download_fits.py ./tessebs_extra.csv -t TIC300560295 TIC307084982 -m TESS -a TESS-SPOC -e 600 -o
```

A target's fits files are downloaded and saved to the `./catalogue/download/{tic}` directory.
This stage saves a target.json file alongside each target's downloaded fits files as a milestone.
Subsequent stages may refer to the json file to confirm the target download has been completed.
You will need to delete the json file or the whole containing folder if you want to force this
module to re-aquire data for a specific target. Alternatively, use a `--targets` filter and
the `--overwrite` flag to force the re-acquisition of a subset of the input targets (however
existing files are not actively deleted so, if not overwritten, may affect subsequent analysis).

#### Performing the STAR_SHADOW analysis
To get STAR_SHADOW to analyse any targets with a completed download run:
```sh
$ python perform_analysis.py
```

This supports the following command line arguments:
- the optional first argument is the input csv file holding the target data. 
Must have Star and Period columns. Defaults to ./tessebs_extra.csv
- `-t`/`--targets`: an optional list of target Star values to filter the input csv on
- `-ps`/`--pool-size`: the maximum number of concurent analyses to run. Defaults to 1
- `-o`/`--overwrite`: forces (re)analysis of the targets, overwriting any existing results

For example:
```sh
$ python perform_analysis.py ./tessebs_extra.csv -t TIC300560295 TIC307084982 -ps 2 -o
```

The STAR SHADOW analysis can be very time consuming, especially if there are a large number
of fits files for a target. Two strategies have been adopted to reduce the overall elapsed
time taken to complete this step;
1. targets' analysis may be performed in parallel, up to the maximim given by `--pool-size`
2. each analysis is carried out on a subset of the fits files downloaded for a target
    - this will be at least 5, but is progressively increased for targets with longer
    orbital periods (ultimately, limited by the number of sectors observed)
    - the targets fits are ranked by their `PDC_TOT` metric with the top(N) being used
        - fits where the `PDC_NOI` > 0.99 are heavily penalized as these are often solely noise

This module does not directly save its own milestones, however STAR SHADOW does and these
are used to handle failure and resumption. STAR SHADOW writes the milestones, log and analysis
output to a `./catalogue/analysis/{tic}_analysis/` directory for each target. The final output
of the analysis for a target, `{tic}_analysis_summary.csv`, contains a list of the system
characteristics resulting from the analysis and will be used by the subsequent stage.

Again, to re-run analyses either delete the corresponding analysis directories or use
a `--targets` filter list and the `--overwrite` flag.

#### Processing analysis results
If a target's STAR SHADOW analysis completes successfully we can use its output to proces
the lightcurves. The following will process any targets where analysis summaries are found:

```sh
$ python process_results.py
```

This supports the following optional command line arguments:
- the optional first argument is the input csv file holding the target data. 
Must have Star and Period columns. Defaults to ./tessebs_extra.csv
- `-t`/`--targets`: an optional list of target Star values to filter the input csv on
- `-fc`/`--flux-column`: the flux column to read. Wither sap_flux or pdcsap_flux (default)
- `-qb`/`--quality-bitmask`: optional bitmask filter to apply over the fluxes' Quality flag.
Defaults to default
    - See [Lightkurve: read()](http://docs.lightkurve.org/reference/api/lightkurve.io.read.html)
for possible string and numeric values
- `-p`/`--plot`: save plots of the lightcurves. If a directory is also given the plots
will be saved within this, otherwise they will be saved within ./catalogue/plots

For example:
```sh
$ python process_results.py ./tessebs_extra.csv -t TIC300560295 TIC307084982 -fc sap_flux -qb hardest -p
```

For each target, where an analysis summary is found, the following is carried out:
1. The analysis summary is parsed for period, eclipse timing and eclipse duration data
2. For each fits/sector for the target
    1. the lightcurve is loaded, filtered on `--quality-bitmask` and the `--flux-column` is normalized
    2. an eclipse mask is created based on the timings in the analysis results
    3. a flattened copy of the lightcurve is made, using the eclipse mask
        - See [Lightkurve: flatten()](http://docs.lightkurve.org/reference/api/lightkurve.LightCurve.flatten.html)
    4. the flattened lightcurve is subtracted from the normalized one to leave the residual variability
    5. a variability metric is calculated
        - this is based on doubling the interquartile range of the residual variability
    6. optionally, the three lightcurves and the eclipse mask are plotted to a single figure
        - these are saved to `{plot_to}/TIC{tic}/TIC_{tic}_{sector}.png`
3. An overall variability metric is given: the mean and 1-sigma of the values across all sectors

There is also a convenience jupyter notebook, `process_target_results.ipynb`, which replicates
this process for a single target except that the plots are rendered interactively. This can be
run from within the **platodebs** conda environment with:
```sh
$ jupyter notebook process_target_results.ipynb
```
This has similar parameters to `process_results.py` except that they are set in the second code cell,
and a single `target` must be given rather than an optional list.

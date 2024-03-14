# platodebs

## POC for a catalogue pipeline for PLATO dEB candidates
### Setting up the platodebs conda environment
This code base was developed on Kubuntu 23.10 within the context of
an [Anaconda 3](https://www.anaconda.com/) conda environment named **platodebs**. 
This environment is configured to support _Python 3.7_, 
the [STAR SHADOW](https://github.com/LucIJspeert/star_shadow) analysis tool
and any libraries upon which the code is dependent.

To set up the **platodebs** environment, having first cloned the GitHub repo, 
open a Terminal, navigate to this directory and run the following command;
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
although I haven't tested it as thoroughly. Again from this directory run;
```sh
$ python -m venv .platodebs
```
```sh
$ source .platodebs/bin/activate
```
You can then use pip to install the follow packages
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
git+https://github.com/LucIJspeert/star_shadow@1.1.7b
```
or create a requirements.txt file, copy the list in and then run 
```sh
$ pip install -r requirements.txt
```

#### First run to test the environment and JIT STAR SHADOW
In either case, having set up and activated the environment, run the following
which acts as a test of the environment and will get numba to JIT the
STAR SHADOW code.
```sh
$ python run_first_use.py
```

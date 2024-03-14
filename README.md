# platodebs

## POC for a catalogue pipeline for PLATO dEB candidates
This code base was developed in VSCode (on Kubuntu 23.10) within the context of
an [Anaconda 3](https://www.anaconda.com/) environment named **platodebs**. 
This environment is configured to support _Python 3.7_, 
the [STAR SHADOW](https://github.com/LucIJspeert/star_shadow) tool and any
libraries upon which the code is dependent.

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

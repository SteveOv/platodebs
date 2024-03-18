""" Downloads TESS timeseries fits files for the targets in tessebs_extra.csv"""
from pathlib import Path
import json

import pandas as pd
import lightkurve as lk

# Basic params - may convert to args
input_file = Path(".") / "tessebs_extra.csv"
chosen_target = None
overwrite = False
flux_column = "pdcsap_flux"

catalogue_dir = Path(".") / "catalogue"
catalogue_dir.mkdir(parents=True, exist_ok=True)
empty_targets = []

# Optionally filter the targets to a single system
input_df = pd.read_csv(input_file, index_col="Star")
#ebs_df.sort_values(by="Priority", inplace=True)
targets = input_df.iterrows()
count_targs = len(input_df)
if chosen_target: 
    targets = [(targ, row) for targ, row in targets if targ == chosen_target]
    count_targs = len(targets)

for target_ix, (target, target_row) in enumerate(targets, start=1):
    tic = target_row["TIC"]
    print()
    print("---------------------------------------------")
    print(f"Processing target ({target_ix}/{count_targs}): {target}")
    print("---------------------------------------------")

    download_dir = catalogue_dir / f"download/{tic:010d}/"
    target_json = download_dir / "target.json"
    if not overwrite and target_json.exists():
        print(f"A download for this target already exists. Skipping.")
    else:
        print(f"Searching for TESS target: {target}")
        results = lk.search_lightcurve(target = target,
                                       mission = "TESS",
                                       author = "SPOC",
                                       exptime="short")
        print(f"The following results have been found for {target}:", results)
        if results:
            lcs = results.download_all(download_dir=f"{download_dir}",
                                       flux_column=flux_column)
            if len(lcs):
                print(f"Downloaded {len(lcs)} LCs")
            else:
                print("Nothing downloaded")
                empty_targets.append(target)

            # Write out the supplied input metadata for this target
            # so we can refer to it when processing the assets.
            # This also acts as "lock" indicating we've downloaded this one
            with open(target_json, mode="w", encoding="utf8") as of:
                json.dump({ "Star": target, **target_row.to_dict() }, 
                          of, ensure_ascii=False, indent=2)
        else:
            print(f"No assets found for target: {target}")
            empty_targets.append(target)

if len(empty_targets):
    print(f"No assets found for the following targets; {empty_targets}")

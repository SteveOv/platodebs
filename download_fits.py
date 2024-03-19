"""
Downloads TESS timeseries fits files for the targets in tessebs_extra.csv.
Will write the fits files into a directory structure under ./catalogue/download/
"""
from pathlib import Path
import json
import lightkurve as lk
from utility import iterate_targets

# Basic params - may convert to args
input_file = Path(".") / "tessebs_extra.csv"
target_filter = []      # list of index (Star) values to filter the input to
mission = "TESS"        # MAST search criteria
author = "SPOC"
exptime = "short"
overwrite = False       # whether to "re-download" each target

catalogue_dir = Path(".") / "catalogue"
catalogue_dir.mkdir(parents=True, exist_ok=True)
empty_targets = []

for counter, (target, target_row, total_rows) in enumerate(
        iterate_targets(input_file, filter=target_filter, nan_to_none=True),
        start=1):
    tic = target_row["TIC"]
    print()
    print("---------------------------------------------")
    print(f"Processing target ({counter}/{total_rows}): {target}")
    print("---------------------------------------------")

    download_dir = catalogue_dir / f"download/{tic:010d}/"
    target_json = download_dir / "target.json"
    if not overwrite and target_json.exists():
        print(f"A download for this target already exists. Skipping.")
    else:
        print(f"Searching for TESS target: {target}")
        results = lk.search_lightcurve(target, mission=mission, author=author, exptime=exptime)
        
        print(f"The following results have been found for {target}:", results)
        if results:
            lcs = results.download_all(download_dir=f"{download_dir}")
            if len(lcs):
                print(f"Downloaded {len(lcs)} LCs")
            else:
                print("Nothing downloaded")
                empty_targets.append(target)

            # Write out the supplied input metadata for this target
            # so we can refer to it when processing the assets.
            # This also acts as "lock" indicating we've downloaded this one
            with open(target_json, mode="w", encoding="utf8") as fp:
                json.dump({ "Star": target, **target_row }, fp, ensure_ascii=False, indent=2)
        else:
            print(f"No assets found for target: {target}")
            empty_targets.append(target)

if len(empty_targets):
    print(f"No assets found for the following targets; {empty_targets}")

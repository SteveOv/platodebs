"""
Downloads TESS timeseries fits files for the targets in tessebs_extra.csv.
Will write the fits files into a directory structure under ./catalogue/download/
"""
from pathlib import Path
import argparse
import json

import lightkurve as lk
from utility import iterate_targets

# Handle the command line args
DESCRIPTION = "Downloads TESS lightcurve fits files for selected targets."
ap = argparse.ArgumentParser(description=DESCRIPTION)
ap.add_argument(dest="input_file", type=Path, nargs="?",
                help="The input file to read the targets from. Defaults to ./tessebs_extra.csv")
ap.add_argument("-t", "--targets", dest="targets",
                type=str, nargs="+", metavar="STAR", required=False,
                help="Optional list of targets, within the input file, to restrict processing to")
ap.add_argument("-m", "--mission", dest="mission", type=str, required=False,
                help="The mission criterion for the lightcurve search [TESS]")
ap.add_argument("-a", "--author", dest="author", type=str, required=False,
                help="The author criterion for the lightcurve search [SPOC]")
ap.add_argument("-e", "--exptime", dest="exptime", type=str, required=False,
                help="The exposure time criterion for the lightcurce search [short]")
ap.add_argument("-o", "--overwrite", dest="overwrite", required=False, action="store_true",
                help="force re-download, potentially overwriting any previous downloaded files")
ap.set_defaults(input_file=Path(".") / "tessebs_extra.csv",
                targets=[],
                mission="TESS",
                author="SPOC",
                exptime="short",
                overwrite=False)
args = ap.parse_args()
if args.exptime.isdecimal(): # support numeric exptime values too
    args.exptime = int(args.exptime)

catalogue_dir = Path(".") / "catalogue"
catalogue_dir.mkdir(parents=True, exist_ok=True)
empty_targets = []

for counter, (target, target_row, total_rows) in enumerate(
        iterate_targets(args.input_file, index_filter=args.targets, nan_to_none=True),
        start=1):
    tic = target_row["TIC"]
    print()
    print("---------------------------------------------")
    print(f"Processing target ({counter}/{total_rows}): {target}")
    print("---------------------------------------------")

    download_dir = catalogue_dir / f"download/{tic:010d}/"
    target_json = download_dir / "target.json"
    if not args.overwrite and target_json.exists():
        print("A download for this target already exists. Skipping.")
    else:
        print(f"Searching for TESS target: {target}")
        results = lk.search_lightcurve(target,
                                       mission=args.mission,
                                       author=args.author,
                                       exptime=args.exptime)

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

if empty_targets:
    print(f"No assets found for the following targets; {empty_targets}")

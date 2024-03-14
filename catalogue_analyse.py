"""
Perform STAR SHADOW analysis on previously downloaded TESS timeseries fits files
(using catalogue_download_fits.py) for the targets in tessebs_extra.csv
"""
from pathlib import Path

import pandas as pd
import star_shadow as sts

# Basic params - may convert to args
input_file = Path(".") / "tessebs_extra.csv"
overwrite = False

catalogue_dir = Path(".") / "catalogue"
analysis_dir = catalogue_dir / "analysis"
analysis_dir.mkdir(parents=True, exist_ok=True)


input_df = pd.read_csv(input_file, index_col="Star")
#ebs_df.sort_values(by="Priority", inplace=True)
for target_ix, (target, target_row) in enumerate(input_df.iterrows(), start=1):
    tic = target_row["TIC"]
    print()
    print("---------------------------------------------")
    print(f"Processing target ({target_ix}/{len(input_df)}): {target}")
    print("---------------------------------------------")

    target_dir = catalogue_dir / f"download/{tic:010d}/"

    # Use the existance of the output/analysis*/*_analysis_summary.csv as a lock
    analysis_csv = analysis_dir / f"{tic}_analysis" / f"{tic}_analysis_summary.csv"
    if not overwrite and analysis_csv.exists():
        # sts won't restart a completed analysis unless overwrite=True so this
        # check isn't entirely necessary but it does make the console log clearer.
        print(f"Found analysis summary csv: {analysis_csv}")
        print(f"Analysis summary exists for {target}. Skipping to next target.")
    else:
        print(f"No analysis summary csv found for {target}. Proceeding with analysis.")

        fits_files = sorted(f"{f}" for f in target_dir.glob("**/*.fits"))
        print(f"Found {len(fits_files)} fits file(s) for {target}.")
        print()

        # With overwrite=False this appears to be able to resume from last
        # completed stage. Set overwrite=True to restart the analysis anyway.
        sts.analyse_lc_from_tic(tic,
                                fits_files,
                                p_orb=target_row["Period"],
                                stage='all',
                                method='fitter',
                                data_id=target,
                                save_dir=f"{analysis_dir}",
                                overwrite=overwrite,
                                verbose=True)

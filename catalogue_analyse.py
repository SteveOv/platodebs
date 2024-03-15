"""
Perform STAR SHADOW analysis on previously downloaded TESS timeseries fits files
(using catalogue_download_fits.py) for the targets in tessebs_extra.csv
"""
from pathlib import Path
import math
from multiprocessing import Pool, cpu_count

import pandas as pd
from astropy.io import fits
import star_shadow as sts

# Basic params - may convert to args
input_file = Path(".") / "tessebs_extra.csv"
overwrite = False
pool_size = 4


def fits_criteria(hdul):
    """
    Suitability criteria applied to fits/LC files (via their HDU lists)
    """
    pdc_tot = hdul[1].header["PDC_TOT"]
    pdc_noi = hdul[1].header["PDC_NOI"]
    return pdc_tot / (1 if pdc_noi <= 0.99 else 100)

def analyse_target(target_ix, target, target_row, total_rows):
    """
    Analyse a single target
    """
    tic = target_row["TIC"]
    period = target_row["Period"]
    print()
    print("---------------------------------------------")
    print(f"Processing target {target_ix}/{total_rows}: {target}")
    print("---------------------------------------------")
    print(f"{target}: Input catalogue gives the period as {period} d.")

    catalogue_dir = Path(".") / "catalogue"
    analysis_dir = catalogue_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    target_dir = catalogue_dir / f"download/{tic:010d}/"

    # Use the existance of the output/analysis*/*_analysis_summary.csv as a lock
    analysis_csv = analysis_dir / f"{tic}_analysis" / f"{tic}_analysis_summary.csv"
    if not overwrite and analysis_csv.exists():
        # sts won't restart a completed analysis unless overwrite=True so this
        # check isn't entirely necessary but it does make the console log clearer.
        print(f"{target}: Found analysis summary csv: {analysis_csv}")
        print(f"{target}: Analysis summary exists. Skipping to next target.")
    else:
        print(f"{target}: No analysis summary csv found so proceeding with analysis.")

        # All the fits previous downloaded for this target
        fits_files = sorted(f"{f}" for f in target_dir.glob("**/*.fits"))

        # The fits.open() call returns a file's HDU list from which we read its metadata.
        # Sort these by chosen criteria & truncate then sort what's left into sector order.
        top_n = max(5, math.ceil((period or 1) / 4))
        best_hduls = sorted(
            sorted([fits.open(f) for f in fits_files], key=fits_criteria, reverse=True)[:top_n],
            key=lambda hdul: hdul[0].header["SECTOR"])
        fits_files, sectors = zip(*[(h.filename(), h[0].header["SECTOR"]) for h in best_hduls])

        print(f"{target}: Will analyse sectors: {sectors}")
        print()

        # With overwrite=False this appears to be able to resume from last
        # completed stage. Set overwrite=True to restart the analysis anyway.
        sts.analyse_lc_from_tic(tic,
                                fits_files,
                                p_orb=period,
                                stage='all',
                                method='fitter',
                                data_id=target,
                                save_dir=f"{analysis_dir}",
                                overwrite=overwrite,
                                verbose=True)


# -------------------------------------------
# Analysis master processing starts here
# -------------------------------------------
if __name__ == "__main__":
    input_df = pd.read_csv(input_file, index_col="Star")
    #input_df.sort_values(by="Priority", inplace=True)

    # Need all params in the form [(1, targ1, row1, total), (2, targ2, row2, total), ...]
    tot = len(input_df)
    iter_prms = ((i, targ, row, tot) for i, (targ, row) in enumerate(input_df.iterrows(), start=1))
    if pool_size <= 1: # We could use a pool of 1 but let's keep execution on the interactive proc
        for prms in iter_prms:
            analyse_target(*prms)
    else:
        with Pool(pool_size) as pool:
            pool.starmap(analyse_target, iter_prms, chunksize=1)

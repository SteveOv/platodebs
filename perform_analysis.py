"""
Perform STAR SHADOW analysis on previously downloaded TESS timeseries fits files
(using catalogue_download_fits.py) for the targets in tessebs_extra.csv
"""
from pathlib import Path
import argparse
import math
from multiprocessing import Pool

from astropy.io import fits
import star_shadow as sts

from utility import iterate_targets


def fits_criteria(hdul):
    """
    Suitability criteria applied to fits/LC files (via their HDU lists).
    Returns a single numeric value for the suitability; higher is better.
    """
    pdc_tot = hdul[1].header["PDC_TOT"] # PDC Total goodness metric for target
    pdc_noi = hdul[1].header["PDC_NOI"] # PDC Noise goodness metric for target

    # Basic metric is based on PDC_TOT but we penalize high PDC_NOI (>.99)
    # as (based on inspection) these usually have noise swamping any signal.
    return pdc_tot / (1 if pdc_noi <= 0.99 else 100)

def analyse_target(counter: int,
                   target: str,
                   target_row: dict,
                   total_rows: int,
                   overwrite_analysis: bool=False) -> None:
    """
    Performs full STAR_SHADOW analysis on a single target system.

    :target_ix: simple counter/index for the target for messages
    :target: the name of the target
    :target_row: the input data associated with the target
    :total_rows: total number of targets being processed (for messages)
    :overwrite_analysis: whether to force the analysis to overwrite previous results
    """
    tic = target_row["TIC"]
    period = target_row["Period"]
    print()
    print("---------------------------------------------")
    print(f"Processing target {counter}/{total_rows}: {target}")
    print("---------------------------------------------")
    print(f"{target}: Input catalogue gives the period as {period} d.")

    catalogue_dir = Path(".") / "catalogue"
    analysis_dir = catalogue_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    target_dir = catalogue_dir / f"download/{tic:010d}/"

    # Use the existance of the output/analysis*/*_analysis_summary.csv as a lock
    # Note: STAR_SHADOW uses the numeric TIC without leading zeros in dir/file names.
    analysis_csv = analysis_dir / f"{tic}_analysis" / f"{tic}_analysis_summary.csv"
    if not overwrite_analysis and analysis_csv.exists():
        # sts won't restart a completed analysis unless overwrite=True so this
        # check isn't entirely necessary but it does make the console log clearer.
        print(f"{target}: Found analysis summary csv '{analysis_csv}'. Skipping to next target.")
    else:
        print(f"{target}: No analysis summary csv found so proceeding with analysis.")

        # All the fits previous downloaded for this target
        fits_files = sorted(f"{f}" for f in target_dir.glob("**/*.fits"))
        print(f"{target}: Found {len(fits_files)} downloaded fits file(s) for this target.")

        # As an optimization avoid using all (potentially 30+) fits for the analysis.
        # We choose the max sectors based on the period so with increasing period more
        # sectors are used to improve the chance of capturing the less frequent eclipses.
        top_n = max(5, math.ceil((period or 1) / 4))

        # As we're not using all the sectors we need to choose the ones most likely
        # to yield a good analysis. Each sector's metadata are assessed with the
        # fits_criteria() call with the top(N) best performing sectors selected.
        hduls = sorted((fits.open(f) for f in fits_files), key=fits_criteria, reverse=True)[:top_n]

        # Finally get things back into sector order for processing by STAR_SHADOW
        hduls = sorted(hduls, key=lambda hdul: hdul[0].header["SECTOR"])
        fits_files, sectors = zip(*[(h.filename(), h[0].header["SECTOR"]) for h in hduls])

        # With overwrite=False this appears to be able to resume from last
        # completed stage. Set overwrite=True to restart the analysis anyway.
        print(f"{target}: Will use sector(s) {sectors} for STAR_SHADOW analysis.\n")
        sts.analyse_lc_from_tic(tic,
                                fits_files,
                                p_orb=period,
                                stage='all',
                                method='fitter',
                                data_id=target,
                                save_dir=f"{analysis_dir}",
                                overwrite=overwrite_analysis,
                                verbose=True)

    # TODO: a summary of the eclipse data, from analysis log & csv, or a failure message


# -------------------------------------------
# Analysis master processing starts here
# -------------------------------------------
if __name__ == "__main__":

    # Handle the command line args
    DESCRIPTION = "Analyses previously downloaded TESS lightcurves with STAR SHADOW."
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument(dest="input_file", type=Path, nargs="?",
                    help="The input file to read the targets from. Defaults to ./tessebs_extra.csv")
    ap.add_argument("-t", "--targets", dest="targets",
                type=str, nargs="+", metavar="STAR", required=False,
                help="Optional list of targets, within the input file, to restrict processing to")
    ap.add_argument("-o", "--overwrite", dest="overwrite", required=False, action="store_true",
                    help="force re-analysis, overwriting any previous results")
    ap.add_argument("-ps", "--pool-size", dest="pool_size", type=int, required=False,
                    help="The maximum number of concurrent analyses to run [1]")
    ap.set_defaults(input_file=Path(".") / "tessebs_extra.csv",
                    targets=[],
                    overwrite=False,
                    pool_size=1)
    args = ap.parse_args()

    # For the analyse_target calls, starmap requires an iterator over the sorted params
    # in the form [(1, targ1, row1, total, ow), (2, targ2, row2, total, ow), ...]
    iter_prms = (
        (i, targ, row, tot, args.overwrite) for i, (targ, row, tot) in enumerate(
            iterate_targets(args.input_file, index_filter=args.targets),
            start=1)
    )

    if args.pool_size <= 1: # We could use a pool of 1, but keep execution on the interactive proc
        for prms in iter_prms:
            analyse_target(*prms)
    else:
        with Pool(args.pool_size) as pool:
            pool.starmap(analyse_target, iter_prms, chunksize=1)

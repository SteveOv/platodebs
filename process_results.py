"""
Uses the results of STAR SHADOW analysis, especially eclipse timing and contact
points, to set up eclipse masks and subsequently flatten catelogue light-curves.
"""
from pathlib import Path
import argparse

import numpy as np
import matplotlib.pyplot as plt
import lightkurve as lk

from utility import iterate_targets
from utility import echo_analysis_log, parse_analysis_for_eclipses, lookup_tess_ebs_ephemeris
from utility import flatten_lightcurve, plot_lightcurves_and_mask
from utility import calculate_variability_metric

# Handle the command line args
DESCRIPTION = "Calculates the variability metrics for the target systems in the input file."
ap = argparse.ArgumentParser(description=DESCRIPTION)
ap.add_argument(dest="input_file", type=Path, nargs="?",
                help="The input file to read the targets from. Defaults to ./tessebs_extra.csv")
ap.add_argument("-t", "--targets", dest="targets",
                type=str, nargs="+", metavar="STAR", required=False,
                help="Optional list of targets, within the input file, to restrict processing to")
ap.add_argument("-fc", "--flux-column", dest="flux_column", type=str, required=False,
                choices=["sap_flux", "pdcsap_flux"], help="The flux_column to use [pdcsap_flux]")
ap.add_argument("-qb", "--quality-bitmask", dest="quality_bitmask", type=str, required=False,
                help="An optional quality bitmask to apply to the lightcurves. Defaults to hardest")
ap.add_argument("-p", "--plot", dest="plot_to", type=Path, required=False,
                nargs="?", const=Path(".") / "catalogue" / "plots", metavar="PATH",
                help="Save plots for each target sector and optionally where to save them")
ap.set_defaults(input_file=Path(".") / "tessebs_extra.csv",
                targets=[],
                flux_column="pdcsap_flux",
                quality_bitmask="default",
                plot_to=None)
args = ap.parse_args()
if args.quality_bitmask.isdecimal(): # support numeric quality_bitmask values too
    args.quality_bitmask = int(args.quality_bitmask)

catalogue_dir = Path(".") / "catalogue"
analysis_dir = catalogue_dir / "analysis"
analysis_dir.mkdir(parents=True, exist_ok=True)

print(f"Reading targets from {args.input_file}")
for counter, (target, target_row, count_rows) in enumerate(
        iterate_targets(args.input_file, index_filter=args.targets),
        start=1):
    tic = target_row["TIC"]
    print(f"""
---------------------------------------------
Processing target {counter}/{count_rows}: {target}
---------------------------------------------""")

    # Use the existance of the output/analysis*/*_analysis_summary.csv as a lock
    analysis_csv = analysis_dir / f"{tic}_analysis" / f"{tic}_analysis_summary.csv"
    if not analysis_csv.exists():
        print(f"Did not find '{analysis_csv}'. Unable to process {target}. Skipping.")
    else:
        echo_analysis_log(analysis_csv.parent / f"{tic}.log")
        (t0, period, ecl_times, ecl_durs) = parse_analysis_for_eclipses(analysis_csv)
        if t0 is None or t0 <= 0.:
            t0, _ = lookup_tess_ebs_ephemeris(target, tic)
            if t0 and t0 > 0.:
                print(f"Analysis didn't find a reference time so using {t0:.6f} from TESS-ebs.")
                ecl_times = [et + t0 for et in ecl_times]

        # Directories based on the tic without leading zeros to match STAR SHADOW's naming
        download_dir = catalogue_dir / f"download/{tic}/"
        target_json = download_dir / "target.json"

        fits = sorted(download_dir.rglob("**/*.fits"))
        lcs = lk.LightCurveCollection([
            lk.read(f"{f}", flux_column=args.flux_column, quality_bitmask=args.quality_bitmask)
                for f in fits])
        print(f"\nLoaded {len(lcs)} light curve fits file(s) for", target)

        variabilities = []
        for lc in lcs:
            sector = lc.meta["SECTOR"]

            # Process the light curve
            lc = lc.normalize()
            flat_lc, res_lc, ecl_mask = flatten_lightcurve(lc, ecl_times, ecl_durs, period)
            variability = calculate_variability_metric(res_lc)
            variabilities.append(variability)
            print(f"Processed sector {sector:03d} {args.flux_column}",
                  f"and calculated its variability metric to be {variability:.6f}")

            # Plots
            if args.plot_to:
                plot_file = args.plot_to / f"{tic}/{target}_{sector:03d}.png"
                plot_file.parent.mkdir(parents=True, exist_ok=True)
                title = f"{lc.meta['OBJECT']} sector {sector:03d} (variability = {variability:.6f})"
                fig, _ = plot_lightcurves_and_mask(lc, flat_lc, res_lc, ecl_mask, (8, 6), title)
                fig.savefig(plot_file, dpi=100)
                plt.close(fig)

        # Calculating the variability by sector & taking the mean/stddev appears
        # more reliable than stitching the res_lcs and calculating the metric directly.
        # The stitched resids suffer from large discursions absent from the source lcs.
        print("\nThe overall variability metric =",
              f"{np.mean(variabilities):.6f}+/-{np.std(variabilities):.6f}\n")

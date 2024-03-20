"""
Uses the results of STAR SHADOW analysis, especially eclipse timing and contact
points, to set up eclipse masks and subsequently flatten catelogue light-curves.
"""
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import lightkurve as lk

from utility import iterate_targets
from utility import echo_analysis_log, parse_analysis_for_eclipses
from utility import flatten_lightcurve, plot_lightcurves_and_mask
from utility import calculate_variability_metric

# Basic params - may convert to args
# pylint: disable=invalid-name
input_file = Path(".") / "tessebs_extra.csv"
target_filter = []      # list of index (Star) values to filter the input to
flux_column = "pdcsap_flux"
quality_bitmask = "hardest"
save_plots = False

catalogue_dir = Path(".") / "catalogue"
analysis_dir = catalogue_dir / "analysis"
analysis_dir.mkdir(parents=True, exist_ok=True)

for counter, (target, target_row, count_rows) in enumerate(
        iterate_targets(input_file, index_filter=target_filter),
        start=1):
    tic = target_row["TIC"]
    print()
    print("---------------------------------------------")
    print(f"Processing target ({counter}/{count_rows}): {target}")
    print("---------------------------------------------")

    # Use the existance of the output/analysis*/*_analysis_summary.csv as a lock
    analysis_csv = analysis_dir / f"{tic}_analysis" / f"{tic}_analysis_summary.csv"
    if not analysis_csv.exists():
        print(f"Did not find '{analysis_csv}'. Unable to process {target}. Skipping.")
    else:
        echo_analysis_log(analysis_csv.parent / f"{tic}.log")
        (t0, period, ecl_times, ecl_durs) = parse_analysis_for_eclipses(analysis_csv)

        # Now we can process each LC for this target
        target_dir = catalogue_dir / f"download/{tic:010d}/"
        target_json = target_dir / "target.json"
        plots_dir = catalogue_dir / "plots" / f"{target}"
        plots_dir.mkdir(parents=True, exist_ok=True)

        fits = sorted(target_dir.rglob("**/*.fits"))
        lcs = lk.LightCurveCollection([
            lk.read(f"{f}", flux_column=flux_column, quality_bitmask=quality_bitmask)
                for f in fits])
        print(f"\nLoaded {len(lcs)} light curve fits file(s) for {target}.")

        variabilities = []
        for lc in lcs:
            sector = lc.meta["SECTOR"]
            print(f"Processing sector {sector:03d}")

            # Process the light curve
            lc = lc.normalize()
            flat_lc, res_lc, ecl_mask = flatten_lightcurve(lc, ecl_times, ecl_durs, period)
            variability = calculate_variability_metric(res_lc)
            variabilities.append(variability)

            # Plots
            if save_plots:
                title = f"{lc.meta['OBJECT']} sector {sector:03d}"
                print("Saving plots for", title)
                fig, _ = plot_lightcurves_and_mask(lc, flat_lc, res_lc, ecl_mask, (8, 6), title)
                fig.savefig(plots_dir / f"{target}_{sector:03d}.png", dpi=100)
                plt.close(fig)

        # Calculating the variability by sector & taking the mean/stddev appears
        # more reliable than stitching the res_lcs and calculating the metric directly.
        # The stitched resids suffer from large discursions absent from the source lcs.
        print("\nThe overall variability metric =",
              f"{np.mean(variabilities):.6f}+/-{np.std(variabilities):.6f}")

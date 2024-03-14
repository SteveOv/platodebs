"""
Uses the results of STAR SHADOW analysis, especially eclipse timing and contact
points, to set up eclipse masks and subsequently flatten catelogue light-curves.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import lightkurve as lk
from uncertainties import ufloat

# Basic params - may convert to args
input_file = Path(".") / "tessebs_extra.csv"
overwrite = False
flux_column = "pdcsap_flux"

catalogue_dir = Path(".") / "catalogue"
analysis_dir = catalogue_dir / "analysis"
analysis_dir.mkdir(parents=True, exist_ok=True)


def read_ufloat(summary, nom_key, err_key=None) -> ufloat:
    """ Read a value and errorbar from the summary into a ufloat. """
    nom = summary.loc[nom_key]["val"] if nom_key in summary.index else 0
    if not err_key:
        err_key = nom_key + "_err"
    err = abs(summary.loc[err_key]["val"] if err_key in summary.index else 0)
    return ufloat(nom, err)


input_df = pd.read_csv(input_file, index_col="Star")
#ebs_df.sort_values(by="Priority", inplace=True)
for target_ix, (target, target_row) in enumerate(input_df.iterrows(), start=1):
    tic = target_row["TIC"]
    print()
    print("---------------------------------------------")
    print(f"Processing target ({target_ix}/{len(input_df)}): {target}")
    print("---------------------------------------------")

    # Use the existance of the output/analysis*/*_analysis_summary.csv as a lock
    analysis_csv = analysis_dir / f"{tic}_analysis" / f"{tic}_analysis_summary.csv"
    if not analysis_csv.exists():
        print(f"Did not find analysis summary csv: {analysis_csv}")
        print(f"Unable to flatten {target}. Skipping to next target.")
    else:
        summary = pd.read_csv(analysis_csv, sep=",", skiprows=2, 
                              names=["name", "val", "desc"], index_col="name")

        t0 = read_ufloat(summary, "t_mean")
        period = read_ufloat(summary, "period", "p_err")

        eclipse_times = [
            (t0 + read_ufloat(summary, "t_1")),
            (t0 + read_ufloat(summary, "t_2"))
        ]

        eclipse_durations = [
            (read_ufloat(summary, "t_1_2") - read_ufloat(summary, "t_1_1")),
            (read_ufloat(summary, "t_2_2") - read_ufloat(summary, "t_2_1"))
        ]

        print("From analysis summary")
        print(f"Reference time:      {t0:.6f}")
        print(f"Orbital period:      {period:.6f}")
        print(f"Eclipse times:      ", ", ".join(f"{t:.6f}" for t in eclipse_times))
        print(f"Eclipse durations:  ", ", ".join(f"{t:.6f}" for t in eclipse_durations))

        if any(t.nominal_value == 0 for t in eclipse_durations):
            print("At least one duration is zero - were eclipses found?")

        # Now we can process each LC for this target            
        target_dir = catalogue_dir / f"download/{tic:010d}/"
        target_json = target_dir / "target.json"
        plots_dir = catalogue_dir / "plots" / f"{target}"
        plots_dir.mkdir(parents=True, exist_ok=True)
        fits = sorted(target_dir.rglob("**/*.fits"))
        lcs = lk.LightCurveCollection([lk.read(f"{f}", flux_column=flux_column) for f in fits])
        print(f"Loaded {len(lcs)} light curve fits file(s) for {target}.")

        for lc in lcs:
            sector = lc.meta["SECTOR"]
            print(f"Sector {sector:03d}...", end="")

            fig, axes = plt.subplots(2, 1, sharex="all", figsize=(10, 6), constrained_layout=True)
            axes = axes.flatten()
            fig.suptitle(f"{lc.meta['OBJECT']} sector {sector:03d}")

            # Optionally normlize
            print("normalizing...", end="")
            lc = lc.normalize()

            # We can plot the raw LC in the upper ax
            lc.scatter(ax=axes[0], label=flux_column)
            axes[0].set_xlabel(None)

            # Work out the eclipse mask for this sector
            print("creating mask...", end="")
            transit_mask = lc.create_transit_mask(
                transit_time=[t.nominal_value for t in eclipse_times],
                duration=[t.nominal_value for t in eclipse_durations],
                period=[period.nominal_value, period.nominal_value])   

            # Plot the masks above the LC in the upper ax
            masked_times = lc.time[transit_mask].value
            masked_flux = [axes[0].get_ylim()[1]] * len(masked_times)
            axes[0].scatter(x=masked_times, y=masked_flux, marker=".")

            # Produce the flattened LC, based on the mask, and plot on lower ax
            print("flattening...", end="")
            flat_lc = lc.flatten(mask=transit_mask)
            flat_lc.scatter(ax=axes[1], label=None)

            print(f"saving plots...", end="")
            plt.savefig(plots_dir / f"{target}_{sector:03d}.png", dpi=300)
            plt.close()
            print("done.")

# Save the ebs dataset to a new file
input_df.to_csv(catalogue_dir / "tessebs_extra_eclipses.csv", sep=",")
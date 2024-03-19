from typing import List, Tuple, Union
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from uncertainties import ufloat, UFloat
from lightkurve import LightCurve

def iterate_targets(input_csv: Path,
                    index_col: str="Star",
                    filter: List[str]=None,
                    sort_by: str=None,
                    nan_to_none: bool=True):
    """
    Iterate through the list of targets held in the input csv file, yielding
    a tuple of the index value, the rest of the row as a dict and total row count.
    The csv file is expected to have an initial row of column names and a comma
    as a column separator.

    :input_csv: the input csv file
    :index_col: the name of the csv column to index on
    :filter: optional list of index values to filter results by (unfiltered if empty)
    :sort_by: optional sort column; prefix with + or - for asc/descending sort
    :nan_to_none: whether to substitute None for NaN values
    :returns: yields a tuple of the index value, row dict and total row count
    """
    input_df = pd.read_csv(input_csv, index_col=index_col, sep=",", header=0)
    if nan_to_none:
        input_df.replace({ np.nan: None }, inplace=True)

    if filter and len(filter) > 0:
        input_df = input_df[input_df.index.isin(filter)]
    
    if sort_by:
        if sort_by.startswith("-"):
            sort_by = sort_by.strip("-")
            ascending = False
        else:
            sort_by = sort_by.strip("+")
            ascending = True
        input_df.sort_values(by=sort_by, ascending=ascending, inplace=True)

    count = len(input_df)
    for index, row in input_df.iterrows():
        # Return the row as a dict so client need know nothing of how we do this
        yield index, row.to_dict(), count


def echo_analysis_log(analysis_log: Path) -> None:
    """
    Will echo the contents of a STAR_SHADOW analysis log file to the console.

    :analysis_log: the input log file
    """
    print("Analysis Log:")
    if not analysis_log.exists():
        print("*** Not found ***")
    else:
        with (analysis_log).open(mode="r") as lf:
            block = "\n".join(l.strip() for l in lf.readlines())
            print(block)


def parse_analysis_for_eclipses(analysis_csv: Path,
                                duration_scale: float=1.,
                                verbose: bool=True) \
        -> Union[Tuple[UFloat, UFloat, List[UFloat], List[UFloat]], None]:
    """
    Will parse a STAR_SHADOW analysis_summary csv file for the eclipse results.

    :analysis_csv: the path of the csv file to open.
    :duration_scale: an optional scaling multiplier to apply to the analysis eclipse durations
    :verbose: whether to print out eclipse details to the console
    :returns: a tuple in the form (reference_time, period, [eclipe_times], [eclipse_durations])
    or None if the analysis_summary csv was not found.
    """
    if not analysis_csv.exists():
        return None

    smry = pd.read_csv(analysis_csv, sep=",", skiprows=2,
                       names=["name", "val", "desc"], index_col="name")

    t0 = read_analysis_value(smry, "t_mean")
    period = read_analysis_value(smry, "period", "p_err")

    eclipse_times = [
        (t0 + read_analysis_value(smry, "t_1")),
        (t0 + read_analysis_value(smry, "t_2"))
    ]

    eclipse_durations = [
        (read_analysis_value(smry, "t_1_2") - read_analysis_value(smry, "t_1_1")) * duration_scale,
        (read_analysis_value(smry, "t_2_2") - read_analysis_value(smry, "t_2_1")) * duration_scale
    ]

    if verbose:
        print(f"From {analysis_csv.name}")
        print(f"Reference time:              {t0:.6f}")
        print(f"Orbital period:              {period:.6f}")
        print(f"Eclipse times:              ", ", ".join(f"{t:.6f}" for t in eclipse_times))
        print(f"Eclipse durations:          ", ", ".join(f"{t:.6f}" for t in eclipse_durations))
        if duration_scale != 1.:
            print(f"Eclipse durations scaled by: {duration_scale}")
        if any(t.nominal_value == 0 for t in eclipse_durations):
            print("At least one eclipse duration is zero. Were eclipses found?")

    return t0, period, eclipse_times, eclipse_durations


def read_analysis_value(summary: pd.DataFrame, nominal_key: str, err_key: str=None) \
        -> Union[UFloat, None]:
    """
    Read a value and errorbar from the analysis summary.

    :summary: the analysis summary DataFrame - should be indexed on "name"
    :nominal_key: the nominal name to lookup
    :err_key: the error index name - if omitted will default to nominal_key with _err suffix
    :returns: an uncertainties ufloat with the requested value or None if not found
    """
    nom = summary.loc[nominal_key]["val"] if nominal_key in summary.index else None
    if nom:
        if not err_key:
            err_key = nominal_key + "_err"
        err = abs(summary.loc[err_key]["val"] if err_key in summary.index else 0)
    return ufloat(nom, err) if nom else None


def flatten_lightcurve(lc: LightCurve,
                       eclipse_times: List[UFloat],
                       eclipse_durations: List[UFloat],
                       orbital_period: UFloat) \
                            -> Tuple[LightCurve, LightCurve, List[bool]]:
    """
    This will produce a flattened copy of the source LightCurve and a further
    LightCurve giving the difference between the source and flattened LC.

    :lc: the source LightCurve
    :eclipse_times: reference central times for the eclipse masks
    :eclipse_durations: eclipse durations for the the eclipse masks
    :orbital_period: the orbital period of the system
    :returns: a tuple in the form (flat_lc, residual_lc, eclipse_mask)
    """
    # Work out the eclipse mask for this sector
    eclipse_mask = lc.create_transit_mask(
        transit_time=[t.nominal_value for t in eclipse_times],
        duration=[t.nominal_value for t in eclipse_durations],
        period=[orbital_period.nominal_value, orbital_period.nominal_value])   
            
    # Flatten the source lc, except the masked time regions, then find the difference 
    flat_lc = lc.flatten(mask=eclipse_mask)
    res_lc = lc - flat_lc

    return (flat_lc, res_lc, eclipse_mask)


def plot_lightcurves_and_mask(lc: LightCurve,
                              flat_lc: LightCurve,
                              residuals_lc: LightCurve,
                              eclipse_mask: any,
                              fig_size: Tuple[float, float]=(8, 6),
                              suptitle: str=None) \
                                    -> Tuple[Figure, Axes]:
    """
    Will create a figure with 3 axes on which it will plot the lc, flat_lc and
    residual_ls in turn. The eclipse mask will be highlighted on each ax.

    :lc: the source LightCurve
    :flat_lc: the flattened equivalent
    :residuals_lc: the difference between the source and flattened LightCurves
    :eclipse_mask: the mask used to exclude eclipses from flattening
    :fig_size: the size of the figure to create
    :suptitle: optional suptitle to give the whole figure
    :returns: a tuple containing the new (figure, axes)
    """
    gridspec_kw = { "height_ratios": [4, 4, 2] }
    fig, axes = plt.subplots(3, 1, sharex="all", figsize=fig_size, 
                             gridspec_kw=gridspec_kw, constrained_layout=True)
    if suptitle:
        fig.suptitle(suptitle)

    # We plot the input LC to the upper ax, the flattened in the middle
    # and the residuals on the lower ax
    lc.scatter(ax=axes[0], marker=".", s=0.5, label=None)
    axes[0].set_xlabel(None)

    flat_lc.scatter(ax=axes[1], marker=".", s=0.5, label=None)
    axes[1].set_xlabel(None)

    residuals_lc.scatter(ax=axes[2], marker=".", s=0.5, label=None)
    axes[2].set_ylabel("Residual")

    # The eclipse masks will be highlighted on all axes. To do this we need
    # the start/end times of each mask. It's a bit tortuous so to doc the algo;
    # clump_masked gets us slices oover each contiguous region of the masked 
    # data then the slices' start/stop can be used as indices to the values.
    mask_slices = np.ma.clump_masked(np.ma.masked_where(eclipse_mask, lc.time.value))
    transform = axes[0].get_xaxis_transform()
    for t1, t4 in ((lc.time[s.start].value, lc.time[s.stop-1].value) for s in mask_slices):
        for ax in axes:
            ax.axvspan(t1, t4, color="lightgray", zorder=-10, transform=transform)

    return fig, axes
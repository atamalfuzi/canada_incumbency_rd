"""Validity checks for the RD: density at the cutoff, placebo cutoffs, balance and whether parties run again.

Writes CSV tables to output/. Run after data.py.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from rddensity import rddensity

import data
from estimate import PERIODS, analysis_sample, major, period, rd_fit

OUTPUT = Path("output")
PLACEBO_CUTOFFS = [-0.20, -0.15, -0.10, -0.075, -0.05, -0.025, 0.025, 0.05, 0.075, 0.10, 0.15, 0.20]
# Each one is fixed before the election whose outcome is being studied.
BALANCE = {"mv_prev2": "Party's margin two elections back", "won_prev2": "Party won two elections back",
           "prev_candidates": "Candidates in last election", "log_prev_valid": "Log valid votes in last election",
           "quebec": "Quebec riding", "ontario": "Ontario riding"}


def density_table(sample):
    """Cattaneo-Jansson-Ma test for each party: pooled, each close race adds one row each side by construction."""
    frame = major(analysis_sample(sample))
    rows = []
    groups = {"Liberal": ["Liberal"], "Conservative": ["Conservative"], "Pooled": ["Liberal", "Conservative"]}
    for group, parties in groups.items():
        for name in ("All years", *PERIODS):
            here = frame[frame["party"].isin(parties)]
            here = here if name == "All years" else period(here, name)
            test = rddensity(X=here["mv_prev"].to_numpy(float))
            rows.append({"group": group, "period": name, "t": test.test["t_jk"], "p": test.test["p_jk"], "h_left": test.h["left"],
                         "h_right": test.h["right"], "n": len(here)})
    return pd.DataFrame(rows)


def placebo_table(sample):
    """RD at false cutoffs, using only rows on the same side of the real cutoff."""
    frame = major(analysis_sample(sample))
    rows = []
    for c in PLACEBO_CUTOFFS:
        side = frame[frame["mv_prev"] > 0] if c > 0 else frame[frame["mv_prev"] < 0]
        rows.append({"cutoff": c, **rd_fit(side, c=c)})
    return pd.DataFrame(rows + [{"cutoff": 0.0, **rd_fit(frame)}]).sort_values("cutoff")


def add_balance_columns(frame):
    frame = frame.copy()
    frame["won_prev2"] = (frame["mv_prev2"] >= 0).astype(float).where(frame["mv_prev2"].notna())
    frame["log_prev_valid"] = np.log(frame["prev_valid"].where(frame["prev_valid"] > 0))
    frame["quebec"] = (frame["province"] == "QUEBEC").astype(float)
    frame["ontario"] = (frame["province"] == "ONTARIO").astype(float)
    return frame


def balance_table(sample):
    frame = add_balance_columns(major(analysis_sample(sample)))
    rows = []
    for name in ("All years", "2011-2025"):
        here = frame if name == "All years" else period(frame, name)
        for column, label in BALANCE.items():
            rows.append({"period": name, "covariate": label, **rd_fit(here, y=column)})
    return pd.DataFrame(rows)


def rerun_table(source):
    """Does a narrow win change whether the party contests the riding again? Ata's party strategic exit question.

    Only ridings with the same name at the next election, and only through 2006: the 2008 margins in
    the source file are wrong for winners.
    """
    main = source[(source["Main election"] == 1) & source["party"].isin(["Liberal", "Conservative"]) & (source["Parliament"] <= 39)].copy()
    main["mv"] = pd.to_numeric(main["MV"], errors="coerce")
    everyone = source[source["Main election"] == 1]
    ridings = set(zip(everyone["Parliament"], everyone["Riding Name"]))
    runs = set(zip(everyone["Parliament"], everyone["Riding Name"], everyone["Combined party"]))
    main = main[[(p + 1, r) in ridings for p, r in zip(main["Parliament"], main["Riding Name"])]]
    main["runs_again"] = [float((p + 1, r, c) in runs) for p, r, c in zip(main["Parliament"], main["Riding Name"], main["Combined party"])]
    main["cluster"] = main["Riding Name"].map(data.normalise_name)
    rows = [{"group": "Liberal and Conservative", **rd_fit(main, y="runs_again", x="mv"), "mean": main["runs_again"].mean()}]
    for party in ("Liberal", "Conservative"):
        here = main[main["party"] == party]
        rows.append({"group": party, **rd_fit(here, y="runs_again", x="mv"), "mean": here["runs_again"].mean()})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    OUTPUT.mkdir(exist_ok=True)
    sample = pd.read_csv("data/sample.csv", low_memory=False)
    tables = {
        "density": density_table(sample),
        "placebo": placebo_table(sample),
        "balance": balance_table(sample),
        "rerun": rerun_table(data.load_source()),
    }
    with pd.option_context("display.width", 200, "display.max_columns", 30, "display.float_format", "{:.4f}".format):
        for name, table in tables.items():
            table.to_csv(OUTPUT / f"{name}.csv", index=False, float_format="%.5f")
            print(f"\n{name}\n{table.to_string()}")

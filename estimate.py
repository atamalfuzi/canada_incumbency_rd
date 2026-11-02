"""Reproduce the 2022 assignment table, then re-estimate with data-driven bandwidths and new elections.

Writes CSV tables to output/. Run after data.py.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from rdrobust import rdrobust

import data

OUTPUT = Path("output")
LEGACY = {"Linear (+/-15%)": (1, 0.15), "Linear (+/-10%)": (1, 0.10), "Cubic": (3, 0.70), "Quartic": (4, 0.70)}
BANDWIDTHS = [0.02, 0.03, 0.04, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70]
PERIODS = {"1872-1949": (2, 21), "1953-2008": (22, 40), "2011-2025": (41, 45)}
LINK_RULES = {"Overlap at least 50%": 0.50, "Overlap at least 75% (main)": 0.75, "Overlap at least 90%": 0.90,
              "Overlap at least 99%": 0.99}


def legacy_ols(frame, degree, h, y="win", x="mv_prev", province="Province", parliament="Parliament", cluster="Riding Name"):
    """Ata's specification: polynomial each side, province and parliament effects, riding clusters."""
    window = frame[frame[x].between(-h, h)].copy()
    window["m"] = window[x]
    window["t"] = (window["m"] >= 0).astype(int)
    terms = ["m"]
    for k in range(2, degree + 1):
        window[f"m{k}"] = window["m"] ** k
        terms.append(f"m{k}")
    formula = f"Q('{y}') ~ t + " + " + ".join(terms + [f"t:{a}" for a in terms]) + f" + C(Q('{province}')) + C(Q('{parliament}'))"
    groups = pd.factorize(window[cluster])[0]
    fit = smf.ols(formula, window).fit(cov_type="cluster", cov_kwds={"groups": groups})
    return {"coef": fit.params["t"], "se": fit.bse["t"], "n": int(fit.nobs)}


def assignment_table(source):
    """The five columns of the 2022 table, on the 1867-2008 file."""
    s = source[(source["Repeat party"] == 1) & source["Combined party"].isin(["Liberal", "Conservative Party of Canada"])]
    lib = s["Combined party"] == "Liberal"
    pre = s["Parliament"] <= 21
    groups = {"Combined": s, "Liberal pre-1950": s[lib & pre], "Liberal post-1950": s[lib & ~pre],
              "Conservative pre-1950": s[~lib & pre], "Conservative post-1950": s[~lib & ~pre]}
    rows = []
    for group, frame in groups.items():
        rows.append({"group": group, "spec": "Mean", "coef": frame["Declared winner"].mean(), "n": len(frame)})
        for spec, (degree, h) in LEGACY.items():
            rows.append({"group": group, "spec": spec, **legacy_ols(frame.assign(win=frame["Declared winner"]), degree, h)})
    return pd.DataFrame(rows)


def rd_fit(frame, y="win", x="mv_prev", c=0.0, h=None, covs=None):
    """Local linear RD with a triangular kernel, riding clusters and a robust bias-corrected interval."""
    use = frame.dropna(subset=[y, x])
    fit = rdrobust(use[y].to_numpy(float), use[x].to_numpy(float), c=c, h=h, cluster=pd.factorize(use["cluster"])[0],
                   covs=None if covs is None else use[covs].to_numpy(float), covs_drop=covs is not None)
    return {"coef": fit.coef.iloc[0, 0], "bias_corrected": fit.coef.iloc[1, 0], "se": fit.se.iloc[0, 0], "ci_low": fit.ci.iloc[2, 0], "ci_high": fit.ci.iloc[2, 1],
            "p_robust": fit.pv.iloc[2, 0], "h": fit.bws.iloc[0, 0], "n_effective": int(sum(fit.N_h)), "n": len(use)}


def analysis_sample(sample, threshold=data.OVERLAP):
    """Riding rows, dropping links below the overlap threshold."""
    return sample[sample["link_overlap"] >= threshold]


def major(sample):
    return sample[sample["party"].isin(["Liberal", "Conservative"])]


def with_dummies(frame):
    dummies = pd.get_dummies(frame[["province", "parliament"]].astype(str), drop_first=True, dtype=float)
    return pd.concat([frame, dummies], axis=1), list(dummies.columns)


def period(frame, name):
    low, high = PERIODS[name]
    return frame[frame["parliament"].between(low, high)]


def main_table(sample):
    """Legacy and data-driven estimates, for the source years and with the new elections."""
    rows = []
    for label, frame in (("1872-2008", major(sample[sample.parliament <= 40])), ("1872-2025", major(analysis_sample(sample)))):
        for spec, (degree, h) in LEGACY.items():
            fit = legacy_ols(frame, degree, h, province="province", parliament="parliament", cluster="cluster")
            rows.append({"sample": label, "spec": spec, **fit})
        rows.append({"sample": label, "spec": "rdrobust, MSE-optimal", **rd_fit(frame)})
        adjusted, covs = with_dummies(frame)
        rows.append({"sample": label, "spec": "rdrobust, province and parliament effects", **rd_fit(adjusted, covs=covs)})
    return pd.DataFrame(rows)


def bandwidth_table(sample):
    """Ata's question: how do the estimates move with the bandwidth?"""
    frame = major(analysis_sample(sample))
    rows = []
    for h in BANDWIDTHS:
        rows.append({"h": h, "method": "rdrobust", **{k: v for k, v in rd_fit(frame, h=h).items() if k != "h"}})
        fit = legacy_ols(frame, 1, h, province="province", parliament="parliament", cluster="cluster")
        rows.append({"h": h, "method": "OLS with effects", **fit, "ci_low": fit["coef"] - 1.96 * fit["se"], "ci_high": fit["coef"] + 1.96 * fit["se"]})
    return pd.DataFrame(rows)


def period_party_table(sample):
    """Estimates by period and party, with the difference against the 1953-2008 period."""
    frame = analysis_sample(sample)
    rows = []
    groups = {"Liberal and Conservative": ["Liberal", "Conservative"], "Liberal": ["Liberal"], "Conservative": ["Conservative"],
              "NDP": ["NDP"], "Bloc": ["Bloc"]}
    for group, parties in groups.items():
        for name in PERIODS:
            here = period(frame[frame["party"].isin(parties)], name)
            # NDP and CCF before 1950, and the Bloc before 1993, are too few to estimate.
            if here["win"].sum() < 50:
                continue
            rows.append({"group": group, "period": name, **rd_fit(here), "mean": here["win"].mean()})
    table = pd.DataFrame(rows)
    reference = table[table["period"] == "1953-2008"].set_index("group")
    table["change_from_1953_2008"] = table["coef"] - table["group"].map(reference["coef"])
    gap_se = np.sqrt(table["se"] ** 2 + table["group"].map(reference["se"]) ** 2)
    table["change_se"] = gap_se.where(table["period"] != "1953-2008")
    return table


def era_table(sample):
    """Estimates in roughly equal blocks of parliaments, for the figure."""
    frame = major(analysis_sample(sample))
    eras = {"1872-1904": (2, 10), "1908-1930": (11, 17), "1935-1958": (18, 24), "1962-1972": (25, 29), "1974-1993": (30, 35),
            "1997-2008": (36, 40), "2011-2025": (41, 45)}
    return pd.DataFrame([{"era": era, **rd_fit(frame[frame["parliament"].between(*span)])} for era, span in eras.items()])


def election_table(sample):
    """Estimates at each election since 2011, with Liberals and Conservatives pooled."""
    frame = major(analysis_sample(sample))
    return pd.DataFrame([{"year": year, **rd_fit(frame[frame["year"] == year], h=0.15), "linked_rows": int((frame["year"] == year).sum())}
                         for year in (2011, 2015, 2019, 2021, 2025)])


def link_table(sample, notional):
    """The 2011-2025 estimate under each way of handling the two redistributions."""
    modern = major(sample[sample.parliament >= 41])
    rows = [{"rule": rule, **rd_fit(modern[modern["link_overlap"] >= threshold])} for rule, threshold in LINK_RULES.items()]
    rows.append({"rule": "Same map only: 2011, 2019, 2021", **rd_fit(modern[modern["year"].isin([2011, 2019, 2021])])})
    pooled = pd.concat([modern[modern["year"].isin([2011, 2019, 2021])], major(notional)], ignore_index=True)
    rows.append({"rule": "Transposed margins, every riding", **rd_fit(pooled)})
    return pd.DataFrame(rows)


def bins_table(sample, width=0.01, reach=0.25):
    """Win rate in 1-point margin bins, the only part of the riding data the figures need."""
    frame = major(analysis_sample(sample)).dropna(subset=["mv_prev"])
    frame = frame[frame["mv_prev"].abs() <= reach]
    groups = {"1872-2025": frame, "2011-2025": period(frame, "2011-2025")}
    rows = []
    for label, here in groups.items():
        lower = np.floor(here["mv_prev"] / width) * width
        table = here.groupby(lower.round(4))["win"].agg(["mean", "size"]).reset_index()
        rows.append(table.set_axis(["bin_left", "win_rate", "n"], axis=1).assign(sample=label))
    return pd.concat(rows, ignore_index=True)


def margin_table(official):
    """Ata's alternative margin: votes over eligible voters instead of votes over votes cast."""
    frame = major(official[(official["link_overlap"] >= data.OVERLAP)].dropna(subset=["mv_eligible"]))
    rows = []
    for label, column in (("Share of votes cast", "mv_prev"), ("Share of eligible voters", "mv_eligible")):
        rows.append({"margin": label, **rd_fit(frame, x=column)})
    for label, h_cast in (("Votes cast, h = 10 points", 0.10), ("Votes cast, h = 5 points", 0.05)):
        rows.append({"margin": label, **rd_fit(frame, x="mv_prev", h=h_cast)})
    for label, h_eligible in (("Eligible voters, h = 6.5 points", 0.065), ("Eligible voters, h = 3.25 points", 0.0325)):
        rows.append({"margin": label, **rd_fit(frame, x="mv_eligible", h=h_eligible)})
    turnout = frame["prev_valid"] / frame["prev_electors"]
    high = turnout >= turnout.median()
    rows.append({"margin": "Votes cast, turnout above median", **rd_fit(frame[high])})
    rows.append({"margin": "Votes cast, turnout below median", **rd_fit(frame[~high])})
    table = pd.DataFrame(rows)
    table["median_turnout"] = turnout.median()
    return table


if __name__ == "__main__":
    OUTPUT.mkdir(exist_ok=True)
    sample = pd.read_csv("data/sample.csv", low_memory=False)
    official = pd.read_csv("data/official.csv", low_memory=False)
    notional = pd.read_csv("data/notional.csv", low_memory=False)
    tables = {
        "assignment_table": assignment_table(data.load_source()),
        "rd_bins": bins_table(sample),
        "main": main_table(sample),
        "bandwidth": bandwidth_table(sample),
        "period_party": period_party_table(sample),
        "eras": era_table(sample),
        "elections": election_table(sample),
        "link_rules": link_table(sample, notional),
        "margin_definition": margin_table(official),
    }
    with pd.option_context("display.width", 200, "display.max_columns", 30, "display.float_format", "{:.4f}".format):
        for name, table in tables.items():
            table.to_csv(OUTPUT / f"{name}.csv", index=False, float_format="%.5f")
            print(f"\n{name}\n{table.to_string()}")

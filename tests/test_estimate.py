"""The 2022 table and the estimators. CI has no 1867-2008 file, so it checks the committed output;
with the file in place, the table is re-run from it."""
import numpy as np
import pandas as pd
import pytest

import data
from checks import add_balance_columns
from estimate import assignment_table, legacy_ols, rd_fit

# Results.pdf from the 2022 assignment: coefficient and standard error for each cell, then N.
ATA = {
    ("Combined", "Linear (+/-15%)"): (0.112, 0.0322, 6465),
    ("Combined", "Linear (+/-10%)"): (0.0941, 0.0376, 4742),
    ("Combined", "Cubic"): (0.0942, 0.0326, 13195),
    ("Combined", "Quartic"): (0.102, 0.0393, 13195),
    ("Liberal pre-1950", "Linear (+/-15%)"): (0.136, 0.0438, 1627),
    ("Liberal pre-1950", "Linear (+/-10%)"): (0.112, 0.0506, 1242),
    ("Liberal pre-1950", "Cubic"): (0.110, 0.0475, 2425),
    ("Liberal pre-1950", "Quartic"): (0.130, 0.0574, 2425),
    ("Liberal post-1950", "Linear (+/-15%)"): (0.108, 0.0371, 1886),
    ("Liberal post-1950", "Linear (+/-10%)"): (0.0697, 0.0443, 1337),
    ("Liberal post-1950", "Cubic"): (0.0868, 0.0384, 4406),
    ("Liberal post-1950", "Quartic"): (0.0862, 0.0456, 4406),
    ("Conservative pre-1950", "Linear (+/-15%)"): (0.0889, 0.0472, 1369),
    ("Conservative pre-1950", "Linear (+/-10%)"): (0.0873, 0.0574, 1059),
    ("Conservative pre-1950", "Cubic"): (0.0762, 0.0495, 2016),
    ("Conservative pre-1950", "Quartic"): (0.0929, 0.0622, 2016),
    ("Conservative post-1950", "Linear (+/-15%)"): (0.106, 0.0359, 1583),
    ("Conservative post-1950", "Linear (+/-10%)"): (0.0699, 0.0431, 1104),
    ("Conservative post-1950", "Cubic"): (0.0827, 0.0388, 4348),
    ("Conservative post-1950", "Quartic"): (0.0954, 0.0451, 4348),
}
MEANS = {"Combined": 0.456, "Liberal pre-1950": 0.612, "Liberal post-1950": 0.430, "Conservative pre-1950": 0.479, "Conservative post-1950": 0.378}


def check_against_assignment(table):
    table = table.set_index(["group", "spec"])
    for cell, (coef, se, n) in ATA.items():
        assert table.loc[cell, "coef"] == pytest.approx(coef, abs=0.0006), cell
        assert table.loc[cell, "se"] == pytest.approx(se, abs=0.00006), cell
        assert table.loc[cell, "n"] == n, cell
    for group, mean in MEANS.items():
        assert table.loc[(group, "Mean"), "coef"] == pytest.approx(mean, abs=0.0006), group


def test_committed_table_matches_the_2022_results():
    check_against_assignment(pd.read_csv("output/assignment_table.csv"))


@pytest.mark.skipif(not data.SOURCE_FILE.exists(), reason="the 1867-2008 file isn't redistributable")
def test_table_rebuilt_from_the_source_file_matches_the_2022_results():
    check_against_assignment(assignment_table(data.load_source()))


def made_up(jump, n=20000, seed=1):
    """Win probability with a known jump at zero and a slope either side."""
    rng = np.random.default_rng(seed)
    margin = rng.uniform(-0.7, 0.7, n)
    chance = np.clip(0.4 + 0.5 * margin + jump * (margin >= 0), 0, 1)
    return pd.DataFrame({
        "win": (rng.uniform(size=n) < chance).astype(float), "mv_prev": margin, "cluster": rng.integers(0, 300, n).astype(str),
        "Province": rng.choice(["ON", "QC", "BC"], n), "Parliament": rng.integers(1, 5, n), "Riding Name": rng.integers(0, 300, n).astype(str)})


@pytest.mark.parametrize("jump", [0.0, 0.2])
def test_rd_fit_recovers_a_known_jump(jump):
    fit = rd_fit(made_up(jump, n=60000))
    assert abs(fit["coef"] - jump) < 3 * fit["se"]
    assert fit["ci_low"] < jump < fit["ci_high"]


@pytest.mark.parametrize("degree,h", [(1, 0.15), (3, 0.7), (4, 0.7)])
def test_legacy_ols_recovers_a_known_jump(degree, h):
    frame = made_up(0.2)
    fit = legacy_ols(frame, degree, h)
    assert abs(fit["coef"] - 0.2) < 3 * fit["se"]
    assert fit["n"] == (frame["mv_prev"].abs() <= h).sum()


def test_won_two_elections_back_stays_missing_when_the_margin_is():
    frame = pd.DataFrame({"mv_prev2": [0.1, -0.1, np.nan], "prev_valid": [10, 0, 5], "province": ["QUEBEC", "ONTARIO", "YUKON"]})
    out = add_balance_columns(frame)
    assert out["won_prev2"].iloc[:2].tolist() == [1.0, 0.0] and np.isnan(out["won_prev2"].iloc[2])
    assert np.isnan(out["log_prev_valid"].iloc[1])
    assert out["quebec"].tolist() == [1.0, 0.0, 0.0]

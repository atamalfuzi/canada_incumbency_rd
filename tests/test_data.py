"""Parsing, margins and riding links. Most use made-up rows and need no downloads."""
from pathlib import Path

import pandas as pd
import pytest

import data


def test_parse_party_reads_each_table_format():
    assert data.parse_party("Scott Andrews ** Liberal/Libéral") == "Liberal"
    assert data.parse_party("Rick Dalton Conservative/conservateur") == "Conservative"
    assert data.parse_party("Dennis Bevington N.D.P./N.P.D.") == "NDP"
    assert data.parse_party("Lori Idlout NDP-New Democratic Party/NPD-Nouveau Parti démocratique") == "NDP"
    assert data.parse_party("A B Bloc Québécois/Bloc Québécois") == "Bloc"
    assert data.parse_party("A B Green Party/Parti Vert") == "Green"
    assert data.parse_party("Scott Andrews ** No Affiliation/Aucune appartenance") == "Other"


def test_parse_surname_stops_at_the_party():
    assert data.parse_surname("Scott Andrews ** Liberal/Libéral") == "ANDREWS"
    assert data.parse_surname("Ryan Cleary NDP-New Democratic Party/NPD-Nouveau Parti démocratique") == "CLEARY"
    assert data.parse_surname("Fabian Manning Conservative/Conservateur") == "MANNING"


def test_normalise_name_ignores_accents_and_dashes():
    assert data.normalise_name("Abitibi--Témiscamingue") == data.normalise_name("ABITIBI - TEMISCAMINGUE")


def test_margins_compare_winner_with_second_and_others_with_winner():
    frame = pd.DataFrame({"id": [1, 1, 1, 2, 2], "votes": [50, 30, 20, 60, 40]})
    assert data.margins(frame, ["id"]).round(6).tolist() == [0.2, -0.2, -0.3, 0.2, -0.2]


def test_margins_give_tied_leaders_zero():
    frame = pd.DataFrame({"id": [1, 1, 1], "votes": [40, 40, 20]})
    assert data.margins(frame, ["id"]).round(6).tolist() == [0.0, 0.0, -0.2]


def test_link_flows_takes_the_smaller_share_and_the_best_match():
    flows = pd.DataFrame({"fed": [1, 1, 2], "old_fed": [10, 20, 20], "weight": [90.0, 10.0, 90.0]})
    best = data.link_flows(flows).set_index("fed")
    assert best.loc[1, "old_fed"] == 10 and best.loc[2, "old_fed"] == 20
    assert best.loc[1, "overlap"] == pytest.approx(0.9)
    assert best.loc[2, "share_new"] == pytest.approx(1.0)
    assert best.loc[2, "overlap"] == pytest.approx(0.9)


def test_committed_links_cover_every_riding_and_match_once():
    links = pd.read_csv("output/riding_links.csv")
    assert links.groupby("year").size().to_dict() == {2015: 338, 2025: 343}
    strict = links[links["overlap"] > 0.5]
    assert not strict.duplicated(["year", "old_fed"]).any()
    counts = pd.read_csv("output/link_counts.csv").set_index("year")
    assert counts.loc[2015, "overlap_75"] == 217 and counts.loc[2025, "overlap_75"] == 283


def test_committed_links_agree_with_official_checks():
    checks = pd.read_csv("output/link_checks.csv").set_index("check")["value"]
    assert checks["2025: correlation of electors with official transposed electors"] > 0.99
    assert checks["2025: officially unchanged ridings found by name"] == len(data.UNCHANGED_2023)
    assert checks["2025: lowest overlap among them"] == pytest.approx(1.0)
    for year in (2015, 2025):
        shown = checks[f"{year}: linked ridings, no by-election, with a sitting MP running"]
        assert checks[f"{year}: of them, sitting MP has the surname of the predecessor's last winner"] / shown > 0.95


needs_source = pytest.mark.skipif(not data.SOURCE_FILE.exists(), reason="the 1867-2008 file isn't redistributable")
needs_raw = pytest.mark.skipif(not (data.RAW / "t12_2006.csv").exists(), reason="run data.py first")


@needs_source
@needs_raw
@pytest.mark.parametrize("year,parliament", [(2004, 38), (2006, 39)])
def test_rebuilt_margins_match_the_source_file(year, parliament):
    source = data.load_source()
    rows = source[(source["Parliament"] == parliament) & (source["Main election"] == 1)]
    rows = rows.assign(key=rows["Riding Name"].map(data.normalise_name), mv=pd.to_numeric(rows["MV"], errors="coerce"))
    theirs = rows.groupby("key")["mv"].max()
    ours = data.load_candidates(year).groupby("key")["mv"].max()
    assert theirs.index.sort_values().tolist() == ours.index.sort_values().tolist()
    assert (theirs - ours).abs().max() < 1e-6


@needs_source
@needs_raw
def test_source_file_2008_winner_margins_are_against_third_place():
    """Documented in the README. It doesn't reach Ata's numbers: the sample ends with margins from 2006."""
    source = data.load_source()
    rows = source[(source["Parliament"] == 40) & (source["Declared winner"] == 1)]
    rows = rows.assign(key=rows["Riding Name"].map(data.normalise_name), mv=pd.to_numeric(rows["MV"], errors="coerce")).set_index("key")["mv"]
    official = data.load_candidates(2008)
    official = official[official["won"] == 1].set_index("key")["mv"]
    assert ((rows - official).abs() > 1e-6).sum() == 159

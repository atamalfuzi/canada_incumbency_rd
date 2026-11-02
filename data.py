"""Download official results, link ridings across redistributions and build the analysis samples.

Writes data/sample.csv, data/official.csv and data/notional.csv (gitignored), plus
output/riding_links.csv and output/link_checks.csv (committed). The 1867-2008 file isn't
redistributable, so it is read from data/original_elections.csv or the path in ORIGINAL_ELECTIONS.
"""
import os
import re
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw")
OUTPUT = Path("output")
SOURCE_FILE = Path(os.environ.get("ORIGINAL_ELECTIONS", "data/original_elections.csv"))
EC = "https://www.elections.ca"
MAPS = "https://ftp.maps.canada.ca/pub/elections_elections/Electoral-districts_Circonscription-electorale"
# Election year -> parliament number and location of Elections Canada's raw tables.
ELECTIONS = {
    2004: (38, "scripts/OVR2004/23/data/table{}.csv"),
    2006: (39, "scripts/OVR2006/25/data_donnees/table_tableau{}.csv"),
    2008: (40, "scripts/OVR2008/31/data/table_tableau{}.csv"),
    2011: (41, "scripts/OVR2011/34/data_donnees/table_tableau{}.csv"),
    2015: (42, "res/rep/off/ovr2015app/41/data_donnees/table_tableau{}.csv"),
    2019: (43, "res/rep/off/ovr2019app/51/data_donnees/table_tableau{}.csv"),
    2021: (44, "res/rep/off/ovr2021app/53/data_donnees/table_tableau{}.csv"),
    2025: (45, "res/rep/off/ovrGE45/62/data_donnees/table_tableau{}.csv"),
}
OTHER_FILES = {
    "trans_2013.csv": f"{EC}/res/cir/trans2013/downloads/TRANSPOSITION_338FED.csv",
    "trans_2023.csv": f"{EC}/res/rep/tra/2023rep/csv/Transposition_343_FED_Vote_Count.csv",
    "poll_2021.zip": f"{EC}/res/rep/off/ovr2021app/53/data_donnees/pollresults_resultatsbureauCanada.zip",
    "PD_CA_2021_EN.zip": f"{MAPS}/Elections_Canada_2021/PD_CA_2021_EN.zip",
    "FED_2023.zip": f"{EC}/res/cir/mapsCorner/edb/FederalElectoralDistricts_SHP.zip",
}
# Previous general election. 2015 and 2025 follow a redistribution; other pairs share a map.
PREVIOUS = {2006: 2004, 2008: 2006, 2011: 2008, 2015: 2011, 2019: 2015, 2021: 2019, 2025: 2021}
# The 2004 and 2006 tables have no riding numbers, so those pairs link on the exact name.
BY_NAME = {2006, 2008}
OVERLAP = 0.75
PARTIES = ["Conservative", "NDP", "Liberal", "Bloc", "Green", "Other"]
AFFILIATION = {
    "Conservative": r"(?i)Conservative/Conservateur$",
    "NDP": r"(NDP-New Democratic Party|N\.D\.P\.)/.*$",
    "Liberal": r"Liberal/Lib.{1,2}ral$",
    "Bloc": r"Bloc Qu.{1,2}b.{1,2}cois/.*$",
    "Green": r"Green Party/.*$",
}
PARTY_PREFIX = {"Conservative": "Conservative", "NDP": "NDP", "New Democratic": "NDP", "Liberal": "Liberal",
                "Bloc Qu": "Bloc", "Green": "Green"}
SOURCE_PARTY = {"Liberal": "Liberal", "Conservative Party of Canada": "Conservative", "New Democratic Party": "NDP",
                "Green Party of Canada": "Green"}
# Elections Canada's list of past by-elections, by the general election that followed.
# Those cancelled by a general election call are left out.
BY_ELECTIONS = {
    2006: ["Labrador"],
    2008: ["Repentigny", "London North Centre", "Outremont", "Roberval--Lac-Saint-Jean", "Saint-Hyacinthe--Bagot",
           "Desnethé--Missinippi--Churchill River", "Vancouver Quadra", "Toronto Centre", "Willowdale"],
    2011: ["Cumberland--Colchester--Musquodoboit Valley", "Hochelaga",
           "Montmagny--L'Islet--Kamouraska--Rivière-du-Loup", "New Westminster--Coquitlam",
           "Dauphin--Swan River--Marquette", "Vaughan", "Winnipeg North"],
    2015: ["Toronto--Danforth", "Calgary Centre", "Durham", "Victoria", "Labrador", "Bourassa",
           "Brandon--Souris", "Provencher", "Toronto Centre", "Scarborough--Agincourt",
           "Trinity--Spadina", "Fort McMurray--Athabasca", "Macleod", "Whitby--Oshawa", "Yellowhead"],
    2019: ["Medicine Hat--Cardston--Warner", "Calgary Heritage", "Calgary Midnapore",
           "Markham--Thornhill", "Ottawa--Vanier", "Saint-Laurent", "Lac-Saint-Jean",
           "Sturgeon River--Parkland", "Bonavista--Burin--Trinity", "Scarborough--Agincourt",
           "Battlefords--Lloydminster", "South Surrey--White Rock", "Chicoutimi--Le Fjord",
           "Leeds--Grenville--Thousand Islands and Rideau Lakes", "York--Simcoe", "Burnaby South",
           "Outremont", "Nanaimo--Ladysmith"],
    2021: ["Toronto Centre", "York Centre"],
    2025: ["Mississauga--Lakeshore", "Notre-Dame-de-Grâce--Westmount", "Oxford",
           "Winnipeg South Centre", "Portage--Lisgar", "Calgary Heritage", "Durham",
           "Toronto--St. Paul's", "LaSalle--Émard--Verdun", "Elmwood--Transcona",
           "Cloverdale--Langley City"],
}
# Appendix A of the 2023 transposition report, boundaries unchanged from the 2013 order. Five more
# are in the appendix under new names and can't be checked by name.
UNCHANGED_2023 = [
    "Labrador", "Cumberland--Colchester", "Abitibi--Baie-James--Nunavik--Eeyou", "Abitibi--Témiscamingue", "Beauce",
    "Bourassa", "Brome--Missisquoi", "Brossard--Saint-Lambert", "Drummond", "La Pointe-de-l'Île", "Lac-Saint-Louis",
    "Laval--Les Îles", "Longueuil--Charles-LeMoyne", "Longueuil--Saint-Hubert", "Marc-Aurèle-Fortin", "Papineau",
    "Pierre-Boucher--Les Patriotes--Verchères", "Pierrefonds--Dollard", "Richmond--Arthabaska",
    "Rosemont--La Petite-Patrie", "Saint-Jean", "Saint-Maurice--Champlain", "Shefford", "Trois-Rivières", "Ajax",
    "Bruce--Grey--Owen Sound", "Burlington", "Eglinton--Lawrence", "Haldimand--Norfolk", "Humber River--Black Creek",
    "Huron--Bruce", "Kitchener South--Hespeler", "Oshawa", "Perth--Wellington", "Willowdale", "York Centre",
    "Lethbridge", "Skeena--Bulkley Valley", "Vancouver East", "Victoria", "Yukon", "Northwest Territories", "Nunavut",
]


def download():
    """Fetch each official file once."""
    RAW.mkdir(parents=True, exist_ok=True)
    files = dict(OTHER_FILES)
    for year, (_, pattern) in ELECTIONS.items():
        files[f"t11_{year}.csv"] = f"{EC}/{pattern.format(11)}"
        files[f"t12_{year}.csv"] = f"{EC}/{pattern.format(12)}"
    for name, url in files.items():
        if not (RAW / name).exists():
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=600) as response:
                (RAW / name).write_bytes(response.read())


def read_table(path, **kwargs):
    """Elections Canada's files are UTF-8 from 2015 and Latin-1 before."""
    try:
        return pd.read_csv(path, encoding="utf-8-sig", **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", **kwargs)


def normalise_name(name):
    """Upper case letters and digits only, so spellings of a riding across files compare equal."""
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def parse_party(candidate):
    """Party group from Table 12's 'Name [**] Party/Parti' string."""
    for party, pattern in AFFILIATION.items():
        if re.search(pattern, candidate):
            return party
    return "Other"


def group_party(name):
    """Party group from a plain affiliation name, as in the poll and transposition files."""
    return next((party for start, party in PARTY_PREFIX.items() if str(name).startswith(start)), "Other")


def parse_surname(candidate):
    """Last word of the candidate's name, in Table 12's 'First Last [**] Party/Parti' string."""
    name = re.split(r"\s\*\*|\s(?:NDP-|N\.D\.P\.|Bloc |Green Party|Forces |People|No Affiliation|Independent|Liberal/|Conservative/|Conservative |Marxist|Christian|Libertarian|Rhino|Communist|PACT|Animal|Canadian|United|Progressive)", candidate)[0]
    return normalise_name(name.split()[-1])


def margins(frame, by):
    """Own vote share minus that of the best other candidate in the riding, as in the source file."""
    votes = frame.groupby(by)["votes"]
    top = votes.transform("max")
    second = votes.transform(lambda v: np.sort(v.to_numpy())[-2] if len(v) > 1 else 0)
    best_other = second.where(frame["votes"].eq(top), top)
    return (frame["votes"] - best_other) / votes.transform("sum")


def load_candidates(year):
    t = read_table(RAW / f"t12_{year}.csv", dtype=str)
    has_number = "Number" in " ".join(t.columns)
    columns = ["province", "riding", "fed", "candidate", "residence", "occupation", "votes", "pct", "majority", "majority_pct"]
    t.columns = columns if has_number else [c for c in columns if c != "fed"]
    t = t[pd.to_numeric(t["votes"].str.replace(",", ""), errors="coerce").notna()].copy()
    t["riding"] = t["riding"].str.split("/").str[0]
    t["key"] = t["riding"].map(normalise_name)
    t["id"] = t["fed"].astype(int) if has_number else t["key"]
    t["votes"] = pd.to_numeric(t["votes"].str.replace(",", ""))
    t["party"] = t["candidate"].map(parse_party)
    t["province"] = t["province"].str.split("/").str[0].str.strip().map(normalise_name)
    t["year"] = year
    t["parliament"] = ELECTIONS[year][0]
    t["mv"] = margins(t, ["id"])
    t["won"] = t["mv"].gt(0).astype(int)
    t["n_candidates"] = t.groupby("id")["votes"].transform("size")
    t["valid_votes"] = t.groupby("id")["votes"].transform("sum")
    t["sitting"] = t["candidate"].str.contains(r"\*\*", regex=True)
    t["surname"] = t["candidate"].map(parse_surname)
    electors = read_table(RAW / f"t11_{year}.csv", dtype=str)
    electors = electors.iloc[:, [2, 4] if has_number else [1, 3]].set_axis(["id", "electors"], axis=1)
    electors["electors"] = pd.to_numeric(electors["electors"].str.replace(",", ""), errors="coerce")
    electors = electors.dropna(subset=["electors"])
    electors["id"] = electors["id"].astype(int) if has_number else electors["id"].str.split("/").str[0].map(normalise_name)
    t = t.merge(electors, on="id", how="left", validate="m:1")
    return t[["year", "parliament", "province", "id", "key", "riding", "party", "surname", "votes", "mv", "won", "sitting",
              "n_candidates", "valid_votes", "electors"]]


def link_flows(flows):
    """Each new riding's best-matched old riding, from a table of voters moved between them.

    overlap is the smaller of two shares: the new riding's voters who came from the old riding, and
    the old riding's voters who went to the new one. Above 0.5 no old riding can match twice.
    """
    flows = flows.copy()
    flows["share_new"] = flows["weight"] / flows.groupby("fed")["weight"].transform("sum")
    flows["share_old"] = flows["weight"] / flows.groupby("old_fed")["weight"].transform("sum")
    flows["overlap"] = flows[["share_new", "share_old"]].min(axis=1)
    best = flows.sort_values("overlap", ascending=False).groupby("fed", as_index=False).head(1)
    return best[["fed", "old_fed", "share_new", "share_old", "overlap"]].sort_values("fed")


def read_transposition_2013():
    t = pd.read_csv(RAW / "trans_2013.csv", skiprows=4, encoding="latin-1", low_memory=False)
    t.columns = ["prov", "fed", "riding", "old_fed", "old_riding", "new_pop", "old_pop", "pop_moved", "type", "pct",
                 "first", "last", "polls", "electors", "weight", *PARTIES]
    t = t[pd.to_numeric(t["fed"], errors="coerce").notna() & pd.to_numeric(t["old_fed"], errors="coerce").notna()]
    return t.astype({"fed": int, "old_fed": int})


def read_transposition_2023():
    """2021 votes on the 2023 map by party group, plus elector counts."""
    t = read_table(RAW / "trans_2023.csv")
    meta = {"PROV_ID", "PROV_NAME", "FED_NUM", "FED_FR", "FED_EN", "Rejected_Ballots", "Transposed_Votes",
            "Registered_Electors", "Estimated_Turnout"}
    votes = pd.DataFrame(0.0, index=t["FED_NUM"].astype(int), columns=PARTIES)
    for column in t.columns.difference(list(meta), sort=False):
        votes[group_party(column)] += pd.to_numeric(t[column], errors="coerce").fillna(0).to_numpy()
    votes["electors"] = pd.to_numeric(t["Registered_Electors"]).to_numpy()
    return votes


def polls_2021():
    """Votes by party group and electors at each 2021 ordinary poll, by riding and poll number."""
    with zipfile.ZipFile(RAW / "poll_2021.zip") as archive:
        frames = [pd.read_csv(archive.open(m), encoding="utf-8-sig", dtype=str, usecols=[0, 3, 9, 13, 17]) for m in archive.namelist()]
    p = pd.concat(frames).set_axis(["old_fed", "poll", "electors", "party", "votes"], axis=1)
    # Numbers like "12A" and "12-1" are parts of poll 12; "S/R 1" is special voting and has no area.
    p["pd_num"] = pd.to_numeric(p["poll"].str.extract(r"^\s*(\d+)", expand=False))
    p = p.dropna(subset=["pd_num"]).astype({"old_fed": int, "pd_num": int})
    p["electors"] = pd.to_numeric(p["electors"])
    p["votes"] = pd.to_numeric(p["votes"])
    p["group"] = p["party"].map(group_party)
    electors = p.drop_duplicates(["old_fed", "poll"]).groupby(["old_fed", "pd_num"])["electors"].sum()
    votes = p.pivot_table(index=["old_fed", "pd_num"], columns="group", values="votes", aggfunc="sum", fill_value=0)
    return votes.reindex(columns=PARTIES, fill_value=0).join(electors).reset_index()


def flows_2023():
    """2021 polls placed on the 2023 map: each poll goes to the riding holding its largest part.

    Polls cut by a new boundary go whole to one side. check_links() measures the error this leaves.
    """
    import geopandas as gpd

    polls = gpd.read_file(f"zip://{RAW / 'PD_CA_2021_EN.zip'}", columns=["FED_NUM", "PD_NUM"])
    polls = polls.explode(index_parts=False)
    polls["area"] = polls.geometry.area
    polls = polls.sort_values("area", ascending=False).drop_duplicates(["FED_NUM", "PD_NUM"])
    polls["geometry"] = polls.geometry.representative_point()
    feds = gpd.read_file(f"zip://{RAW / 'FED_2023.zip'}!FederalElectoralDistricts_SHP/ED_CF.shp")[["ED_CF_NUM", "geometry"]]
    placed = gpd.sjoin_nearest(polls.to_crs(feds.crs), feds, how="left").drop_duplicates(["FED_NUM", "PD_NUM"])
    placed = pd.DataFrame(placed[["FED_NUM", "PD_NUM", "ED_CF_NUM"]]).set_axis(["old_fed", "pd_num", "fed"], axis=1)
    placed = placed.astype({"old_fed": int, "pd_num": int, "fed": int})
    return polls_2021().merge(placed, on=["old_fed", "pd_num"], how="inner")


def build_links(candidates):
    """One row per new riding at each redistribution, with its predecessor and how much carried over."""
    t2013 = read_transposition_2013()
    links_2015 = link_flows(t2013.groupby(["fed", "old_fed"], as_index=False)["weight"].sum())
    links_2015["year"], links_2015["source"] = 2015, "official transposition, 2011 votes"
    moved = flows_2023()
    links_2025 = link_flows(moved.groupby(["fed", "old_fed"], as_index=False)["electors"].sum().rename(columns={"electors": "weight"}))
    links_2025["year"], links_2025["source"] = 2025, "2021 polls placed on 2023 map, electors"
    links = pd.concat([links_2015, links_2025], ignore_index=True)
    for year in (2015, 2025):
        here = links["year"] == year
        names = candidates[candidates.year == year].drop_duplicates("id").set_index("id")["riding"]
        old_names = candidates[candidates.year == PREVIOUS[year]].drop_duplicates("id").set_index("id")["riding"]
        links.loc[here, "riding"] = links.loc[here, "fed"].astype(object).map(names)
        links.loc[here, "old_riding"] = links.loc[here, "old_fed"].astype(object).map(old_names)
    return links[["year", "fed", "riding", "old_fed", "old_riding", "share_new", "share_old", "overlap", "source"]], moved


def check_links(links, moved, candidates):
    """Compare the rebuilt 2023 flows with official totals, and links with who the sitting MP was."""
    official = read_transposition_2023()
    votes = moved.groupby("fed")[PARTIES].sum()
    official_votes, votes = official[PARTIES].align(votes, join="inner", axis=0)
    gap = (official_votes.div(official_votes.sum(axis=1), axis=0) - votes.div(votes.sum(axis=1), axis=0)).abs().max(axis=1)
    electors = moved.groupby("fed")["electors"].sum().reindex(official.index)
    linked = links[(links.year == 2025) & (links.overlap >= OVERLAP)]["fed"]
    rows = {
        "2025: ridings rebuilt from polls": len(votes),
        "2025: correlation of electors with official transposed electors": electors.corr(official["electors"]),
        "2025: median gap in electors, share of official": ((electors - official["electors"]).abs() / official["electors"]).median(),
        "2025: median largest party share gap, rebuilt against official": gap.median(),
        "2025: 90th percentile largest party share gap": gap.quantile(0.9),
        "2025: median largest party share gap, linked ridings": gap.reindex(linked).median(),
    }
    unchanged = links[(links.year == 2025) & links["riding"].map(normalise_name).isin([normalise_name(n) for n in UNCHANGED_2023])]
    rows["2025: officially unchanged ridings found by name"] = len(unchanged)
    rows["2025: lowest overlap among them"] = unchanged["overlap"].min()
    rows["2025: of them, predecessor has same name"] = (unchanged["riding"].map(normalise_name) == unchanged["old_riding"].map(normalise_name)).sum()
    for year in (2015, 2025):
        here = links[(links.year == year) & (links.overlap >= OVERLAP)]
        new = candidates[(candidates.year == year) & candidates["sitting"]][["id", "surname"]].rename(columns={"id": "fed", "surname": "sitting"})
        old = candidates[(candidates.year == PREVIOUS[year]) & (candidates.won == 1)][["id", "surname"]].rename(columns={"id": "old_fed", "surname": "winner"})
        here = here[~here["old_fed"].isin(excluded_by_election(candidates, year))]
        both = here.astype({"fed": object, "old_fed": object}).merge(new, on="fed").merge(old, on="old_fed")
        rows[f"{year}: linked ridings, no by-election, with a sitting MP running"] = len(both)
        rows[f"{year}: of them, sitting MP has the surname of the predecessor's last winner"] = (both["sitting"] == both["winner"]).sum()
    return pd.Series(rows, name="value").rename_axis("check").reset_index()


def excluded_by_election(candidates, year):
    """Riding ids in the previous election that had a by-election before this general election."""
    table = candidates[candidates.year == PREVIOUS[year]].drop_duplicates("key")
    lookup = dict(zip(table["key"], table["key"] if year in BY_NAME else table["id"]))
    return {lookup[normalise_name(name)] for name in BY_ELECTIONS[year]}


def build_sample(candidates, links):
    """Party rows from official tables, with the party's margin in the riding at the last election.

    Every link is kept with its overlap, so the analysis can apply any threshold.
    """
    frames = []
    clusters = {}
    for year, previous in PREVIOUS.items():
        now = candidates[(candidates.year == year) & (candidates.party != "Other")].copy()
        before = candidates[(candidates.year == previous) & (candidates.party != "Other")]
        if year in BY_NAME:
            now["prev_id"], right = now["key"], before.assign(prev_id=before["key"])
            now["link_overlap"] = 1.0
        elif year in (2015, 2025):
            link = links[links.year == year].astype({"fed": object}).set_index("fed")
            now["prev_id"] = now["id"].map(link["old_fed"]).astype(object)
            now["link_overlap"] = now["id"].map(link["overlap"]).astype(float)
            right = before.assign(prev_id=before["id"].astype(object))
        else:
            now["prev_id"], right = now["id"], before.assign(prev_id=before["id"])
            now["link_overlap"] = 1.0
        now = now[~now["prev_id"].isin(excluded_by_election(candidates, year))]
        lag = right[["prev_id", "party", "mv", "n_candidates", "valid_votes", "electors", "key"]].rename(columns={
            "mv": "mv_prev", "n_candidates": "prev_candidates", "valid_votes": "prev_valid",
            "electors": "prev_electors", "key": "prev_key"})
        merged = now.merge(lag, on=["prev_id", "party"], how="inner", validate="m:1")
        merged["mv_eligible"] = merged["mv_prev"] * merged["prev_valid"] / merged["prev_electors"]
        # A linked riding keeps its predecessor's name as the cluster, so a chain counts once.
        merged["cluster"] = merged["prev_key"].map(lambda k: clusters.get(k, k))
        clusters.update(dict(zip(merged["key"], merged["cluster"])))
        frames.append(merged)
    sample = pd.concat(frames, ignore_index=True).astype({"prev_id": object, "id": object})
    earlier = sample[["year", "id", "party", "mv_prev"]].rename(columns={"id": "prev_id", "mv_prev": "mv_prev2"})
    earlier["year"] = earlier["year"].map({v: k for k, v in PREVIOUS.items()})
    sample = sample.merge(earlier.dropna(subset=["year"]).astype({"year": int}), on=["year", "prev_id", "party"], how="left")
    return sample.rename(columns={"won": "win"})[[
        "year", "parliament", "province", "riding", "party", "win", "mv_prev", "mv_eligible", "mv_prev2",
        "prev_candidates", "prev_valid", "prev_electors", "link_overlap", "cluster"]]


def build_notional(candidates):
    """Party margins on the new maps from the official transposed votes, for every riding."""
    votes = {2015: read_transposition_2013().groupby("fed")[PARTIES].sum().astype(float),
             2025: read_transposition_2023()[PARTIES]}
    frames = []
    for year, table in votes.items():
        long = table.rename_axis("id").reset_index().melt(id_vars="id", var_name="party", value_name="votes")
        long = long[long.votes > 0].astype({"id": object})
        long["mv_prev"] = margins(long, ["id"])
        now = candidates[(candidates.year == year) & (candidates.party != "Other")].astype({"id": object})
        merged = now.merge(long[long.party != "Other"][["id", "party", "mv_prev"]], on=["id", "party"], how="inner")
        frames.append(merged.rename(columns={"won": "win"}).assign(cluster=lambda f: f["key"]))
    return pd.concat(frames, ignore_index=True)[["year", "parliament", "province", "riding", "party", "win", "mv_prev", "cluster"]]


def load_source():
    """The 1867-2008 candidate file."""
    d = pd.read_csv(SOURCE_FILE, low_memory=False, na_values=["NULL"], encoding="latin-1")
    d["mv_prev"] = pd.to_numeric(d["Mvprev"], errors="coerce")
    d["party"] = d["Combined party"].map(SOURCE_PARTY)
    d.loc[d["Combined party"].astype(str).str.startswith("Bloc"), "party"] = "Bloc"
    return d


def source_sample(d):
    """Parties in ridings they also contested last time, with lags for the balance checks."""
    main = d[d["Main election"] == 1]
    riding = main.groupby(["Parliament", "Riding Name"]).agg(
        prev_candidates=("Votes received", "size"), prev_valid=("Votes received", "sum")).reset_index()
    riding["Parliament"] += 1
    earlier = main[["Parliament", "Riding Name", "Combined party", "mv_prev"]].rename(columns={"mv_prev": "mv_prev2"})
    earlier = earlier.assign(Parliament=earlier["Parliament"] + 1).drop_duplicates(["Parliament", "Riding Name", "Combined party"])
    s = main[(main["Repeat party"] == 1) & main["party"].notna()]
    s = s.merge(riding, on=["Parliament", "Riding Name"], how="left").merge(earlier, on=["Parliament", "Riding Name", "Combined party"], how="left")
    out = pd.DataFrame({
        "year": pd.to_numeric(s["Date of Election"].astype(str).str.extract(r"(\d{4})", expand=False)),
        "parliament": s["Parliament"], "riding": s["Riding Name"], "party": s["party"], "win": s["Declared winner"],
        "province": s["Province"].map(normalise_name).replace({"NEWFOUNDLAND": "NEWFOUNDLANDANDLABRADOR"}),
        "mv_prev": s["mv_prev"], "mv_prev2": s["mv_prev2"], "prev_candidates": s["prev_candidates"],
        "prev_valid": s["prev_valid"], "link_overlap": 1.0, "cluster": s["Riding Name"].map(normalise_name)})
    return out.dropna(subset=["mv_prev"])


if __name__ == "__main__":
    download()
    candidates = pd.concat([load_candidates(y) for y in ELECTIONS], ignore_index=True)
    links, moved = build_links(candidates)
    OUTPUT.mkdir(exist_ok=True)
    links.to_csv(OUTPUT / "riding_links.csv", index=False, float_format="%.4f")
    checks = check_links(links, moved, candidates)
    checks.to_csv(OUTPUT / "link_checks.csv", index=False, float_format="%.4f")
    print(checks.to_string())
    official = build_sample(candidates, links)
    official.to_csv("data/official.csv", index=False)
    build_notional(candidates).to_csv("data/notional.csv", index=False)
    if not SOURCE_FILE.exists():
        raise SystemExit(f"Links and official samples written. {SOURCE_FILE} is missing, so data/sample.csv was not.")
    source = source_sample(load_source())
    pd.concat([source, official[official["year"] >= 2011]], ignore_index=True).to_csv("data/sample.csv", index=False)
    print(official.groupby("year").agg(rows=("win", "size"), linked=("link_overlap", lambda s: (s >= OVERLAP).sum())))
    counts = links.groupby("year")["overlap"].agg(
        ridings="size", **{f"overlap_{int(t * 100)}": (lambda s, t=t: int((s >= t).sum())) for t in (0.5, 0.75, 0.9, 0.99)})
    counts["not_linked"] = counts["ridings"] - counts["overlap_75"]
    counts.to_csv(OUTPUT / "link_counts.csv")
    print(counts)

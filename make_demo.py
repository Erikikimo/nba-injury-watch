"""Build docs/demo.html: the dashboard pre-loaded with the real 11/22/26 1:00 PM and
1:15 PM reports (parsed rows captured from the official PDFs), for previewing the UI."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
import injury_watch as w  # noqa: E402

ROWS_1PM = """03:30|DET@ATL|Detroit Pistons|Cade Cunningham|Probable|Injury/Illness - Right Knee Soreness
03:30|DET@ATL|Detroit Pistons|Jalen Duren|Out|Injury/Illness - Right Hamstring Strain
03:30|DET@ATL|Detroit Pistons|Ronald Holland II|Questionable|Injury/Illness - Left Knee Contusion / Bone Bruise
03:30|DET@ATL|Detroit Pistons|Isaac Jones|Questionable|G League - Two-Way
03:30|DET@ATL|Detroit Pistons|Ebuka Okorie|Out|Injury/Illness - Left Oblique Strain
03:30|DET@ATL|Detroit Pistons|Ugonna Onyenso|Out|G League - Two-Way
03:30|DET@ATL|Detroit Pistons|Taurean Prince|Out|Injury/Illness - Right Knee Arthroscopy
03:30|DET@ATL|Detroit Pistons|Duncan Robinson|Out|Injury/Illness - Left Quadriceps Strain
03:30|DET@ATL|Atlanta Hawks|Rafael Castro|Questionable|G League - Two-Way
03:30|DET@ATL|Atlanta Hawks|RayJ Dennis|Questionable|G League - Two-Way
03:30|DET@ATL|Atlanta Hawks|Kingston Flemings|Questionable|Injury/Illness - Lumbar Strain
03:30|DET@ATL|Atlanta Hawks|Mouhamed Gueye|Out|Injury/Illness - Left Foot Fracture
03:30|DET@ATL|Atlanta Hawks|Jock Landale|Out|Injury/Illness - Right Great Toe Sprain
03:30|DET@ATL|Atlanta Hawks|CJ McCollum|Out|Injury/Illness - Left Calf Strain
03:30|DET@ATL|Atlanta Hawks|Asa Newell|Out|Injury/Illness - Left Great Toe Surgery
03:30|DET@ATL|Atlanta Hawks|Henri Veesaar|Out|Injury/Illness - Right ACL Tear
03:30|DET@ATL|Atlanta Hawks|Jalen Wilson|Questionable|G League - Two-Way
06:00|OKC@MIA|Oklahoma City Thunder|Alex Caruso|Out|Injury/Illness - Right Hip Soreness
06:00|OKC@MIA|Oklahoma City Thunder|Shai Gilgeous-Alexander|Questionable|Injury/Illness - Low Back Contusion/ Neck Strain
06:00|OKC@MIA|Oklahoma City Thunder|Chet Holmgren|Out|Injury/Illness - Right Knee/ Injury Recovery
06:00|OKC@MIA|Oklahoma City Thunder|Thomas Sorber|Out|Injury/Illness - Right Knee Surgery
06:00|OKC@MIA|Oklahoma City Thunder|Nikola Topic|Out|Injury/Illness - Left Hip Strain
06:00|OKC@MIA|Oklahoma City Thunder|Cason Wallace|Out|Injury/Illness - Left Shoulder Surgery
06:00|OKC@MIA|Oklahoma City Thunder|Jalen Williams|Out|Injury/Illness - Left Ankle Surgery
06:00|OKC@MIA|Oklahoma City Thunder|Jaylin Williams|Out|Injury/Illness - Low Back Spasms
06:00|OKC@MIA|Miami Heat|Giannis Antetokounmpo|Questionable|Injury/Illness - Right Groin tendinitis
06:00|OKC@MIA|Miami Heat|Myron Gardner|Probable|Injury/Illness - Right Hamstring Tightness / Soreness
06:00|OKC@MIA|Miami Heat|Vladislav Goldin|Out|G League - Two-Way
06:00|OKC@MIA|Miami Heat|Keshad Johnson|Out|G League - Two-Way
07:00|DAL@UTA|Utah Jazz|Jonas Aidoo|Out|G League - Two-Way
07:00|DAL@UTA|Utah Jazz|Kobe Bufkin|Out|G League - Two-Way
07:00|DAL@UTA|Utah Jazz|Harrison Ingram|Out|G League - Two-Way
07:00|DAL@UTA|Utah Jazz|Jaren Jackson Jr.|Out|Injury/Illness - Right MCL Tear
07:00|DAL@UTA|Utah Jazz|Lauri Markkanen|Out|Injury/Illness - Right Hand Fracture
07:00|DAL@UTA|Utah Jazz|Jusuf Nurkic|Out|Injury/Illness - Right 2nd Plantar Plate Tear
07:00|DEN@CHI|Denver Nuggets|DaRon Holmes II|Out|G League - On Assignment
07:00|DEN@CHI|Denver Nuggets|Bryce Hopkins|Out|G League - Two-Way
07:00|DEN@CHI|Denver Nuggets|Julian Strawther|Out|Injury/Illness - Left Knee Sprain
07:00|DEN@CHI|Denver Nuggets|Cam Whitmore|Out|G League - Two-Way
07:00|DEN@CHI|Chicago Bulls|Tobe Awaka|Out|G League - Two-Way
07:00|DEN@CHI|Chicago Bulls|Nic Claxton|Questionable|Injury/Illness - Illness
07:00|DEN@CHI|Chicago Bulls|Norman Powell|Questionable|Injury/Illness - Right Hamstring Strain
07:00|DEN@CHI|Chicago Bulls|Orlando Robinson|Available|-
07:00|DEN@CHI|Chicago Bulls|Jaylin Sellers|Out|G League - Two-Way
07:00|DEN@CHI|Chicago Bulls|Jalen Smith|Probable|Injury/Illness - Gastrointestinal Illness
07:00|DEN@CHI|Chicago Bulls|Patrick Williams|Probable|Injury/Illness - Left Thumb Sprain
07:00|DEN@CHI|Chicago Bulls|Caleb Wilson|Out|Injury/Illness - Right Metacarpal Fracture
07:00|ORL@WAS|Orlando Magic|Paolo Banchero|Out|Injury/Illness - Right High Ankle Sprain
07:00|ORL@WAS|Orlando Magic|Jonathan Isaac|Out|Injury/Illness - Left Knee Injury Management
07:00|ORL@WAS|Orlando Magic|Izaiyah Nelson|Out|Injury/Illness - Left Ankle injury recovery
07:00|ORL@WAS|Orlando Magic|Noah Penda|Out|Injury/Illness - Right Partially torn hamstring
07:00|ORL@WAS|Washington Wizards|Deandre Ayton|Questionable|Injury/Illness - Illness
07:00|ORL@WAS|Washington Wizards|Reece Beekman|Out|Injury/Illness - Right AC Joint Sprain / Separation
07:00|ORL@WAS|Washington Wizards|Justin Champagnie|Out|Injury/Illness - Right Foot Surgery
07:00|ORL@WAS|Washington Wizards|Felix Okpara|Questionable|G League - Two-Way
07:00|ORL@WAS|Washington Wizards|Tristan Vukcevic|Out|Injury/Illness - Left Hip Impingement
07:00|ORL@WAS|Washington Wizards|Jamir Watkins|Out|Injury/Illness - Left ACL Repair / Surgery
08:00|IND@NYK|Indiana Pacers|Johnny Furphy|Out|Injury/Illness - Right ACL Repair / Surgery
08:00|IND@NYK|Indiana Pacers|Tyrese Haliburton|Out|Injury/Illness - Left Hamstring Strain
08:00|IND@NYK|Indiana Pacers|T.J. McConnell|Out|Injury/Illness - Left Hamstring Soreness
08:00|IND@NYK|Indiana Pacers|Ben Sheppard|Out|Injury/Illness - Left Meniscus Surgery
08:00|IND@NYK|Indiana Pacers|Pascal Siakam|Questionable|Injury/Illness - Left Hip Soreness / Tightness
08:00|IND@NYK|New York Knicks|OG Anunoby|Out|Injury/Illness - Left Calf Tightness
08:00|IND@NYK|New York Knicks|Jordan Clarkson|Out|Injury/Illness - Right Plantar Fasciitis
08:00|IND@NYK|New York Knicks|Karl-Anthony Towns|Questionable|Injury/Illness - Illness
08:30|BOS@GSW|Golden State Warriors|Jimmy Butler III|Out|Injury/Illness - Right ACL Repair / Surgery
08:30|BOS@GSW|Golden State Warriors|Stephen Curry|Out|Injury/Illness - Right Oblique Tear
08:30|BOS@GSW|Golden State Warriors|Moses Moody|Out|Injury/Illness - Left Patellar Tendon Repair / Surgery
08:30|BOS@GSW|Golden State Warriors|Kristaps Porzingis|Out|Not With Team
08:30|BOS@GSW|Golden State Warriors|Brandon Williams|Out|Injury/Illness - Left Hamstring Strain"""

TEAMS = [  # (date, time, matchup, team, submitted)
    ("11/22/2026", "03:30", "DET@ATL", "Detroit Pistons", True), ("11/22/2026", "03:30", "DET@ATL", "Atlanta Hawks", True),
    ("11/22/2026", "06:00", "OKC@MIA", "Oklahoma City Thunder", True), ("11/22/2026", "06:00", "OKC@MIA", "Miami Heat", True),
    ("11/22/2026", "07:00", "DAL@UTA", "Dallas Mavericks", False), ("11/22/2026", "07:00", "DAL@UTA", "Utah Jazz", True),
    ("11/22/2026", "07:00", "DEN@CHI", "Denver Nuggets", True), ("11/22/2026", "07:00", "DEN@CHI", "Chicago Bulls", True),
    ("11/22/2026", "07:00", "ORL@WAS", "Orlando Magic", True), ("11/22/2026", "07:00", "ORL@WAS", "Washington Wizards", True),
    ("11/22/2026", "08:00", "IND@NYK", "Indiana Pacers", True), ("11/22/2026", "08:00", "IND@NYK", "New York Knicks", True),
    ("11/22/2026", "08:30", "BOS@GSW", "Boston Celtics", False), ("11/22/2026", "08:30", "BOS@GSW", "Golden State Warriors", True),
    ("11/23/2026", "07:00", "MEM@CHA", "Memphis Grizzlies", False), ("11/23/2026", "07:00", "MEM@CHA", "Charlotte Hornets", False),
    ("11/23/2026", "07:00", "POR@PHI", "Portland Trail Blazers", False), ("11/23/2026", "07:00", "POR@PHI", "Philadelphia 76ers", False),
]


def parsed(label, rows, teams):
    return {"report_label": label,
            "players": [dict(game_date="11/22/2026", game_time=t, matchup=m, team=tm, player=n, name=n, status=s, reason=r)
                        for t, m, tm, n, s, r in rows],
            "teams": [dict(game_date=d, game_time=t, matchup=m, team=tm, submitted=s) for d, t, m, tm, s in teams]}


def main():
    index = w.PlayerIndex(json.loads((ROOT / "config/players.json").read_text()))
    rows_a = [tuple(l.split("|")) for l in ROWS_1PM.splitlines()]
    rows_b = []
    for r in rows_a:  # real changes between the 1:00 and 1:15 PM reports
        r = list(r)
        if r[3] in ("Jalen Wilson", "Rafael Castro"):
            r[4] = "Out"
        if r[3] == "RayJ Dennis":
            r[4] = "Available"
        rows_b.append(tuple(r))
    rows_b.append(("07:00", "ORL@WAS", "Washington Wizards", "Bub Carrington", "Questionable", "Injury/Illness - Illness"))
    url = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-22_01_{}PM.pdf"
    a = w.build_snapshot(parsed("11/22/26 01:00 PM", rows_a, TEAMS), index, url.format("00"), None)
    a["report"]["slot"] = "2026-11-22T13:00:00-05:00"
    b = w.build_snapshot(parsed("11/22/26 01:15 PM", rows_b, TEAMS), index, url.format("15"), None)
    b["report"]["slot"] = "2026-11-22T13:15:00-05:00"
    changes = list(reversed(w.diff(a, b)))
    html = (ROOT / "docs/index.html").read_text()
    demo = json.dumps({"latest": b, "changes": changes})
    html = html.replace("<script>", f"<script>window.__DEMO__ = {demo};</script>\n<script>", 1)
    (ROOT / "docs/demo.html").write_text(html)
    print(f"demo.html written: {len(b['players'])} players, {len(changes)} changes, "
          f"{sum(p['notable'] for p in b['players'])} tracked players on report")


if __name__ == "__main__":
    main()

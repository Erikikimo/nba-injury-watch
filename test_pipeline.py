"""End-to-end test: render PDFs with the real report's geometry, run the poller on
two consecutive "reports", and check the parsed rows and detected changes.

    pip install pdfplumber reportlab && python tests/test_pipeline.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
X = [24.1, 120.6, 201.0, 265.2, 426.0, 586.7, 667.1]  # column x positions from a real report
W, H = 841.95, 595.35


def render(path, label, pages):
    """pages: list of lists of rows; row = dict(date,time,matchup,team,player,status,reason=[lines])."""
    c = canvas.Canvas(str(path), pagesize=(W, H))
    for n, rows in enumerate(pages, 1):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(289, H - 62, f"Injury Report: {label}")
        c.setFont("Helvetica", 9)
        c.drawString(398, H - 545, f"Page {n} of {len(pages)}")
        y = 115.2
        if n == 1:
            for x, t in zip(X, ["Game Date", "Game Time", "Matchup", "Team", "Player Name", "Current Status", "Reason"]):
                c.drawString(x - 1, H - y, t)
            y += 21
        else:
            y = 90
        for r in rows:
            reason = r.get("reason", [])
            rowh = 22 if len(reason) <= 1 else 29
            mid = y + (7 if len(reason) == 2 else 0)
            for x, k in zip(X[:6], ["date", "time", "matchup", "team", "player", "status"]):
                if r.get(k):
                    c.drawString(x, H - mid, r[k])  # real PDFs centre the row on its reason
            if len(reason) == 2:
                c.drawString(X[6], H - y, reason[0])
                c.drawString(X[6], H - (y + 14), reason[1])
            elif reason:
                c.drawString(X[6], H - y, reason[0])
            y += rowh
        c.showPage()
    c.save()


def report(label, curry_status, add_porzingis, celtics_submitted):
    gsw_rows = [
        dict(time="08:30 (ET)", matchup="BOS@GSW", team="Boston Celtics",
             **({"player": "Tatum, Jayson", "status": "Out", "reason": ["Injury/Illness - Right Achilles; Repair"]}
                if celtics_submitted else {"reason": ["NOT YET SUBMITTED"]})),
        dict(team="Golden State Warriors", player="Butler III, Jimmy", status="Out",
             reason=["Injury/Illness - Right ACL Repair /", "Surgery"]),
        dict(player="Curry, Stephen", status=curry_status, reason=["Injury/Illness - Right Oblique Tear"]),
    ]
    if add_porzingis:
        gsw_rows.append(dict(player="Porzingis, Kristaps", status="Questionable", reason=["Illness"]))
    page1 = [
        dict(date="11/22/2026", time="07:00 (ET)", matchup="DEN@CHI", team="Chicago Bulls",
             player="Claxton, Nic", status="Questionable", reason=["Injury/Illness - Illness"]),
        dict(player="Johnson, Cameron", status="Out", reason=["Injury/Illness - Right Knee; Bone"]),
    ]
    page2_prefix = [dict(reason=["Bruise"])]  # page-break spill-over of Cameron Johnson's reason
    return label, [page1, page2_prefix + gsw_rows]


def main():
    work = Path(tempfile.mkdtemp())
    repo = work / "repo"
    shutil.copytree(ROOT / "scraper", repo / "scraper")
    shutil.copytree(ROOT / "config", repo / "config")
    a = work / "Injury-Report_2026-11-22_01_00PM.pdf"
    b = work / "Injury-Report_2026-11-22_01_15PM.pdf"
    render(a, *report("11/22/26 01:00 PM", "Questionable", False, False))
    render(b, *report("11/22/26 01:15 PM", "Out", True, True))

    for pdf in (a, b):
        subprocess.run([sys.executable, str(repo / "scraper" / "injury_watch.py"), "--pdf", str(pdf)], check=True)

    latest = json.loads((repo / "docs/data/latest.json").read_text())
    changes = json.loads((repo / "docs/data/changes.json").read_text())
    by_name = {p["name"]: p for p in latest["players"]}

    assert by_name["Jimmy Butler III"]["reason"] == "Injury/Illness - Right ACL Repair / Surgery", by_name["Jimmy Butler III"]
    assert by_name["Jimmy Butler III"]["watch"] is True
    assert by_name["Cameron Johnson"]["reason"] == "Injury/Illness - Right Knee; Bone Bruise", by_name["Cameron Johnson"]
    assert by_name["Cameron Johnson"]["rank"] == 161  # fuzzy match to "Cam Johnson"
    assert by_name["Nic Claxton"]["rank"] == 142      # alias "Nicolas Claxton"
    assert by_name["Stephen Curry"]["rank"] == 4
    assert by_name["Stephen Curry"]["team"] == "Golden State Warriors"
    assert by_name["Jayson Tatum"]["matchup"] == "BOS@GSW"

    kinds = {(c["type"], c["name"] or c["team"]) for c in changes}
    assert ("status", "Stephen Curry") in kinds, kinds
    assert ("added", "Kristaps Porzingis") in kinds, kinds
    assert ("initial", "Jayson Tatum") in kinds, kinds
    assert ("team_submitted", "Boston Celtics") in kinds, kinds
    curry = next(c for c in changes if c["name"] == "Stephen Curry")
    assert (curry["from"], curry["to"], curry["direction"]) == ("Questionable", "Out", "downgrade")
    print("ALL TESTS PASSED")
    for c in changes:
        print("  ", c["type"], c["name"] or c["team"], c["from"], "->", c["to"])


if __name__ == "__main__":
    main()

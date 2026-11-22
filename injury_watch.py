"""Poll the NBA's official injury report, diff it, and write JSON for the dashboard.

Run:  python scraper/injury_watch.py            (normal poll)
      python scraper/injury_watch.py --pdf X.pdf (process a local PDF, for testing)

Reports are published as static PDFs every 15 minutes (Eastern time):
  https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-22_01_15PM.pdf
so "is a new one posted?" is just a request for the next expected URL.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from parse_report import STATUSES, parse_pdf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
CONFIG = ROOT / "config" / "players.json"
ET = ZoneInfo("America/New_York")
URL_TMPL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{d:%Y-%m-%d}_{d:%I_%M%p}.pdf"
INDEX_TMPL = "https://official.nba.com/nba-injury-report-{season}/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
}
MAX_CATCHUP_SLOTS = 16   # look back at most 4 hours for missed reports
MAX_CHANGES = 2000
MAX_REPORTS = 500
SEVERITY = {s: i for i, s in enumerate(STATUSES)}  # Available=0 ... Out=4


# ---------------------------------------------------------------- names
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace("-", " ")
    s = re.sub(r"[.'’,]", "", s)
    parts = [p for p in s.split() if p not in SUFFIXES]
    return " ".join(parts)


class PlayerIndex:
    """Decides which players are 'notable' (top-200 ranked or on the watchlist)."""

    def __init__(self, cfg: dict):
        self.by_norm: dict[str, dict] = {}
        for i, n in enumerate(cfg.get("ranked", []), 1):
            self.by_norm[norm(n)] = {"display": n, "rank": i, "watch": False}
        for n in cfg.get("watchlist", []):
            info = self.by_norm.setdefault(norm(n), {"display": n, "rank": None, "watch": False})
            info["watch"] = True
        for ours, pdf_name in cfg.get("aliases", {}).items():
            if norm(ours) in self.by_norm:
                self.by_norm[norm(pdf_name)] = self.by_norm[norm(ours)]

    def lookup(self, pdf_name: str) -> dict | None:
        k = norm(pdf_name)
        if k in self.by_norm:
            return self.by_norm[k]
        # Fuzzy: same last name, one first name is a prefix of the other
        # (Cam/Cameron, Nic/Nicolas, Alex/Alexandre).
        parts = k.split()
        if len(parts) < 2:
            return None
        first, last = parts[0], " ".join(parts[1:])
        hits = []
        for key, info in self.by_norm.items():
            kp = key.split()
            if len(kp) >= 2 and " ".join(kp[1:]) == last:
                a, b = sorted([first, kp[0]], key=len)
                if len(a) >= 3 and b.startswith(a):
                    hits.append(info)
        uniq = {id(h): h for h in hits}
        return next(iter(uniq.values())) if len(uniq) == 1 else None


# ---------------------------------------------------------------- fetching
def slot_floor(t: dt.datetime) -> dt.datetime:
    t = t.astimezone(ET).replace(second=0, microsecond=0)
    return t.replace(minute=t.minute - t.minute % 15)


def fetch_pdf(url: str) -> bytes | None:
    import requests

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        print(f"  ! {url}: {e}")
        return None
    if r.status_code == 200 and r.content[:4] == b"%PDF":
        return r.content
    return None


def discover_from_index(now: dt.datetime) -> list[str]:
    """Fallback: scrape the official index page for PDF links (in case the naming changes)."""
    import requests

    y = now.year if now.month >= 8 else now.year - 1
    url = INDEX_TMPL.format(season=f"{y}-{(y + 1) % 100:02d}")
    try:
        html = requests.get(url, headers=HEADERS, timeout=30).text
    except Exception as e:  # noqa: BLE001
        print(f"  ! index page failed: {e}")
        return []
    links = re.findall(r"https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_[^\"'\s]+?\.pdf", html)
    return sorted(set(links))


def slot_from_url(url: str) -> dt.datetime | None:
    m = re.search(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})(?:_(\d{2}))?(AM|PM)\.pdf", url)
    if not m:
        return None
    d, hh, mm, ap = m.groups()
    t = dt.datetime.strptime(f"{d} {hh}:{mm or '00'} {ap}", "%Y-%m-%d %I:%M %p")
    return t.replace(tzinfo=ET)


# ---------------------------------------------------------------- snapshot + diff
def build_snapshot(parsed: dict, index: PlayerIndex, url: str, slot: dt.datetime | None) -> dict:
    players = []
    for p in parsed["players"]:
        info = index.lookup(p["name"])
        players.append({
            "name": p["name"], "team": p["team"], "matchup": p["matchup"],
            "game_date": p["game_date"], "game_time": p["game_time"],
            "status": p["status"], "reason": p["reason"],
            "rank": info["rank"] if info else None,
            "watch": bool(info and info["watch"]),
            "notable": bool(info),
        })
    return {
        "report": {
            "label": parsed["report_label"], "url": url,
            "slot": slot.isoformat() if slot else None,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        },
        "players": players,
        "teams": parsed["teams"],
    }


def _pkey(p):
    return f"{norm(p['name'])}|{p['team']}|{p['game_date']}"


def _tkey(t):
    return f"{t['team']}|{t['game_date']}"


def diff(prev: dict | None, cur: dict) -> list[dict]:
    if not prev:
        return []
    label = cur["report"]["label"]
    slot = cur["report"]["slot"]
    pp = {_pkey(p): p for p in prev["players"]}
    cp = {_pkey(p): p for p in cur["players"]}
    pt = {_tkey(t): t["submitted"] for t in prev["teams"]}
    ct = {_tkey(t): t["submitted"] for t in cur["teams"]}
    events = []

    def ev(kind, p, frm=None, to=None, direction=None):
        events.append({
            "report": label, "slot": slot, "type": kind, "direction": direction,
            "name": p["name"], "team": p["team"], "matchup": p["matchup"],
            "game_date": p["game_date"], "game_time": p["game_time"],
            "from": frm, "to": to, "reason": p.get("reason"),
            "rank": p.get("rank"), "watch": p.get("watch", False), "notable": p.get("notable", False),
        })

    for k, p in cp.items():
        if k in pp:
            old = pp[k]["status"]
            if old != p["status"]:
                worse = SEVERITY.get(p["status"], 0) > SEVERITY.get(old, 0)
                ev("status", p, old, p["status"], "downgrade" if worse else "upgrade")
        else:
            team_was_in = pt.get(_tkey(p))
            # 'added' = team had already filed and this player is new to it.
            # 'initial' = team just filed its first report for this game.
            ev("added" if team_was_in else "initial", p, None, p["status"],
               "downgrade" if SEVERITY.get(p["status"], 0) >= 2 else None)
    for k, p in pp.items():
        if k not in cp and ct.get(_tkey(p)):
            ev("removed", p, p["status"], None, "upgrade")
    for t in cur["teams"]:
        if t["submitted"] and pt.get(_tkey(t)) is False:
            events.append({
                "report": label, "slot": slot, "type": "team_submitted", "direction": None,
                "name": None, "team": t["team"], "matchup": t["matchup"],
                "game_date": t["game_date"], "game_time": t["game_time"],
                "from": None, "to": None, "reason": None, "rank": None, "watch": False, "notable": False,
            })
    return events


# ---------------------------------------------------------------- io
def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False))
    tmp.replace(path)


def process(pdf_path: str, url: str, slot, index: PlayerIndex) -> tuple[dict, list]:
    parsed = parse_pdf(pdf_path)
    if not parsed["players"] and not parsed["teams"]:
        raise ValueError(f"parsed nothing from {url}")
    cur = build_snapshot(parsed, index, url, slot)
    prev = load(DATA / "latest.json", None)
    events = diff(prev, cur)

    save(DATA / "latest.json", cur)
    changes = load(DATA / "changes.json", [])
    save(DATA / "changes.json", (list(reversed(events)) + changes)[:MAX_CHANGES])
    reports = load(DATA / "reports.json", [])
    reports.insert(0, {
        "label": cur["report"]["label"], "url": url, "slot": cur["report"]["slot"],
        "players": len(cur["players"]),
        "unsubmitted": sum(not t["submitted"] for t in cur["teams"]),
        "changes": len(events), "notable_changes": sum(e["notable"] for e in events),
    })
    save(DATA / "reports.json", reports[:MAX_REPORTS])
    return cur, events


def set_output(**kv):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="process a local PDF instead of polling")
    ap.add_argument("--now", help="pretend current ET time, e.g. 2026-11-22T13:20")
    args = ap.parse_args()
    index = PlayerIndex(load(CONFIG, {}))

    if args.pdf:
        slot = slot_from_url(args.pdf)
        cur, events = process(args.pdf, args.pdf, slot, index)
        print(f"{cur['report']['label']}: {len(cur['players'])} players, {len(events)} changes")
        return

    now = dt.datetime.fromisoformat(args.now).replace(tzinfo=ET) if args.now else dt.datetime.now(ET)
    latest = load(DATA / "latest.json", None)
    last_slot = None
    if latest and latest["report"].get("slot"):
        last_slot = dt.datetime.fromisoformat(latest["report"]["slot"])

    newest = slot_floor(now)
    if last_slot and newest - last_slot <= dt.timedelta(hours=4):
        candidates, t = [], last_slot + dt.timedelta(minutes=15)
        while t <= newest:
            candidates.append(t)
            t += dt.timedelta(minutes=15)
    else:
        # First run (or long gap): just find the most recent report.
        candidates = [newest - dt.timedelta(minutes=15 * i) for i in range(MAX_CATCHUP_SLOTS)][::-1]
        candidates = candidates[-MAX_CATCHUP_SLOTS:]

    found = []
    baseline = not last_slot
    for slot in (reversed(candidates) if baseline else candidates):
        url = URL_TMPL.format(d=slot)
        data = fetch_pdf(url)
        print(f"  {'✓' if data else '·'} {url.rsplit('/', 1)[-1]}")
        if data:
            found.append((slot, url, data))
            if baseline:
                break  # first run: newest report is all we need

    if not found and (not last_slot or newest - last_slot > dt.timedelta(hours=3)):
        print("  nothing at expected URLs; checking official index page")
        for url in discover_from_index(now)[-3:]:
            s = slot_from_url(url)
            if s and (not last_slot or s > last_slot):
                data = fetch_pdf(url)
                if data:
                    found.append((s, url, data))

    if not last_slot:
        found = found[-1:]  # baseline from the latest report only

    total_events = 0
    for slot, url, data in found:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(data)
            f.flush()
            try:
                cur, events = process(f.name, url, slot, index)
            except Exception as e:  # noqa: BLE001
                print(f"  ! failed to process {url}: {e}")
                continue
        notable = [e for e in events if e["notable"]]
        total_events += len(events)
        print(f"{cur['report']['label']}: {len(cur['players'])} players, "
              f"{len(events)} changes ({len(notable)} notable)")
        for e in notable:
            print(f"   * {e['name']} ({e['team']}): {e['from']} -> {e['to']}")

    set_output(changed=str(bool(found)).lower(), events=total_events)
    if not found:
        print("No new report.")


if __name__ == "__main__":
    main()

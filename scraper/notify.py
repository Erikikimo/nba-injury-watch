"""Send a phone push (via ntfy.sh) for tracked-player changes since the last alert.

Runs after injury_watch.py. Needs env NTFY_TOPIC (a GitHub secret); does nothing without it.
Keeps its place in docs/data/notify_state.json so each change is only sent once.
"""
import json
import os
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "docs" / "data"
STATE = DATA / "notify_state.json"
SEV = {"Available": 0, "Probable": 1, "Questionable": 2, "Doubtful": 3, "Out": 4}
SHORT = {"Available": "AVAIL", "Probable": "PROB", "Questionable": "QUES", "Doubtful": "DOUBT", "Out": "OUT", None: "off report"}


def load(p, default):
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def line(e):
    who = f"{e['name']} ({e['matchup']})"
    if e["type"] == "status":
        arrow = "🔴" if e["direction"] == "downgrade" else "🟢"
        return f"{arrow} {who}: {SHORT[e['from']]} → {SHORT[e['to']]}"
    if e["type"] == "removed":
        return f"🟢 {who}: dropped off report (was {SHORT[e['from']]})"
    if e["type"] == "added":
        return f"🟠 {who}: added as {SHORT[e['to']]}"
    return f"⚪ {who}: listed {SHORT[e['to']]}"  # initial listing when team files


def is_big(e):
    """Worth a loud alert: a top-50 or watchlist player getting worse."""
    important = e.get("watch") or (e.get("rank") or 999) <= 50
    worse = e["type"] in ("status", "added") and SEV.get(e["to"], 0) > SEV.get(e["from"], 0)
    return important and worse


def main():
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    reports = load(DATA / "reports.json", [])
    if not reports:
        return
    newest = reports[0]["slot"]
    state = load(STATE, {})
    last = state.get("last_slot")
    STATE.write_text(json.dumps({"last_slot": newest}))
    if not topic or not last or newest == last:
        return  # first run just sets a starting point; no backlog blast

    changes = load(DATA / "changes.json", [])
    events = [e for e in changes if e.get("notable") and (e.get("slot") or "") > last]
    # Initial listings (team just filed) are noisy: only Out/Doubtful/Questionable ones matter.
    events = [e for e in events if e["type"] != "initial" or SEV.get(e["to"], 0) >= 2]
    if not events:
        return
    events.sort(key=lambda e: (not is_big(e), e.get("rank") or 999))
    big = [e for e in events if is_big(e)]
    title = (f"{big[0]['name']}: {SHORT[big[0]['from']]} -> {SHORT[big[0]['to']]}" if big
             else f"Injury report: {len(events)} update{'s' * (len(events) > 1)}")
    body = "\n".join(line(e) for e in events[:12])
    if len(events) > 12:
        body += f"\n…and {len(events) - 12} more"
    body += f"\n(report {reports[0]['label']} ET)"

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    owner, _, name = repo.partition("/")
    url = f"https://{owner.lower()}.github.io/{name}/" if repo else None
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), method="POST")
    req.add_header("Title", title.encode("ascii", "ignore").decode() or "Injury report")
    req.add_header("Priority", "high" if big else "default")
    req.add_header("Tags", "basketball")
    if url:
        req.add_header("Click", url)
    try:
        urllib.request.urlopen(req, timeout=20)
        print(f"sent alert: {title} ({len(events)} items)")
    except Exception as e:  # noqa: BLE001 - never fail the run over an alert
        print(f"alert failed: {e}")


if __name__ == "__main__":
    main()

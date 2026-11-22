"""Parse an official NBA injury report PDF into structured rows.

The PDF is a landscape table with columns:
  Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason

Layout quirks this handles (verified against real 2026-27 reports):
  * Date / time / matchup / team are only printed on the first row of their group
    -> carried forward.
  * A reason that wraps onto two lines is vertically centred on the row, so its
    first line sits ~7pt ABOVE the player's line and the second ~7pt BELOW.
    -> reason-only lines are attached to the nearest player row.
  * A reason can spill over a page break -> attached to the previous row.
  * Words split across a line with a trailing hyphen ("Gilgeous-" "Alexander,").
  * Teams that haven't filed show "NOT YET SUBMITTED" in the Reason column.

The core works on plain word lists so it can be tested with any PDF text
extractor; `parse_pdf` is the pdfplumber adapter used in production.
"""
from __future__ import annotations

import re

STATUSES = ["Available", "Probable", "Questionable", "Doubtful", "Out"]
COLS = ["date", "time", "matchup", "team", "player", "status", "reason"]
# Column start x-positions measured on a real report (page width 841.95pt).
DEFAULT_COL_STARTS = [23.1, 119.6, 200.0, 264.2, 425.0, 585.7, 666.1]
DEFAULT_PAGE_WIDTH = 841.95

LINE_TOL = 2.0       # words within this many pt vertically are on the same line
ATTACH_MAX_DY = 12.0  # reason fragment must be this close to a row to attach to it


def _join(tokens: list[str]) -> str:
    out = ""
    for t in tokens:
        if not out:
            out = t
        elif out.endswith("-") and len(out) > 1 and out[-2] != " ":
            out += t  # re-join hyphen-wrapped words: "Two-" + "Way"
        else:
            out += " " + t
    return out.strip()


def _cluster_lines(words):
    """words: list of (x0, top, text) -> list of lines (top, [(x0, text)])."""
    lines = []
    for x0, top, text in sorted(words, key=lambda w: (w[1], w[0])):
        if lines and abs(top - lines[-1][0]) <= LINE_TOL:
            lines[-1][1].append((x0, text))
        else:
            lines.append([top, [(x0, text)]])
    for ln in lines:
        ln[1].sort()
    return lines


def _detect_columns(pages):
    for page in pages:
        for top, toks in _cluster_lines(page["words"]):
            texts = [t for _, t in toks]
            if "Player" in texts and "Reason" in texts and "Matchup" in texts:
                games = [x for x, t in toks if t == "Game"]
                find = lambda name: next(x for x, t in toks if t == name)
                if len(games) >= 2:
                    return [games[0], games[1], find("Matchup"), find("Team"),
                            find("Player"), find("Current"), find("Reason")]
    w = pages[0].get("width", DEFAULT_PAGE_WIDTH) if pages else DEFAULT_PAGE_WIDTH
    return [x * w / DEFAULT_PAGE_WIDTH for x in DEFAULT_COL_STARTS]


def _col_of(x0, starts):
    idx = 0
    for i, s in enumerate(starts):
        if x0 >= s - 3:
            idx = i
    return COLS[idx]


def display_name(raw: str) -> str:
    """'Holland II, Ronald' -> 'Ronald Holland II'."""
    if "," in raw:
        last, first = raw.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return raw.strip()


def parse_words(pages):
    """pages: [{'width': float, 'words': [(x0, top, text), ...]}, ...]

    Returns {'report_label': str|None, 'players': [...], 'teams': [...]}
    """
    starts = _detect_columns(pages)
    ctx = {"date": None, "time": None, "matchup": None, "team": None}
    players, teams = [], []
    report_label = None
    last_record = None

    for page in pages:
        page_records = []  # (top, record)
        orphans = []       # (top, text)
        for top, toks in _cluster_lines(page["words"]):
            text = _join([t for _, t in toks])
            if text.startswith("Injury Report:"):
                report_label = text.replace("Injury Report:", "").strip()
                continue
            if re.fullmatch(r"Page \d+ of \d+", text):
                continue
            cells = {c: [] for c in COLS}
            for x0, t in toks:
                cells[_col_of(x0, starts)].append(t)
            cells = {c: _join(v) for c, v in cells.items()}
            if cells["player"].startswith("Player Name") or cells["matchup"] == "Matchup":
                continue  # header row

            is_row = any(cells[c] for c in ("date", "time", "matchup", "team", "player", "status"))
            if not is_row:
                if cells["reason"]:
                    orphans.append((top, cells["reason"]))
                continue

            if cells["date"]:
                ctx["date"] = cells["date"]
            if cells["time"]:
                ctx["time"] = cells["time"].replace("(ET)", "").strip()
            if cells["matchup"]:
                ctx["matchup"] = cells["matchup"]
            if cells["team"]:
                ctx["team"] = cells["team"]
                teams.append({
                    "game_date": ctx["date"], "game_time": ctx["time"],
                    "matchup": ctx["matchup"], "team": ctx["team"],
                    "submitted": "NOT YET SUBMITTED" not in cells["reason"].upper(),
                })

            if cells["player"] or cells["status"]:
                rec = {
                    "game_date": ctx["date"], "game_time": ctx["time"],
                    "matchup": ctx["matchup"], "team": ctx["team"],
                    "player": cells["player"], "name": display_name(cells["player"]),
                    "status": cells["status"], "_reason": [],
                }
                if cells["reason"]:
                    rec["_reason"].append((top, cells["reason"]))
                players.append(rec)
                page_records.append((top, rec))
                last_record = rec
            elif cells["reason"] and "NOT YET SUBMITTED" not in cells["reason"].upper():
                orphans.append((top, cells["reason"]))

        first_top = page_records[0][0] if page_records else None
        for top, text in orphans:
            best = min(page_records, key=lambda r: abs(r[0] - top), default=None)
            if best and abs(best[0] - top) <= ATTACH_MAX_DY:
                best[1]["_reason"].append((top, text))
            elif first_top is not None and top < first_top and players:
                # spill-over from previous page: attach to last row before this page
                idx = players.index(page_records[0][1]) - 1
                if idx >= 0:
                    players[idx]["_reason"].append((-1e6 + top, text))
            elif best:
                best[1]["_reason"].append((top, text))
            elif last_record:
                last_record["_reason"].append((1e6 + top, text))

    for rec in players:
        frags = sorted(rec.pop("_reason"), key=lambda f: f[0])
        # page-break spill fragments were stored with a large negative key on the
        # *next* page; they belong after the row's own text.
        own = [t for k, t in frags if k > -1e5]
        spill = [t for k, t in frags if k <= -1e5]
        rec["reason"] = _join(own + spill)
        if rec["status"] not in STATUSES:
            rec["status"] = rec["status"] or "Unknown"

    return {"report_label": report_label, "players": players, "teams": teams}


def parse_pdf(path: str):
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            words = p.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
            pages.append({
                "width": float(p.width),
                "words": [(float(w["x0"]), float(w["bottom"]), w["text"]) for w in words],
            })
    return parse_words(pages)

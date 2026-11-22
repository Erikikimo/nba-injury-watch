# NBA Injury Watch

Checks the NBA's official injury report every few minutes, works out what changed since the last report, and publishes a dashboard to GitHub Pages. Everything runs for free on GitHub.

**How it works**
- The NBA posts each report as a PDF at a predictable address every 15 minutes (Eastern time), e.g. `…/Injury-Report_2026-11-22_01_15PM.pdf`. The poller asks for the next expected file. If it's there, it downloads and parses it. If it's missing, the report isn't up yet.
- Each report is compared with the previous one to catch status changes (Questionable → Out), players added to or dropped from the report, and teams that have now submitted.
- "Top players" means the top 200 of the Basketball Monster rankings plus a watchlist, both stored in `config/players.json`.

## Setup (about 5 minutes)

1. **Create a new repository** on GitHub, e.g. `nba-injury-watch`. Make it **public**: public repos get unlimited free Actions minutes. Checking every 5 minutes would use up a private repo's 2,000 free minutes per month.
2. **Add these files** to the repo. You can drag the unzipped folder onto the repo's "uploading an existing file" page; make sure the `.github` folder comes along. Or run:
   ```bash
   cd nba-injury-watch
   git init -b main && git add . && git commit -m "Initial commit"
   git remote add origin https://github.com/<you>/nba-injury-watch.git
   git push -u origin main
   ```
3. **Settings → Pages →** under "Build and deployment", set *Source* to **GitHub Actions**.
4. **Settings → Actions → General →** under "Workflow permissions", choose **Read and write permissions** and save.
5. **Actions tab → Injury watch → Run workflow.** After a minute or so your dashboard is live at
   `https://<you>.github.io/nba-injury-watch/`

The first run records the latest report as a baseline. Changes start appearing once the next report comes out.

## Things to know
- GitHub runs scheduled jobs on a best-effort basis. The workflow asks for every 5 minutes, but in practice runs are often 5–15 minutes apart. If a run is late, the poller catches up on any reports it missed, up to 4 hours back, so no changes are skipped.
- Data is only committed when a new report shows up, so the repo history won't fill up with empty commits.
- If the NBA ever changes its file naming, the poller falls back to scraping the links from `official.nba.com/nba-injury-report-<season>/`.

## Customising
- **Who counts as notable:** edit `config/players.json`. Use `ranked` for the top-200 list (order sets the rank badge), `watchlist` for anyone else, and `aliases` when the NBA's PDF uses a different first name (e.g. "Mo Bamba" → "Mohamed Bamba"). Nickname-style variants like Cam/Cameron or Nic/Nicolas are matched automatically.
- **Refresh the rankings:** replace the `ranked` list with a fresh copy from basketballmonster.com/playerrankings.aspx.

## Files
| Path | What it is |
|---|---|
| `scraper/parse_report.py` | Turns the PDF table into rows. Handles carried-down team/game cells, two-line reasons, and reasons that spill onto the next page |
| `scraper/injury_watch.py` | Finds new reports, compares them with the previous one, writes `docs/data/*.json` |
| `docs/index.html` | The dashboard (static page, refreshes every 60s) |
| `docs/data/` | `latest.json` (current report), `changes.json` (change feed), `reports.json` (history) |
| `.github/workflows/injury-watch.yml` | Schedule, commit, and Pages deploy |
| `tests/test_pipeline.py` | End-to-end test using PDFs built with the real report's layout |

Run it locally: `pip install -r requirements.txt && python scraper/injury_watch.py`

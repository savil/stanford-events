# Stanford events

A public, by-day listing of Stanford campus events for **today through the next 30 days** (`America/Los_Angeles`).

v1 scrapes three sources, writes `out/events.json` and `out/index.html`, and publishes the `out/` directory with GitHub Pages.

**Site:** https://savil.github.io/stanford-events/

More sources come later. The longer wishlist in [`sources.md`](sources.md) is not scraped.

## Sources (v1 only)

| Module | URL | Strategy |
|--------|-----|----------|
| `localist` | https://events.stanford.edu/ and [Bing Concert Hall](https://events.stanford.edu/bing_concert_hall) | Localist JSON API `/api/2/events` |
| `hci_seminar` | https://hci.stanford.edu/seminar/ | Fall quarter HTML table |
| `hai` | https://hai.stanford.edu/events | Server-rendered HTML cards |

One source failing does not fail the run. The error is stored in `out/errors.json` and noted on the page. The run fails only when every source fails, so an empty calendar is not published over the last good listing.

There are no topic filters. Audience is shown as a badge:

| Value | Badge |
|-------|-------|
| `open_to_public` | Public |
| `stanford_only` | Stanford only |
| `unknown` | Unknown |

Near-duplicate events (same or almost the same title, and the same start) are collapsed across sources. The fuller record is kept. Other source names are stored on `also_sources`.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m stanford_events
# optional: python -m stanford_events --days 30 --out out
python -m unittest discover -s tests -v
```

That writes:

- `out/index.html` — the public by-day page (this file is the GitHub Pages homepage)
- `out/events.json` — normalized events in the window
- `out/errors.json` — per-source failures, including tracebacks
- `out/sample-preview.md` — by-day markdown for review

Open `out/index.html` in a browser, or from the repo root:

```bash
python3 -m http.server 8765 --directory out
```

Then visit http://127.0.0.1:8765/ .

## Schema

Each event in `out/events.json`:

- `id` — sha256 prefix of `source_url + title + start`
- `title`, `start`, `end` (ISO 8601; naive times are treated as `America/Los_Angeles`)
- `location` (optional), `url`
- `source_name`, `source_url`
- `description` (optional, short; omitted on the HTML page)
- `audience` — `open_to_public`, `stanford_only`, or `unknown`
- `also_sources` — optional list of other source names collapsed into this row

### Audience

- **HCI Seminar** — the page says the seminar is open to the public, so talks are `open_to_public`.
- **Localist** — `filters.event_audience` names (`Everyone`, `General Public` → public; Students / Faculty / Staff / Postdocs / Affiliates / Alumni / Members without a public tag → `stanford_only`; missing or unrecognized → `unknown`).
- **HAI** — listing text. Clear public phrasing → `open_to_public`; Stanford community / campus-only / SUNet → `stanford_only`; otherwise `unknown`.

## GitHub Action

[`.github/workflows/scrape.yml`](.github/workflows/scrape.yml) (`Scrape and publish`):

- **Schedule:** weekdays at 15:32 UTC (`32 15 * * 1-5`), which is 8:32am PDT and 7:32am PST. GitHub may start the job a few minutes late.
- **Manual:** Actions → Scrape and publish → Run workflow (`workflow_dispatch`).
- Installs Python 3.12 and `requirements.txt`, runs the unit tests, then `python -m stanford_events --days 30 --out out`.
- Commits refreshed `out/` back to the branch the workflow ran on (the schedule uses `main`) as `github-actions[bot]`.
- On `main`, uploads `out/` as the Pages artifact and deploys it. `out/index.html` is the site root, so the homepage is https://savil.github.io/stanford-events/ and the JSON is https://savil.github.io/stanford-events/events.json .

A dispatch from another branch still refreshes that branch's `out/` and does not deploy Pages.

### Enable GitHub Pages (one settings step)

Pages is not on for this repo yet, and turning it on is a repository setting this change cannot flip by itself.

1. Open **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Merge the workflow to `main`.
4. Run **Actions → Scrape and publish → Run workflow** on `main` (or wait for the next weekday morning).

Until that source is set, the scrape job can still commit `out/`, and the deploy job will fail. After it succeeds, the site is https://savil.github.io/stanford-events/ .

If `main` is protected, allow `github-actions[bot]` to push, or the commit step will fail.

## Politeness

- User-Agent: `StanfordEvents/1.0 (+https://savil.github.io/stanford-events/; …)`
- About 0.4s between HTTP requests
- Localist pages are capped (`pp=100`, at most 15 pages)

## Limitations

- v1 is these three parsers only. Do not scrape the rest of [`sources.md`](sources.md) yet.
- Localist returns one instance per occurrence. Audience comes from `filters.event_audience`, not from the title.
- HCI uses the current quarter table (Fall 2026 at time of writing). “No Seminar” rows are skipped. Times are the page’s standing Friday 11:30–12:30 PT slot.
- HAI cards often omit the room, so location may be empty. Cards without audience language stay `unknown`.
- Deduping matches normalized titles (a short added suffix counts) and starts within 15 minutes on the same Pacific day. An exact title also matches when one source only has a date (midnight) and the other has a clock time. Different times on the same day are kept.
- HTML and API shapes can change. Parsers are brittle.

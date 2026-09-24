# Architecture

A weekday job scrapes Stanford calendars and publishes one by-day listing for today through the next 30 days (`America/Los_Angeles`). The public page is https://savil.github.io/stanford-events/. [`sources.md`](sources.md) is the curated URL list: scraped, already in the Localist main feed, or skipped.

## Data flow

```
sources.md  →  registry.iter_sources()
            →  each source's fetch(days)
            →  build_event()
            →  filter_window + dedupe
            →  out/events.json
               out/index.html
               out/sample-preview.md
               out/errors.json
            →  GitHub Pages (out/ is the site root)
```

[`stanford_events/__main__.py`](stanford_events/__main__.py) is the CLI: `python -m stanford_events --days 30 --out out`. It calls every source in [`stanford_events/registry.py`](stanford_events/registry.py). One source raising is recorded and the others continue. After the window filter and cross-source dedupe, the CLI writes:

| File | Role |
|------|------|
| `out/events.json` | Normalized events in the window |
| `out/index.html` | The Pages homepage: one static page, sections per Pacific day |
| `out/sample-preview.md` | Same listing as markdown, for review |
| `out/errors.json` | Per-source error, plus a short traceback |

`errors.json` is written first. If the window is empty and any source raised, the process exits 1 and leaves the previous JSON, HTML, and markdown in place, so the Action does not commit an empty calendar over the last good listing. A partial failure still publishes the events that came back. The HTML page notes source failures.

There is no database and no request-time scrape. Pages serves the committed `out/` files. Audience toggles run in the browser against `data-audience` on each card.

## Layout

```
stanford_events/__main__.py      CLI
stanford_events/registry.py      Source list (key, label, fetch)
stanford_events/normalize.py     Schema, window, dedupe
stanford_events/preview.py       index.html and sample-preview.md
stanford_events/http_util.py     Shared GET (User-Agent, ~0.4s gap)
stanford_events/parse_util.py    JSON:API and HTML text helpers
stanford_events/localist.py      events.stanford.edu
stanford_events/sws.py           Shared SWS JSON:API view
stanford_events/hs_events.py     Shared H&S hs_event JSON:API
stanford_events/html_listings.py HTML-only sites (GSB, SLAC, …)
stanford_events/*.py             One module per other site
tests/                           unittest
.github/workflows/scrape.yml     Scrape, commit out/, deploy Pages
sources.md                       What is scraped, covered, or skipped
requirements.txt                 requests, beautifulsoup4, lxml, python-dateutil
```

The module table in [`README.md`](README.md) matches `iter_sources()`. Registry keys are short (`law`, `gsb`); `source_name` on an event is the display label (`Stanford Law`, `Stanford GSB`).

## Event schema

Each object in `out/events.json` comes from `build_event()` in [`stanford_events/normalize.py`](stanford_events/normalize.py):

- `id` — first 16 hex chars of sha256(`source_url|title|start`)
- `title`, `url`, `source_name`, `source_url`
- `start`, `end` — ISO 8601. Naive datetimes are treated as `America/Los_Angeles`. `end`, `location`, and `description` may be null.
- `description` — shortened to 280 characters. The HTML page does not show it.
- `audience` — `open_to_public`, `stanford_only`, or `unknown`
- `also_sources` — optional. Other `source_name` values collapsed into this row.

The window is inclusive Pacific dates from today through today+`--days` (default 30). `filter_window` keeps events whose start is in `[today 00:00 PT, today+days+1 00:00 PT)`.

`dedupe` first merges exact `id`s, then groups by Pacific day. Titles match when they normalize to the same phrase, or one only adds a short suffix (at least 28 characters, ratio ≥ 0.62, at most four extra words). Starts match within 15 minutes. An exact title also matches when one side is date-only (midnight) and the other has a clock time. Different times on the same day stay separate. The kept row prefers a known audience, a real clock time, location, and a longer description; missing fields are filled from the other row. The other source names go on `also_sources`.

## Audience

Classification lives next to the parsers; nothing defaults to public.

- Localist uses `filters.event_audience`. Drupal tag lists use the same helper, `classify_audience_names`: `Everyone` / `General Public` → `open_to_public`; a set made only of Students / Faculty / Staff / Postdocs / Affiliates / Alumni / Faculty/Staff / Alumni/Friends / Members → `stanford_only`; empty, unrecognized, or `By Invitation Only` → `unknown`. A public tag wins over campus tags.
- GSE uses `field_event_admission` (`open_to_public` or community-only). Events with `field_hide_from_public` are skipped.
- HTML and other JSON listings use `classify_audience_from_text` (`open to the public`, `free and open to …`, Stanford community / campus-only / SUNet). Ticketed shows stay `unknown` unless the page says they are public.
- HCI Seminar is `open_to_public` because the seminar page says so.

The static page badges those three values as Public, Stanford only, and Unknown. Buttons write the choice into the URL: `?audience=public`, `?audience=stanford`, or `?audience=public,stanford`. `#audience=public` is read too, then replaced with the query form. Neither button shows every event, including Unknown. Any selection hides the other audiences; Unknown stays hidden until both toggles are off. CSS hides non-matching cards before paint; the script updates day counts and the jump links.

## Adding a source

1. Put the URL in [`sources.md`](sources.md) under Scraped, Covered by the Localist main feed, or Skipped, with the reason.
2. Do not add another fetch for an events.stanford.edu department or venue page that the unfiltered Localist `/api/2/events` feed already contains. Bing Concert Hall is the exception still queried by `venue_id`; overlap collapses in dedupe. `department_id` is ignored by that API.
3. If the site is a Localist mirror (`su_event_source` or the event link is `events.stanford.edu`), skip those rows. [`stanford_events/sws.py`](stanford_events/sws.py) and [`stanford_events/hs_events.py`](stanford_events/hs_events.py) already do this.
4. Otherwise add a `fetch(days) -> list[Event]` and a `Source` in `iter_sources()`:
   - SWS department `/events` pages: `fetch_sws` (`/jsonapi/views/stanford_events/list_page`).
   - H&S `hs_event` pages: `fetch_hs`.
   - HTML with no JSON feed: a function in [`stanford_events/html_listings.py`](stanford_events/html_listings.py), or a dedicated module (Localist, HCI, HAI, Stanford Live, CCRMA, Law, GSE, FSI, Hoover) that ends in `build_event(...)`.
5. Use `http_util.get` for requests. Return `[]` when the page lists nothing; raise on HTTP or parse failure so the error lands in `out/errors.json`.
6. Cover the parser with a fixture test under [`tests/`](tests/).

## CI and deploy

[`.github/workflows/scrape.yml`](.github/workflows/scrape.yml) (`Scrape and publish`):

- Schedule: `0 11 * * 1-5` (11:00 UTC; 3:00 AM PST). During PDT the same cron fires at 4:00 AM local. GitHub may start it a few minutes late.
- Also `workflow_dispatch` (Actions → Scrape and publish → Run workflow).
- Python 3.12, `pip install -r requirements.txt`, `python -m unittest discover -s tests -v`, then `python -m stanford_events --days 30 --out out`.
- Commits `out/` on the branch the workflow ran on (`github-actions[bot]`, message `Refresh Stanford events listing`) when the tree changed. The schedule uses `main`.
- On `main` only: uploads `out/` with `actions/upload-pages-artifact` and deploys with `actions/deploy-pages`. A dispatch from another branch refreshes that branch's `out/` and does not deploy.
- Concurrency group `stanford-events-scrape` does not cancel an in-progress run.

Pages source must be **GitHub Actions** (Settings → Pages). Until that is set, the scrape job can still commit `out/` and the deploy job fails. `out/index.html` is the site root, so the JSON is https://savil.github.io/stanford-events/events.json. If `main` is protected, `github-actions[bot]` needs permission to push.

## What this version does not do

- No topic filters. The only client filter is audience.
- `sources.md` is the full list. URLs on it are scraped, already covered by Localist, or skipped. None of them are deferred.
- No server, accounts, or search index. The page is the generated HTML plus a small script.
- Descriptions stay in JSON and the markdown preview. They are not rendered on the HTML page.
- Parsers follow each site's current HTML or JSON shape. When a feed changes, that source fails alone until its parser is updated.

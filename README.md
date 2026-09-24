# Stanford Events SPIKE (local)

Local spike to scrape **three** Stanford event source shapes, normalize them into a shared JSON schema, and write reviewable previews. **Not** a full multi-source crawler, **not** a GitHub Pages deploy.

## Sources (spike only)

| Module | URL | Strategy |
|--------|-----|----------|
| `localist` | https://events.stanford.edu/ (+ Bing Concert Hall venue) | Localist JSON API `/api/2/events` (preferred over HTML) |
| `hci_seminar` | https://hci.stanford.edu/seminar/ | Fall quarter HTML table (`#quarter_talk_table`); Fridays 11:30–12:30 PT, Gates B3 |
| `hai` | https://hai.stanford.edu/events | SSR HTML cards on the HAI Next.js listing |

A longer curated source list lives in [`sources.md`](sources.md) for future work — this SPIKE does **not** scrape it.

## Schema

Each event in `out/events.json`:

- `id` — stable sha256 prefix of `source_url + title + start`
- `title`, `start`, `end` (ISO 8601; naive times treated as `America/Los_Angeles`)
- `location` (optional), `url`
- `source_name`, `source_url`
- `description` (optional, short)
- `audience` — one of `open_to_public` | `stanford_only` | `unknown` (no other values; `unknown` when the source gives no clear signal)

### Audience classification

- **HCI Seminar** — page states open to the public → all talks `open_to_public`.
- **Localist** — uses API `filters.event_audience` names (`Everyone`, `General Public` → public; Students/Faculty/Staff/Postdocs/Affiliates/Alumni/Members without public tags → `stanford_only`; missing filters → `unknown`).
- **HAI** — listing-card text (prefer description blurbs over title keywords): clear public / open-to-all phrasing → `open_to_public`; Stanford community / campus-only / SUNet → `stanford_only`; else `unknown`.

## Setup

```bash
cd /workspace/stanford-events
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
cd /workspace/stanford-events
source .venv/bin/activate
python -m stanford_events
# or: python -m stanford_events --days 30 --out out
```

Writes:

- `out/events.json` — normalized events in **today .. +30 days PT**
- `out/errors.json` — per-source failures (run continues)
- `out/sample-preview.md` — by-day markdown (includes audience)
- `out/index.html` — minimal mobile-friendly by-day preview with Public / Stanford only / Unknown badges (open locally; not published)

## Politeness

- Custom `User-Agent`: `StanfordEventsSpike/0.1 …`
- ~0.4s minimum interval between HTTP requests
- Modest pagination (`pp=100`, capped pages) — do not hammer Localist

## Limitations

- **SPIKE only** — three parsers, not the ~35 URLs in `sources.md`.
- **Localist** returns one `event_instance` per list row for multi-day / recurring items; we keep each instance as its own event. Very large result sets are page-capped. Audience comes from `filters.event_audience` only (not inferred from titles).
- **HCI** assumes the current quarter table (Fall 2026 at time of writing). “No Seminar” / TBA-only rows are skipped or labeled; times are fixed (11:30–12:30 PT) from the page header, not scraped per row.
- **HAI** listing HTML omits room for many cards; location is often null unless present in the card text. Duplicate cards in the SSR DOM are deduped by URL. Many cards lack audience language → `unknown`.
- Dedupe collapses exact ids and same title+day *within* a source_url; the same talk on Localist and HAI can appear twice so you can compare shapes.
- No auth, no GitHub Pages, no cron — re-run the CLI when you want a fresh snapshot.
- Site HTML/API shapes can change without notice; treat parsers as brittle research code.

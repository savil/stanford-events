# Stanford event sources

Updated 2026-09-24. Every URL below is either scraped, already covered by the
Localist main feed, or skipped. Nothing on this list is deferred.

Window for every scraper: today through +30 days, `America/Los_Angeles`.

## Scraped

| URL | Module | How |
|-----|--------|-----|
| https://events.stanford.edu/ | `localist` | Localist JSON `/api/2/events` (main feed) |
| https://events.stanford.edu/bing_concert_hall | `localist` | Extra `venue_id` query kept from v1. A spot-check on 2026-09-24 found Bing's in-window events already in the main feed; dedupe collapses the overlap. |
| https://hci.stanford.edu/seminar/ | `hci_seminar` | Fall-quarter HTML table |
| https://hai.stanford.edu/events | `hai` | Server-rendered HTML cards |
| https://live.stanford.edu/events/calendar | `stanford_live` | JSON `https://live.stanford.edu/api/events/Live` (the Vue calendar's feed). Not fully duplicated in Localist. |
| https://ccrma.stanford.edu/calendar | `ccrma` | Drupal month grid, then each event page |
| https://www.gsb.stanford.edu/events | `gsb` | Drupal HTML rows |
| https://law.stanford.edu/events/ | `law` | The Events Calendar REST `/wp-json/tribe/events/v1/events` |
| https://ed.stanford.edu/events | `gse` | Drupal JSON:API `node/event`, filtered on `field_start_end_datetimes` |
| https://fsi.stanford.edu/events | `fsi` | Drupal JSON:API `node/event`, filtered on `field_event_periods` |
| https://www.hoover.org/events | `hoover` | Drupal JSON:API `node/event`, filtered on `field_date` |
| https://siepr.stanford.edu/events | `siepr` | Stanford Web Services JSON:API view `stanford_events/list_page` |
| https://shc.stanford.edu/stanford-humanities-center/events | `humanities_center` | Drupal HTML rows (`time[datetime]`) |
| https://kipac.stanford.edu/events/upcoming-events | `kipac` | SWS JSON:API view (native events; Localist mirrors skipped) |
| https://qfarm.stanford.edu/events | `qfarm` | SWS JSON:API view |
| https://neuroscience.stanford.edu/events | `neuroscience` | HTML cards with `time[datetime]` |
| https://med.stanford.edu/healthlibrary/lectures-events.html | `health_library` | Prose "LECTURES + EVENTS" list |
| https://aimi.stanford.edu/upcoming-events | `aimi` | SWS JSON:API view |
| https://psychology.stanford.edu/news-events/upcoming-events | `psychology` | H&S JSON:API `node/hs_event` |
| https://statistics.stanford.edu/events/statistics-seminar | `statistics` | H&S JSON:API `node/hs_event` |
| https://physics.stanford.edu/news-events/upcoming-events | `physics` | H&S JSON:API. Rows whose `field_hs_event_link` points at events.stanford.edu are skipped. |
| https://art.stanford.edu/events/calendar-events-exhibitions | `art` | Same H&S JSON:API. Current upcoming rows are Localist links and are skipped. |
| https://bioengineering.stanford.edu/events | `bioengineering` | Same SWS view. The page currently says there are no events, so this source contributes nothing until new ones are published. |
| https://www6.slac.stanford.edu/news-and-events/events/public-lectures | `slac` | HTML cards that include a date. Past "upcoming" cards are dropped by the window. |
| https://www6.slac.stanford.edu/news-and-events/events/seminars-and-conferences | `slac` | Same card parser. The seminars page does not list individual talks; see skipped note below. |

Audience stays `unknown` unless a page or API tag says otherwise. Drupal audience
tags use the same names as Localist (`Everyone` / `General Public` → public;
Students / Faculty / Staff / Members / Alumni without a public tag → Stanford
only). GSE uses `field_event_admission` (`open_to_public`, `gse_community_only`).
"By Invitation Only" stays `unknown`.

## Covered by the Localist main feed

Checked 2026-09-24. The unfiltered `/api/2/events?days=31` feed (9 pages, 450
distinct events) was compared with `venue_id` queries and with `group_id` set
to each department's numeric id (`department_id` is ignored by this API and
returns the unfiltered feed). Every filtered id was already in the main feed,
so these URLs are not fetched again.

Department and venue pages:

- https://events.stanford.edu/department/stanford_live
- https://events.stanford.edu/cantor_arts_center
- https://events.stanford.edu/anderson_collection
- https://events.stanford.edu/memorial_church
- https://events.stanford.edu/dinkelspiel_auditorium
- https://events.stanford.edu/department/department_of_music
- https://events.stanford.edu/department/stanford_jazz_workshop (no events in the window)
- https://events.stanford.edu/department/stvp
- https://events.stanford.edu/department/school_of_engineering
- https://events.stanford.edu/gates_computer_science_building
- https://events.stanford.edu/frost_amphitheater (no events in the window)

Sites whose own listings are Localist mirrors (`su_event_source` or the event
link is `events.stanford.edu`):

- https://www.cs.stanford.edu/events
- https://energy.stanford.edu/news-events/events/upcoming-events
- https://sustainability.stanford.edu/news/events (sampled through the SWS view; every row linked to Localist)
- https://comm.stanford.edu/events

Stanford Live performances that are also on Localist still collapse in dedupe
(`also_sources`). The Live JSON feed above is what adds the rest.

## Skipped

- https://arts.stanford.edu/events/ — Cloudflare challenge (`Just a moment...`), no HTML or JSON feed. Office of the Vice President for the Arts events that are on Localist are already in the main feed.
- https://biox.stanford.edu/events — same Cloudflare challenge. No usable feed.
- https://ee.stanford.edu/research/seminars — names standing seminars and points at a department calendar. Neither `/research/seminars` nor `/events` lists dated talks. No JSON:API.
- https://msande.stanford.edu/get-involved/colloquia-seminars — standing series with weekly times, no dated instances. The SWS `list_page` view is empty.
- https://www6.slac.stanford.edu/news-and-events/events/seminars-and-conferences — no per-talk schedule in the HTML (one Localist calendar link). The card parser still runs in case a dated card appears. Scientific seminars are not a separate feed.

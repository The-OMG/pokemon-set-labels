# Pokemon Set Label Press

Single-page app that renders binder/index labels for every English Pokemon TCG expansion and prints them
either one-per-label on a Phomemo M110 (or any label printer) or as a cut-out sheet on a color printer.

- `public/index.html` – the app. Deployed to Cloudflare Workers (static assets) with `npx wrangler deploy`; also opens straight from disk.
- `public/sets.js` – data snapshot (name, series, type, Bulbapedia set code, abbreviation, sequential expansion number,
  release date, printed + secret card counts, set symbol as data URI, path to logo).
- `public/img/logos/` – set logos (Bulbapedia archives, resized to 1000px, 256-color).
- `pipeline/` – regeneration scripts. Order: `parse_bulba.py` (needs `bulba_expansions.html` fetched from
  Bulbapedia's "List of Pokémon Trading Card Game expansions") → `build_data.py` (needs `sets_p1.json` from
  `https://api.pokemontcg.io/v2/sets?pageSize=250`) → `fetch_images.py` → `make_setsjs.py` (writes `public/`).

Numbering: main-series expansions and special expansions are numbered on separate sequential counters, which
matches the 2023 index-card batch (Legends Awakened 37, Team Up 79, Silver Tempest 94; Dragon Vault special 1).
`docx_abbrs.json` is the abbreviation list from that 2023 batch and drives the "Not yet printed" filter.

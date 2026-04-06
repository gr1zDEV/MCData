# Vanilla Minecraft Item IDs

This repository tracks canonical **vanilla Minecraft Java Edition item IDs** as namespaced identifiers (for example, `minecraft:stone`).

The dataset intentionally uses vanilla registry IDs, **not** Paper/Bukkit `Material` enums.

## Data source strategy

The extraction pipeline uses official Mojang metadata to discover the latest stable release and then derives item IDs from vanilla generated reports:

1. Fetch Mojang version manifest (`version_manifest_v2.json`).
2. Resolve the latest stable Java release.
3. Download that release's vanilla server jar.
4. Run Minecraft's data generator with `--reports`.
5. Read `reports/items.json` and extract all namespaced item IDs.
6. Sort and write deterministic outputs in `data/`.

`reports/items.json` is treated as the primary source of truth for canonical item registry keys.

If Mojang endpoints are temporarily unreachable in an execution environment, the extractor falls back to the `misode/mcmeta` mirror to keep automation operational.

## Repository outputs

- `data/items.json` — pretty-printed JSON array of item IDs.
- `data/items.txt` — one item ID per line.
- `data/items.md` — markdown master list generated from `data/items.json`.
- `data/categories/*.md` — generated category markdown lists (bucketed by first character after `minecraft:`).
- `data/version.json` — release metadata for the current dataset snapshot.

## Automation (GitHub Actions)

Workflows:

- `.github/workflows/update-items.yml` updates raw dataset files (if present in your branch).
- `.github/workflows/sync-categories.yml` regenerates `data/items.md` and `data/categories/*.md` whenever the master list changes.

The category sync workflow can also be run manually with `workflow_dispatch`, and commits only when generated markdown changes.

## Run locally

Requirements:

- Python 3.11+
- Java 21+

Run:

```bash
python tools/extract_items.py
python tools/sync_categories.py
```

This updates files under `data/`, including the markdown master and categorized lists.

## Notes / caveats

- The workflow targets the **latest stable release**, not snapshots.
- If Mojang changes report generation flags/structure, the primary extraction may fail. The script includes a documented mirror fallback for resiliency.
- Item IDs are normalized as lowercase `minecraft:*` namespaced keys and sorted alphabetically for deterministic output.

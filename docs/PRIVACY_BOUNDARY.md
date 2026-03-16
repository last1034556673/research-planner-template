# Privacy Boundary

This public repository is designed so the code can be shared while real research records stay local.

## Tracked in the public repo

- source code
- starter templates
- anonymized demo data
- anonymized screenshots and sample outputs
- documentation

## Not tracked by default

- `workspace/`
- generated local dashboards
- generated local history
- local daily reports
- local calendar exports
- `.app` bundles
- ad hoc export files such as `.ics`

See [`.gitignore`](../.gitignore).

## Demo policy

The demo data under [`examples/wetlab_demo/`](../examples/wetlab_demo/) is hand-curated and synthetic:

- synthetic dates
- generic project names
- generic assay and sample names
- generic calendar labels
- no personal names
- no private paths

## Publishing checklist

Before publishing your own derived repo, verify:

- no absolute home-directory paths remain in tracked files
- no real person names remain in tracked files
- no real calendar names remain in tracked files
- no real experiment identifiers remain in tracked files
- no real history snapshots are tracked

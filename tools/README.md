# Tool index

The supported public entry points are the root `Makefile`,
`bootstrap-deps.sh`, `import-inputs.sh`, `build-munch.sh`, `pack-munch.py` and
`verify-munch.py`. Their tested path is documented in `BUILDING.md`.

The remaining scripts preserve the bring-up workflow:

- `prepare-*` and `package-*` create WinPE, Windows or recovery artifacts from
  files supplied by the user;
- `collect-*` gathers logs without changing the firmware source;
- `analyze-*`, `audit-*` and `check-*` inspect dumps, drivers or hardware
  contracts;
- `tests/` contains host-side regression tests for safety-critical firmware
  logic. They are development tests, not one independent suite: some require
  `make deps`, imported device inputs, generated ACPI, BSP driver files, or
  recovery archives. The supported clean-checkout verification command is
  `make verify` after `make stable`.

Recovery/deployment scripts can write phone partitions and are not invoked by
`make stable`, `make verify`, or the normal temporary boot procedure. Historical
profile numbers in log-analysis filenames are experiment identifiers, not
images that a new user should boot. Never run a write-capable tool without
reading its source and confirming every expected partition identity.


`python3 tools/clean-build.py` previews known generated outputs; `make clean`
validates and removes them. Device inputs, dependency sources, `.git`, `.venv`
and vendor templates are retained.

PEP research starts with `docs/PEP.md`. The retained optional tools are
`audit-kona-pep.py`, `prepare-munch-pep-prep.py` (read-only readiness package)
and `prepare-kona-gpu-bootstrap.py --stage pep` (initial installer scaffolding).
They require the pinned local BSP described there. `make pep` / `make verify-pep`
build and check the unfinished ACPI profile without requiring that BSP.

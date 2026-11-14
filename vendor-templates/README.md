# XBL metadata templates

These files are text-only EDK II INF descriptions used by the local extractor
to identify modules in the exact XBL revision listed in
`inputs/munch/expected-inputs.json`. They contain module names, GUIDs, dependency
expressions and expected output paths, but no Qualcomm/Xiaomi executable code.

The resulting `.efi` and `.depex` files are extracted only from an XBL supplied
by the user, are written below the ignored `inputs/munch/extracted-xbl/` path and
must not be committed or published as project releases. See `THIRD_PARTY.md` for
the repository-wide provenance and redistribution policy.

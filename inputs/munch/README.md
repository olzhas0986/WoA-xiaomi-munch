# Device-owned inputs

This directory intentionally contains no Qualcomm/Xiaomi executable firmware.
The build requires an XBL dump and the live device tree from the tested POCO F4
firmware. Import them with:

```sh
make inputs XBL=/path/to/xbl.img DTB=/path/to/munch-live.dtb
```

The importer accepts only the hashes recorded in `expected-inputs.json`, checks
the DTB model, extracts 91 required modules without patching their bytes, and
keeps every generated file ignored by Git. A different stock firmware revision
must be audited and its addresses revalidated before its hashes are accepted.

The imported files and generated UEFI image remain local build artifacts. This
project does not grant permission to redistribute proprietary modules extracted
from an XBL, so they must not be committed or attached to project releases.

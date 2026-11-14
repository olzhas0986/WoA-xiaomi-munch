# PEP research safety

`make pep` adds the experimental `QCOM2519` ACPI device. It is intended for
driver and ETW analysis only. The corresponding Qualcomm PEP driver has caused
boot loops and multiple bugchecks on this port.

Before testing, keep Android/recovery available, disable automatic Windows
recovery loops, and have an offline method to set the `qcpep` service to
`Start=4`. Never combine a new ACPI table, a new driver package and a binary
patch in the same test: change one variable and collect the generated report.

The `firmware/munch/GpuPep*` directories preserve staged scripts and rollback
logic from the investigation. The LMH patch test is diagnostic evidence, not a
fix. Dumps and ETL files are intentionally excluded because they are large and
may contain private machine data.

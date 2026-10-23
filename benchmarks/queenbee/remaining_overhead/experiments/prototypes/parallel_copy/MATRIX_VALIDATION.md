<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Additional all-precision local validation

`validation/matrix/SUMMARY.json` records PASS for all 15 standard NUMCHECK=10
matrix configurations across double, single and long-double. The 3×2
communication check passed for all three; single and long-double also passed
1×2. The combined three-precision lifecycle test passed at 3×2. Each copied
archive changes only hpx-comm.o, with 31 original members preserved; original
serial/thread/bench libraries, bench objects and driver sources were hash-checked
before and after testing.

The original focused double checks in `validation/SUMMARY.json` were retained,
not rerun. The new double bridge object is byte-identical to the originally
tested object, SHA-256 `26f991862be1f90d13ccc102e1efd849323a5f86f054c11d9fd728de8b11725b`.
Those original numerical checks used 256³, 2×2, one warmup and three samples.
The extended matrix does not replace or reinterpret that record.

Reproduce with the source directory restored to build/qb_remaining/parallel_copy
and the existing original precision builds available. Run
`bash validate_precision.sh build PRECISION` for double, single and long_double,
then `bash validate_combined.sh build`. Run each precision's `test` phase
sequentially, then `bash validate_combined.sh test`. Commands and full logs are
under `validation/matrix/`. Bridge builds use -O3 -DNDEBUG; communication and
combined checkers explicitly retain assertions. All tests used same-workstation
TCP only, at most six runtime workers, coordinated within twelve aggregate
local cores. No remote access or cluster performance claim is part of this
validation. All sources and this documentation are GPL version2 or later;
see the repository COPYING.

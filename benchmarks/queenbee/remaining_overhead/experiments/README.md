<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Remaining-overhead experiment sources and local checks

This directory preserves experiment sources and local correctness evidence.
Cluster performance results are pending in this package. No speedup, winning
implementation, or causal explanation is established by the local tests. The
measured cluster report and downloaded cluster outputs are maintained by the
parent report outside this directory.

The port code, authored tests/scripts and this documentation are licensed under
GNU GPL version 2 or later; see [COPYING](../../../../COPYING). Existing notices
are preserved. Generated configuration files and command/log records are
included as provenance. There are no executables, object files, static/shared
libraries, copied full FFTW trees or symlinks in this package.

## Contents and validation scope

- `candidates/` is the exact prepared 23-file input bundle plus its original
  manifest for candidate job 1125899. It contains seven primary cases and two
  separate diagnostic cases, frozen source copies, the untouched production
  driver, the diagnostic-only driver patch and result checkers. Its README is
  the preparation-time record; submitted/running does not mean passed. Verify
  its original manifest from this directory with
  `sha256sum -c candidates/SHA256SUMS`.
- `prototypes/hybrid/` contains the clean direct-target/pooled-fallback source,
  separate counter source, patches, immutable pool/direct references, ten
  deterministic archive/ownership groups, and complete local command/log/hash
  evidence. Its `validation/SUMMARY.json` records PASS for 15 standard matrix
  calls across double/single/long-double, six communication launches, combined
  precision cleanup/reinitialization, and the unchanged 256³ driver at 2×2,
  two warmups and seven samples.
- `prototypes/parallel_copy/` contains the bounded copy-task source and patch,
  dedicated guard/lifetime/threshold checks, and its original double-precision
  correctness evidence. The original `validation/SUMMARY.json` records copy
  checks at 1×1 and 1×4, communication at 1×2 and 2×2, and the unchanged 256³
  driver at 2×2, **one warmup and three samples**. There is no separately
  instrumented parallel-copy bridge. Its completed additional all-precision matrix is recorded separately under
  `validation/matrix/SUMMARY.json`: 15 standard configurations, five additional
  communication launches and combined precision all passed. The new double
  bridge object is byte-identical to the original focused-test object.
- `prototypes/rendezvous/` contains clean/counter variants and patches relative
  to the corresponding hybrid sources, preparation script, expanded mixed-API
  communication tests, eleven deterministic groups and completed local
  validation. `validation_summary.json` records 15 standard matrix calls,
  per-precision communication checks, combined-precision lifecycle, unchanged
  128³/3×2 and 256³/2×2 numerical runs. `tag_reuse_assessment.md` documents the
  channel metadata-retention limitation separately from numerical correctness.
- `integration_tests/` contains supplementary ordinary-main tests compiled
  against the actual counter-free hybrid and rendezvous bridges, with no
  diagnostic includes or counter dependencies. Both double-precision variants
  passed (10 and 11 groups respectively); their sources, commands, status,
  empty compiler logs and hashes are retained. These supplementary source
  adaptations were not repeated for single/long-double.
- `support/` preserves the shared combined-precision smoke source, the recorded
  local environment exports as data, and generated configuration headers for
  the three original local builds. These configuration headers are provenance,
  not portable replacements for a new machine's configure output.

Prototype preparation-time `PROVENANCE.json` and README status fields are
preserved exactly. Where they describe an unbuilt prototype or narrower test
scope, the explicitly identified final validation summary is authoritative.
Local timings in logs were incidental to correctness checks; the different
local workloads and settings are not a comparative performance campaign.

Every tested archive replacement records the hash of all 32 members and changes
only `hpx-comm.o`. Original core/thread/bench libraries and bench objects are
preserved. Standalone ownership and communication checks retain assertions;
production bridge objects use their recorded release flags. Tests that use real
HPX archive chunk destination selection followed by simulated transport fill
are distinguished from network transfers in their README and test output.

TCP was used only between processes on this workstation. No packaged local
helper authorizes cross-server TCP or QueenBee access. The cluster bundle forces
TCP off and uses the MPI parcelport and UCX `rc,sm,self`. Local builds/tests were
coordinated within the user's aggregate twelve-core limit, with each runtime
campaign using at most six HPX workers. The packaging agent made no QB login.

## Reproducing the local checks

Use a fresh checkout and compatible installed HPX/dependencies. Build the
original double/single/long-double libraries and bench objects first using the
[HPX build instructions](../../../../hpx/README.md). The original archive/input
hashes are retained for comparison; binaries are intentionally not distributed.
Local scripts contain the original build paths and must be restored into the
same repository-relative layout before execution. Do not run them directly
from this evidence directory or overwrite an existing work-in-progress build.

From a fresh repository root, copy the prototype source directories into
`build/qb_remaining/{hybrid,parallel_copy,rendezvous}`. Copy
`support/combined_precision_smoke.cpp` to `build/combined_precision_smoke.cpp`,
and create/adapt `build/hpx_env.sh` for the installed dependencies; the recorded
exports in `support/local_environment.txt` show the environment used here.
For the supplementary clean tests, also restore `integration_tests/` to
`build/qb_remaining/integration_tests`, then use
`bash build/qb_remaining/integration_tests/validate.sh hybrid double` and the
corresponding `rendezvous double` invocation. They use the existing tracked
`hpx/hpx-message-check.hpp`; that header is unchanged and already in this repo.
Archived logs may be copied for reference but their absolute input/output hash
paths describe the original workstation. New builds produce fresh hashes.

Run one distributed test helper at a time because the local launcher uses
shared default ports. Do not exceed twelve total local cores across concurrent
work. The prototype READMEs list their original build/test commands. For hybrid,
run `validate_units.sh build`, then `test`, build each precision with
`validate_precision.sh build PRECISION`, and build the combined checker with
`validate_combined.sh build`; only then run each precision's `test` phase and the
combined `test`. Rendezvous's `validate.sh` preserves its initial bridge/unit/
link/runtime workflow; the precision and combined helpers reproduce its broader
matrix. Do not rerun `prepare.py` over the authored expanded tests: it records
source generation, and its initial test templates are narrower than the final
checks. Parallel-copy's original `validate.sh build` and `test` reproduce its
focused campaign; additional precision helper instructions accompany the final
matrix summary.

The standard matrix uses the unchanged FFTW `check.pl` with NUMCHECK=10 at 1×1,
2×1, 3×1, 4×1 and 3×2 (last with two FFT threads). A successful invocation may
cover multiple generated transforms; a count of matrix calls is not a count of
individual FFTs. Preserve logs containing their exact generated arguments.

## Integrity

`SHA256SUMS` covers every file in this directory except itself.
`PACKAGING_PROVENANCE.json` maps preserved records to their original local
paths. `PATCH_VERIFICATION.json` records reconstruction checks for the frozen
source patches and diagnostic driver. Run `sha256sum -c SHA256SUMS` here to
verify the package. Nested original `input.sha256`/`output.sha256` files record
excluded build artifacts or absolute local paths; they are historical evidence,
not manifests of the published files. Synthetic parser fixtures were not copied;
the small `PREPARATION_CHECKS.txt` explicitly identifies those preparation checks.

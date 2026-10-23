<!--
Copyright (c) 2026 Dominic C. Marcello

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
-->

# Integrated pooled-receive validation

All recorded checks passed against the tracked pooled-receive bridge with
SHA-256 `57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c`.
The source hashes matched before and after the builds and tests.

- Existing double, single, and long-double configurations rebuilt successfully
  using their normal generated Makefiles. Three `make -j2` builds ran together,
  with at most six compiler processes.
- Each precision passed the four deterministic message-check groups and the
  assertion-enabled communication check at 1 locality × 2 workers and
  3 localities × 2 workers. Each communication case completed two init/cleanup
  cycles, including ownership and overlapping-buffer checks.
- Standard double `make -j1 check` passed the upstream serial, pthread, and
  thread-callback numerical checks, followed by the HPX message and
  communication checks and all five standard HPX numerical configurations:
  1×1, 2×1, 3×1, 4×1, and 3×2. Each HPX numerical configuration used the default
  `NUMCHECK=10`.
- The full log places `HPX_MESSAGE_CHECK pooled_receive PASS` before the
  communication check, confirming the new target runs first in `check-local`.

These are local workstation checks through the existing local TCP test
launcher. They do not establish a distributed MPI parcelport result. Runtime
cases ran serially and used at most six workers. No remote login was made for
this validation.

`summary.json` records the results and log line references. Each precision
folder contains exact commands, full text logs, exit statuses, dependency
flags, configuration hashes, and binary hashes. `source_inputs.sha256` uses
paths relative to the repository root; `SHA256SUMS` uses paths relative to
this evidence directory. `BASE_COMMIT` identifies the checkout base before
these uncommitted integration changes; source hashes identify the tested
contents precisely.

`run_validation.sh` is the unchanged execution script copied from
`build/qb_optimize/integration_validation/`. Its relative path calculation
expects that original location and the existing build configurations. The
`.command` files record the actual underlying build and test commands.

After validation, six Automake-generated trailing spaces were removed from
`hpx/Makefile.in`. The source-input manifest identifies the tested generated
file before that whitespace-only cleanup. Transport and test code are unchanged.

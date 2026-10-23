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

# Clean-bridge message checks for integration

Choose `hybrid/hpx-message-check.cpp` or `rendezvous/hpx-message-check.cpp` to accompany the corresponding clean bridge. These are alternatives, not two executables to add to the library. They include the actual `hpx-comm.cpp` and the existing tracked `hpx-message-check.hpp`; the header and current ordinary-main `hpx-message-check` Automake target require no change. Do not link an FFTW HPX library into that target because the source includes its bridge definitions exactly once.

The tests derive from the already validated prototype units. Diagnostic includes, counters, resets and counter assertions have been removed. Behavioral checks still inspect exact destination pointers, payloads and guard regions, reject duplicate claims and wrong byte counts, isolate precision/group/epoch/source/tag/sequence keys, exercise the actual HPX zero-copy input archive, and verify self-copy, overlap boundaries, fallback ownership, exact-size pool reuse, retained largest blocks, late owners and old-epoch wire messages. The rendezvous alternative also checks readiness serialization and rejects a required direct target that is absent. These are deterministic serialization/storage tests; distributed ordering and progress remain covered by the separate communication and numerical checks.

The source has an `NDEBUG` error guard, and the existing Makefile uses `-UNDEBUG` for this target. User `CXXFLAGS` may follow Automake target flags; if they reintroduce `NDEBUG`, the guard fails the build explicitly instead of silently omitting assertions. The local validation script puts `-UNDEBUG` last. Test requirements use exceptions as well.

Run from the repository root:

```sh
build/qb_remaining/integration_tests/validate.sh hybrid double
build/qb_remaining/integration_tests/validate.sh rendezvous double
```

The script also accepts `single` and `long_double` when needed. It selects the original frozen clean source through the include path, uses the existing configured precision header, and links ordinary-main HPX component libraries with `-shared` removed. It neither alters candidate sources nor starts the HPX runtime. Commands, input/output hashes, compiler environment, logs and final status are saved below `validation/<candidate>/<precision>/`.

The clean source inputs are hybrid `5a2446f92d48d69d25f16f2b19202e7e03159aab57397c415c3e31f8592ae0cd` and rendezvous `cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c`. No production bridge, tracked test, build glue or benchmark source was edited for this preparation.

## Completed local validation

Both double-precision clean-source tests compiled with `-O3 -UNDEBUG`, passed all 10 hybrid/all 11 rendezvous test groups, and preserved every recorded input hash. Both compiler logs are empty. At most two compilers ran concurrently; execution used ordinary main without HPX runtime workers or sockets. See `validation_summary.json` and the exact commands/logs under `validation/`. Other precision tests have not been repeated for these new test-source adaptations.

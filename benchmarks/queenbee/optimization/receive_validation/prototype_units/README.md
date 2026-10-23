# Deterministic prototype checks

These standalone sources include their frozen experimental bridge `.cpp`
files. They do not modify or instrument those prototypes. Build one source per
executable with the same HPX/FFTW include paths and dependency link flags used
for the corresponding prototype. Each defines ordinary `main` and uses HPX
serialization archives without starting an HPX runtime. Do not explicitly link
a second bridge object; an archive can be linked normally because the included
bridge already provides its communication symbols.

All source files carry the complete GPL version 2 or later notice. The checks
use exceptions rather than C assertions, so `NDEBUG` does not disable them.
The parent subsequently authorized local compilation and execution with at
most two concurrent compilers. Both programs compiled and passed against the
existing double-precision configuration and HPX component flags. Complete
commands, input/output hashes, compiler/environment details, and test logs are
under `results/direct_receive/` and `results/pooled_receive/`; `results/summary.json`
records the result. A missing closing brace in the pool test source was fixed
after its first compile attempt; that diagnostic is preserved. Neither frozen
prototype changed.

Reproduce with `bash run_one.sh build direct_receive`, then
`bash run_one.sh test direct_receive`, and the corresponding `pooled_receive`
commands. The script loads the existing `build/hpx_env.sh`, uses the double
configuration and HPX component package flags, and removes only `-shared`
for the ordinary-main executable. No FFTW archive was needed for linking.

`direct_receive_units.cpp` tests:

- Real HPX archive deserialization into exactly the registered user address,
  including guard bytes, payload contents, source reuse, and rejection of a
  second claim.
- Owned fallback that outlives the source, serialized archive, and original
  Message while another shared Message remains alive.
- A byte-count mismatch throws before modifying or consuming the target.
- Precision/group/epoch/source/tag/sequence mismatches cannot claim a posted
  target. The exact matching key remains usable afterward.
- A real chunked HPX archive with `allow_zero_copy_receive` exports the exact
  posted destination for its payload chunk, leaving the destination unchanged
  until a simulated transport write fills it. This proves the archive branch;
  it is not an actual MPI transfer test.
- Empty messages, self-copy source independence, and exact, partial,
  contained, adjacent, reversed, and zero-length overlap boundaries.

`pooled_receive_units.cpp` tests:

- Real Message deserialization cannot recycle storage while another Message
  owns it, then does reuse the same address after the last owner releases it.
- Allocation misses, exact-size hits, equal-size returns, retention of a larger
  idle block, and replacement of a smaller idle block.
- Cleanup leaves live payload contents intact, lets the old pool expire after
  its last owner, and prevents both late releases and delayed serialized
  old-epoch messages from replacing a new epoch's cached block.
- Self-copy independence and exclusion of zero-byte messages from cache reuse.

The explicit precision namespaces are selected by the prototype's usual
`FFTW_SINGLE` or `FFTW_LDOUBLE` flags. Group-key isolation checks use different
precision prefixes; they do not replace the combined-precision executable
check or multi-locality transport tests.

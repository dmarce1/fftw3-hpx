# fftw3-hpx: build instructions for an implementing agent

You are to produce **fftw3-hpx**: FFTW 3.3.11's distributed-memory library
(`mpi/`) with every MPI call replaced by an HPX equivalent, plus HPX threads in
place of FFTW's pthreads/OpenMP workers. Read this whole file before starting.

## 1. Goal and non-goals

**Goal.** A library `libfftw3_hpx` (and `libfftw3f_hpx`, `libfftw3l_hpx`) with
the same algorithms, data distributions, planner behaviour and numerical results
as `libfftw3_mpi`, where one FFTW "process" is one HPX locality, communication
uses HPX collectives and channels, and FFTW's threaded loops run on HPX threads.

**Non-goals. Do not do any of these:**

- Do not improve, optimize, or restructure anything. No algorithm, schedule,
  block-distribution, planner, flag, or numerical change. No zero-copy work, no
  overlap of communication and computation. Plain copies into HPX payloads are
  correct and expected.
- Do not modify anything under `kernel/`, `dft/`, `rdft/`, `reodft/`, `simd-support/`,
  `threads/`, `api/`, `genfft/`, or `mpi/`. The only edits outside the new `hpx/`
  directory are build glue (section 9).
- Do not use FFTW's GitHub repository, OCaml, `genfft`, or maintainer mode.
- Do not port the Fortran 2003 interface (`f03-wrap.c`, `*.f03.in`). Leave it out.
- Do not use FFTW's CMake build; it cannot build `mpi/`. Use autotools.

## 2. Standing rules from the user (mandatory)

- **Local machine only.** Do not connect to QB4 (`qbd.loni.org`) or any other
  cluster by any means. Cluster access is paused by the user.
- **Core budget.** Builds and tests together use at most 12 cores (`make -j12`
  or less; HPX localities × threads per locality ≤ 12). Other sessions share
  this budget, so check `uptime` first and use fewer cores if the machine is busy.
- **Branch names** are snake_case, never hyphens (e.g. `hpx_port`).
- **New C++ code** places `const` to the right of the type: `int const`,
  `T const &`, `char * const`. Do not restyle FFTW's existing C code.
- **No outward actions** (pushing, opening PRs or issues, emailing FFTW
  maintainers) without the user's explicit approval.

## 3. Source

Use the official release tarball, which contains the generated codelets:

- URL: `https://fftw.org/fftw-3.3.11.tar.gz`
- SHA256: `5630c24cdeb33b131612f7eb4b1a9934234754f9f388ff8617458d0be6f239a1`

Verify the hash before extracting. Extract into a fresh empty directory, never
into a directory containing your own scripts.

## 4. Repository and workflow

Work in `/home/dmarce1/workspace/fftw3_hpx` (this file's directory).

1. `git init`. First commit: the pristine tarball contents only (strip the
   `fftw-3.3.11/` prefix), message `Import FFTW 3.3.11 release tarball`. This
   commit is the upstream baseline that every later diff is measured against.
2. Second commit: `cp -a mpi hpx`, unmodified, message
   `Copy mpi/ to hpx/ as the starting point for the HPX port`.
3. All further work goes in small commits on top. `git diff <baseline> -- mpi`
   must stay empty, and `diff -ru mpi hpx` must show only the MPI-to-HPX
   replacement, renames, notices, and build changes.
4. Commit `INSTRUCTIONS.md` separately, or leave it untracked; never fold it
   into the baseline commit.

## 5. Execution model

- **Rank = locality.** FFTW rank *r* is HPX locality *r*
  (`hpx::get_locality_id()`), communicator size is
  `hpx::get_num_localities(hpx::launch::sync)`. Threads within a locality come
  from FFTW's thread layer (section 8).
- **SPMD.** Every locality calls the same `fftw_hpx_*` functions on the same
  communicator in the same order, from an HPX thread. This is the same rule MPI
  imposes. Applications run `hpx_main` on all localities
  (`hpx.run_hpx_main!=1` in the config, or `--hpx:run-hpx-main`). HPX's own
  collectives unit tests (`libs/full/collectives/tests/unit/` in the HPX source)
  use this pattern; copy their startup and `hpx::finalize()` handling.
- **Large stacks.** FFTW places buffers of up to `MAX_STACK_ALLOC` = 64 KiB on
  the stack with `alloca` (`kernel/ifftw.h:210`), on top of codelet frames.
  HPX's default thread stacks can be smaller than that. Every HPX thread that
  runs FFTW code must use `hpx::threads::thread_stacksize::large`. That applies
  to the jobs spawned in section 8, and to the thread that plans and executes
  (tests and documentation must launch FFTW work on a large-stack executor).
- **Planning is collective.** `hpx/api.c` installs planner hooks (`cost_hook`,
  `wisdom_ok_hook`, `nowisdom_hook`, `bogosity_hook`) that run an allreduce or
  broadcast on every timing measurement, so that all localities choose the same
  plan. Keep them exactly as they are; they are why the collective call
  sequence is identical on every locality.

## 6. Public API

Rename the public prefix from `mpi_` to `hpx_` in two places, so that every
function name follows automatically:

- `hpx/ifftw-hpx.h` (from `ifftw-mpi.h`): `#define XM(name) X(CONCAT(hpx_, name))`
- `hpx/fftw3-hpx.h` (from `fftw3-mpi.h`): the `FFTW_MPI_MANGLE_*` macros become
  `FFTW_HPX_MANGLE_*` using `FFTW_CONCAT(hpx_,name)`; `FFTW_MPI_DEFINE_API`
  becomes `FFTW_HPX_DEFINE_API`. Rename the header guard.

Result: `fftw_hpx_init`, `fftw_hpx_plan_many_dft`, `fftw_hpx_local_size_many`,
`fftwf_hpx_*`, `fftwl_hpx_*`, and so on. Keep the `FFTW_MPI_DEFAULT_BLOCK`,
`FFTW_MPI_SCRAMBLED_*`, `FFTW_MPI_TRANSPOSED_*` flag names as
`FFTW_HPX_*` equivalents with identical values.

Replace `MPI_Comm` in the public API with an opaque handle declared once in
`fftw3-hpx.h`, outside the per-precision macro:

```c
typedef struct fftw_hpx_comm_s *fftw_hpx_comm;
#define FFTW_HPX_COMM_NULL ((fftw_hpx_comm) 0)
```

Add, per precision, `fftw_hpx_comm XM(comm_world)(void)` returning the
library-owned world communicator (valid between `XM(init)` and `XM(cleanup)`;
callers never free it). A handle belongs to the precision library that created
it. No other communicator constructors are public for now.

`XM(init)()` must be called on every locality, on a large-stack HPX thread,
before any other FFTW call. It does, in order: `X(init_threads)()`, installs
the HPX thread callback (section 8), creates the world group (collective), then
does everything the original `fftw_mpi_init` did. `XM(cleanup)()` is called on
every locality before `hpx::finalize()`, and releases all groups.

## 7. Communication layer

Write one C header and one C++ file:

- `hpx/hpx-comm.h`: C-callable declarations, included by `ifftw-hpx.h` in place
  of `<mpi.h>`. Must compile as C and C++.
- `hpx/hpx-comm.cpp`: the implementation. Include only `config.h`, `hpx-comm.h`,
  standard headers, and HPX headers. **Never include FFTW's internal C headers
  from C++.** Pass raw pointers, element counts, and `sizeof(R)` instead.

All exported symbols are mangled per precision like the rest of FFTW
(`fftw_hpx_*`, `fftwf_hpx_*`, `fftwl_hpx_*`). Use `FFTW_SINGLE` and
`FFTW_LDOUBLE` from `config.h` to pick the prefix in C++. HPX communicator
basenames start with the same mangled prefix (e.g. `fftwf_hpx/world`) so that
two precision libraries in one program never collide.

### 7.1 Communicator model

A handle points to a refcounted **group**:

```text
group:  basename, rank, size, world ranks of the members,
        hpx::collectives::communicator      (collectives)
        hpx::collectives::channel_communicator (point-to-point)
        generation counter, split counter, per-peer send/recv sequence numbers
handle: shared ownership of one group
```

- **World group**: created in `XM(init)` with
  `create_communicator(basename, num_sites_arg(size), this_site_arg(rank))` and
  `create_channel_communicator(hpx::launch::sync, ...)` with the same arguments.
  Do **not** use `hpx::collectives::get_world_communicator()`: its generation
  numbers are shared with whatever else the application does on it.
- **Generations**: every collective on a group passes
  `generation_arg(++group.generation)`, starting at 1. All members advance the
  counter identically because they issue the same collectives in the same order.
- **`MPI_Comm_dup` → share the group.** FFTW dups the communicator for every
  problem and plan it creates (`*-problem.c`, `transpose-alltoall.c`,
  `transpose-pairwise.c`) and frees it on destroy. Planning creates thousands of
  problems. A dup must therefore return a new handle to the **same** group with
  no HPX call. This is safe because FFTW's collectives on a group are issued
  sequentially and identically on every member.
- **`MPI_Comm_free` → release the handle.**
- **`MPI_Comm_split(comm, color, key)`** (`transpose-recurse.c:240,251`,
  `wisdom-api.c:57`): `all_gather` the `(color, key)` pairs over the parent;
  members of a colour are ordered by `(key, parent rank)`, which gives the new
  rank and size. Look the result up in a per-locality cache keyed by
  `(parent basename, colour, ordered member list)`. On a miss, create the group
  with basename `<parent>/c<colour>/<hash of member list>`. Keep cached groups
  alive until `XM(cleanup)`. Every member reaches the same hit or miss because
  they all took part in the same splits. FFTW never passes `MPI_UNDEFINED`.
- **Groups of size 1** may skip HPX entirely and copy locally; the results are
  identical.

### 7.2 Call-by-call mapping

Line numbers refer to FFTW 3.3.11 `mpi/`. Buffers are bytes; `R`-typed data is
`count * sizeof(R)` bytes. `FFTW_MPI_TYPE`, `FFTW_MPI_SIZE_T` and
`FFTW_MPI_PTRDIFF_T` disappear.

| MPI call | Used in | HPX replacement |
|---|---|---|
| `MPI_Comm_size`, `MPI_Comm_rank` | throughout | group `size`, `rank` |
| `MPI_Comm_dup`, `MPI_Comm_free` | problems, plans | section 7.1 |
| `MPI_Comm_split` | `transpose-recurse.c`, `wisdom-api.c` | section 7.1 |
| `MPI_Allreduce` LOR, LAND (int) | `any-true.c:36,56`, `api.c:106` | `all_reduce(hpx::launch::sync, comm, value, std::logical_or<>{} / std::logical_and<>{}, this_site_arg, generation_arg)`; return `int` 0 or 1 |
| `MPI_Allreduce` SUM or MAX (double) | `api.c:60` (`cost_hook`) | `all_reduce` with `std::plus<>` or a max function |
| `MPI_Bcast` | `any-true.c:53`, `api.c:100`, `wisdom-api.c:97-108` | root: `broadcast_to(comm, std::vector<char>, ...)`; others: `broadcast_from<std::vector<char>>(comm, ...)`; copy into the buffer. FFTW always uses root 0; assert it |
| `MPI_Alltoall`, `MPI_Alltoallv` | `transpose-alltoall.c:61-78` | build one `std::vector<char>` per destination from the send counts and offsets, call `all_to_all(hpx::launch::sync, comm, std::move(blocks), this_site_arg, generation_arg)`, copy block *s* to the receive offset for source *s*; assert each size matches the receive count |
| `MPI_Sendrecv` | `transpose-pairwise.c:72,89` | start `set(channel, that_site_arg(dest), payload, tag_arg(t))`, then `get<std::vector<char>>(channel, that_site_arg(source), tag_arg(t)).get()`, then wait for the `set`. Start the send before the receive or pairs deadlock. FFTW skips self-exchange itself |
| `MPI_Send`, `MPI_Recv` | `wisdom-api.c:65-72` | channel `set` (then wait) and `get` |
| `MPI_Abort` | `wisdom-api.c:74,101` | `hpx::terminate()` |
| `MPI_Status`, `MPI_COMM_NULL` | `transpose-pairwise.c`, `api.c` | remove; `FFTW_HPX_COMM_NULL` |

**Message ordering.** MPI guarantees that messages with the same source, tag
and communicator arrive in send order. FFTW reuses tags
(`(my_pe * n_pes + pe) & 0x7fff`) on every execution. Fold a per-peer sequence
number into the HPX tag (sender increments `sendSeq[dest]`, receiver
`recvSeq[source]`) so that matching never depends on whether HPX channels are
FIFO.

## 8. Threading: HPX futures through `fftw_threads_set_callback`

Do not touch `threads/`. FFTW 3.3.9 and later route every threaded loop through
a user callback (`X(threads_set_callback)`, `api/fftw3.h:395`). When it is set,
the pthread pool never starts. Implement the callback in `hpx-comm.cpp` with
**a `std::vector` of `hpx::async` futures and `hpx::wait_all`** (the user's
choice; do not use `for_loop` or parallel algorithms). Run the last job inline
on the calling thread, as FFTW's own `threads.c` does:

```cpp
namespace
{
void runJobs(void *(*work)(char *), char * const jobData, std::size_t const elementSize,
             int const jobCount)
{
    hpx::execution::parallel_executor const executor(hpx::threads::thread_stacksize::large);
    std::vector<hpx::future<void>> futures;
    futures.reserve(static_cast<std::size_t>(jobCount - 1));
    for (int job = 0; job < jobCount - 1; ++job)
    {
        char * const data = jobData + static_cast<std::size_t>(job) * elementSize;
        futures.push_back(hpx::async(executor, [work, data] { work(data); }));
    }
    work(jobData + static_cast<std::size_t>(jobCount - 1) * elementSize);
    hpx::wait_all(futures);
}
}    // namespace

// Exported with the per-precision name XM(parallel_loop).
extern "C" void parallelLoop(void *(*work)(char *), char *jobData, std::size_t elementSize,
                             int jobCount, void *)
{
    if (jobCount <= 0)
    {
        return;
    }
    if (hpx::threads::get_self_ptr() == nullptr)
    {
        hpx::run_as_hpx_thread([&] { runJobs(work, jobData, elementSize, jobCount); });
        return;
    }
    runJobs(work, jobData, elementSize, jobCount);
}
```

`XM(init)` (C, in `hpx/api.c`) calls `X(init_threads)()` and then
`X(threads_set_callback)(XM(parallel_loop), 0)`. Users still choose the thread
count with `fftw_plan_with_nthreads`; about `hpx::get_os_thread_count()` is
sensible. Nested `spawn_loop` calls work without special handling. The snippet
has not been compiled; check it against the installed HPX headers.

## 9. Build system (autotools)

HPX to use: **HPX 1.11.0 at `/home/dmarce1/local/hpx/Release`**, which provides
`lib/pkgconfig/hpx_component.pc` (libraries), `hpx_application.pc` (programs),
and `bin/hpxrun.py`. Its flags include `-std=c++20`. It was built with the TCP
and MPI parcelports, so `libhpx` itself links MPI; that is fine, but
fftw3-hpx's own sources must not include `mpi.h` or call MPI.

- `configure.ac`
  - Add `AC_PROG_CXX` before `AC_PROG_LIBTOOL`/`LT_INIT` (lines 314-315).
  - Add `--enable-hpx` next to `--enable-mpi` (line 322). Error out for quad
    precision (as MPI does) and when `--enable-threads` is not also given.
  - Find HPX with `PKG_CHECK_MODULES([HPX], [hpx_component])` and
    `PKG_CHECK_MODULES([HPX_APP], [hpx_application])` (`pkg.m4` is in
    `/usr/share/aclocal`). Users set `PKG_CONFIG_PATH`.
  - Find `hpxrun.py` with `AC_PATH_PROG` and substitute it.
  - `AM_CONDITIONAL([HPX], ...)`; add `hpx/Makefile` to `AC_CONFIG_FILES`.
- Top-level `Makefile.am`: add `hpx` to `SUBDIRS` next to `mpi` (line 43).
- `hpx/Makefile.am`, derived from `mpi/Makefile.am`:
  - library `libfftw3@PREC_SUFFIX@_hpx.la`, header `fftw3-hpx.h`, everything
    inside `if HPX`;
  - sources as for MPI, minus `f03-wrap.c`, plus `hpx-comm.h` and
    `hpx-comm.cpp`; automake then links with the C++ linker;
  - normal `CC` (not `MPICC`); `AM_CXXFLAGS = $(HPX_CFLAGS)`;
  - `LIBADD = ../libfftw3@PREC_SUFFIX@.la ../threads/libfftw3@PREC_SUFFIX@_threads.la $(HPX_LIBS)`
    (or nothing extra for threads when `COMBINED_THREADS`);
  - drop every Fortran and `C_MPI_FINT` rule.
- Regenerate with `autoreconf -fi` (autoconf, automake 1.18.1 and libtool are
  installed). Do not pass `--enable-maintainer-mode`.
- A plain `./configure && make` without `--enable-hpx` must still build stock
  FFTW, unchanged.
- FFTW PR #341 (https://github.com/FFTW/fftw3/pull/341, an unmerged HPX
  *threads* backend) has HPX detection in `configure.ac` you may read for
  reference. Its code is GPL like FFTW, so reuse is allowed, but its threading
  approach is not what we want.

## 10. Test program

Port `mpi/mpi-bench.c` to `hpx/hpx-bench.c` with the same verification logic.
It additionally uses `MPI_Gather`, `MPI_Gatherv`, `MPI_Scatterv`,
`MPI_Init_thread` and `MPI_Finalize`; add bench-only `gather`, `gatherv` and
`scatterv` bridge functions built on the HPX gather and scatter collectives (or
on `all_gather`). Rename its C `main` and add a small `hpx/hpx-bench-main.cpp`
that starts HPX with `hpx_main` on every locality, runs the bench on a
large-stack HPX thread, and finalizes correctly.

`check-local` mirrors the MPI checks, replacing `$(MPIRUN) -np N` with
`hpxrun.py -l N -t T -p tcp -r none`. Read `tests/check.pl` to see how it
appends the program's arguments to the `--mpi` command; if the `--` separator
that `hpxrun.py` requires does not fit, use a small wrapper script in `hpx/`.

## 11. Acceptance criteria

All of these, in double, single (`--enable-float`) and long double
(`--enable-long-double`) builds configured with `--enable-hpx --enable-threads`:

1. `make check` in `hpx/` passes on 1, 2, 3 and 4 localities with 1 thread
   each, and on 3 localities with 2 threads each (the same matrix as FFTW's MPI
   checks). Non-power-of-two locality counts are required.
2. `make bigcheck` in `hpx/` passes at least once in double precision.
3. Top-level serial `make check` still passes.
4. `grep -rn 'MPI_\|mpi\.h' hpx/` finds only comments and notices.
5. `git diff <baseline> -- mpi kernel dft rdft reodft threads api genfft`
   is empty.
6. No hangs: every run finishes, including `FFTW_MEASURE` planning and the
   wisdom gather/broadcast functions.

## 12. Licence obligations (FFTW is GPL v2 or later)

- Keep `COPYING`, `COPYRIGHT`, `AUTHORS` and every existing copyright notice.
- Every file under `hpx/` that came from `mpi/` gets a line under its existing
  copyright notice:
  `Modified 2026 by Dominic C. Marcello: MPI communication replaced with HPX.`
- New files (`hpx-comm.h`, `hpx-comm.cpp`, `hpx-bench-main.cpp`, wrapper scripts)
  carry `Copyright (c) 2026 Dominic C. Marcello` with FFTW's GPL v2-or-later
  notice text.
- Add a `NEWS`/`README` section describing fftw3-hpx and the date of the change.
- Do not add any other licence. The user may later license their own new files
  under Boost as well; that decision is theirs, so ask rather than doing it.

## 13. Report back

When finished, report: the commit list; `diff -ru mpi hpx --stat`; the exact
configure and test commands you ran with their pass/fail output; anything from
sections 5-8 that did not behave as described here (stack size, generation
rules, channel ordering, `hpxrun.py` arguments); and any deviation from these
instructions, with the reason.
# Modified 2026 by Dominic C. Marcello: MPI communication replaced with HPX.

# fftw3-hpx.h includes the installed public header "fftw3.h".
AM_CPPFLAGS = -I $(top_srcdir) -I $(top_srcdir)/api

EXTRA_DIST = testsched.c hpx-run.sh README.md VALIDATION.md .clang-format

if HPX
lib_LTLIBRARIES = libfftw3@PREC_SUFFIX@_hpx.la
include_HEADERS = fftw3-hpx.h
noinst_PROGRAMS = hpx-bench hpx-comm-check

AM_CXXFLAGS = $(HPX_CFLAGS)

TRANSPOSE_SRC = transpose-alltoall.c transpose-pairwise.c transpose-recurse.c transpose-problem.c transpose-solve.c hpx-transpose.h
DFT_SRC = dft-serial.c dft-rank-geq2.c dft-rank-geq2-transposed.c dft-rank1.c dft-rank1-bigvec.c dft-problem.c dft-solve.c hpx-dft.h
RDFT_SRC = rdft-serial.c rdft-rank-geq2.c rdft-rank-geq2-transposed.c rdft-rank1-bigvec.c rdft-problem.c rdft-solve.c hpx-rdft.h
RDFT2_SRC = rdft2-serial.c rdft2-rank-geq2.c rdft2-rank-geq2-transposed.c rdft2-problem.c rdft2-solve.c hpx-rdft2.h
SRC = any-true.c api.c block.c choose-radix.c conf.c dtensor.c fftw3-hpx.h ifftw-hpx.h rearrange.c wisdom-api.c hpx-comm.h hpx-comm.cpp

libfftw3@PREC_SUFFIX@_hpx_la_SOURCES = $(SRC) $(TRANSPOSE_SRC) $(DFT_SRC) $(RDFT_SRC) $(RDFT2_SRC)
libfftw3@PREC_SUFFIX@_hpx_la_LDFLAGS = -version-info @SHARED_VERSION_INFO@

if !COMBINED_THREADS
LIBFFTWTHREADS = $(top_builddir)/threads/libfftw3@PREC_SUFFIX@_threads.la
endif

libfftw3@PREC_SUFFIX@_hpx_la_LIBADD = $(LIBFFTWTHREADS) ../libfftw3@PREC_SUFFIX@.la $(HPX_LIBS) $(THREADLIBS)

hpx_bench_CFLAGS = $(PTHREAD_CFLAGS)
hpx_bench_CXXFLAGS = $(HPX_APP_CFLAGS)
hpx_bench_SOURCES = hpx-bench.c hpx-bench-main.cpp $(top_srcdir)/tests/fftw-bench.c $(top_srcdir)/tests/hook.c
hpx_bench_LDADD = libfftw3@PREC_SUFFIX@_hpx.la $(LIBFFTWTHREADS) $(top_builddir)/libfftw3@PREC_SUFFIX@.la $(top_builddir)/libbench2/libbench2.a $(HPX_APP_LIBS) $(THREADLIBS)

hpx_comm_check_CXXFLAGS = $(HPX_APP_CFLAGS)
hpx_comm_check_SOURCES = hpx-comm-check.cpp
hpx_comm_check_LDADD = libfftw3@PREC_SUFFIX@_hpx.la $(LIBFFTWTHREADS) $(top_builddir)/libfftw3@PREC_SUFFIX@.la $(HPX_APP_LIBS) $(THREADLIBS)

CHECK = $(top_srcdir)/tests/check.pl
NUMCHECK = 10
CHECKSIZE = 10000
CHECKOPTS = --verbose --random --maxsize=$(CHECKSIZE) -c=$(NUMCHECK) $(CHECK_PL_OPTS)
HPX_RUN = $(SHELL) $(srcdir)/hpx-run.sh "$(HPXRUN)"

check-local: hpx-bench$(EXEEXT) hpx-comm-check$(EXEEXT)
	$(HPX_RUN) 3 2 "$(abs_builddir)/hpx-comm-check$(EXEEXT)"
	perl -w $(CHECK) $(CHECKOPTS) --mpi '$(HPX_RUN) 1 1 "$(abs_builddir)/hpx-bench$(EXEEXT)"'
	@echo "HPX FFTW transforms passed $(NUMCHECK) tests, 1 locality, 1 thread"
	perl -w $(CHECK) $(CHECKOPTS) --mpi '$(HPX_RUN) 2 1 "$(abs_builddir)/hpx-bench$(EXEEXT)"'
	@echo "HPX FFTW transforms passed $(NUMCHECK) tests, 2 localities, 1 thread each"
	perl -w $(CHECK) $(CHECKOPTS) --mpi '$(HPX_RUN) 3 1 "$(abs_builddir)/hpx-bench$(EXEEXT)"'
	@echo "HPX FFTW transforms passed $(NUMCHECK) tests, 3 localities, 1 thread each"
	perl -w $(CHECK) $(CHECKOPTS) --mpi '$(HPX_RUN) 4 1 "$(abs_builddir)/hpx-bench$(EXEEXT)"'
	@echo "HPX FFTW transforms passed $(NUMCHECK) tests, 4 localities, 1 thread each"
	perl -w $(CHECK) $(CHECKOPTS) --mpi --nthreads=2 '$(HPX_RUN) 3 2 "$(abs_builddir)/hpx-bench$(EXEEXT)"'
	@echo "HPX FFTW threaded transforms passed $(NUMCHECK) tests, 3 localities, 2 threads each"

bigcheck: hpx-bench$(EXEEXT)
	$(MAKE) $(AM_MAKEFLAGS) NUMCHECK=100 CHECKSIZE=60000 check-local

smallcheck: hpx-bench$(EXEEXT)
	$(MAKE) $(AM_MAKEFLAGS) NUMCHECK=2 check-local
endif

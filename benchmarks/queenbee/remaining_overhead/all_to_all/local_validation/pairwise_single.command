timeout --kill-after=10s 900s env FFTW_HPX_TRANSPOSE_EXCHANGE=pairwise make -j1 -C build/single/hpx smallcheck 

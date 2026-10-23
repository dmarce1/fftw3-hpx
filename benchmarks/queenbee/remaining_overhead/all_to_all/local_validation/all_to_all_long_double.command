timeout --kill-after=10s 900s env FFTW_HPX_TRANSPOSE_EXCHANGE=all_to_all make -j1 -C build/long_double/hpx check 

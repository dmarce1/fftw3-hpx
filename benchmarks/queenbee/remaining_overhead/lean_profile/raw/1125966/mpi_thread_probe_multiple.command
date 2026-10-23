cd /work/dmarce1/fftw3_hpx_remaining_20261023
/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install/bin/mpiexec -n 4 --map-by ppr:1:node --bind-to none /usr/bin/numactl --interleave=all env OMPI_MPI_THREAD_LEVEL=3 /work/dmarce1/fftw3_hpx_remaining_20261023/results/1125966/bin/mpi_thread_probe --expect-multiple 

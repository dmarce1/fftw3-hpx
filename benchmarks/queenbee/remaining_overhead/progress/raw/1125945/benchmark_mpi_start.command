cd /work/dmarce1/fftw3_hpx_remaining_20261023
/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install/bin/mpiexec -n 4 --map-by ppr:1:node --bind-to none /usr/bin/numactl --interleave=all /work/dmarce1/fftw3_hpx_optimize_20261022/results/1125395/bin/mpi --size=1024 --threads=64 --warmups=2 --samples=7 

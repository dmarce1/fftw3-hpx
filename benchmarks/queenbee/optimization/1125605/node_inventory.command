cd /work/dmarce1/fftw3_hpx_optimize_20261022
srun --mpi=none --nodes=4 --ntasks=4 --ntasks-per-node=1 --cpus-per-task=1 --label sh -c hostname\;\ uname\ -a\;\ lscpu\;\ numactl\ --show 

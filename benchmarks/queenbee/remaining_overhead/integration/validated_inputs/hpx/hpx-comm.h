/*
 * Copyright (c) 2026 Dominic C. Marcello
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

#ifndef FFTW_HPX_COMM_H
#define FFTW_HPX_COMM_H

#include <stddef.h>

#include "fftw3-hpx.h"

#if defined(FFTW_SINGLE)
#define FFTW_HPX_COMM_FN(name) FFTW_CONCAT(fftwf_hpx_, name)
#elif defined(FFTW_LDOUBLE)
#define FFTW_HPX_COMM_FN(name) FFTW_CONCAT(fftwl_hpx_, name)
#else
#define FFTW_HPX_COMM_FN(name) FFTW_CONCAT(fftw_hpx_, name)
#endif

#ifdef __cplusplus
extern "C"
{
#endif

    enum
    {
        FFTW_HPX_LOR,
        FFTW_HPX_LAND,
        FFTW_HPX_SUM,
        FFTW_HPX_MAX
    };

    void FFTW_HPX_COMM_FN(comm_init)(void);
    void FFTW_HPX_COMM_FN(comm_cleanup)(void);
    fftw_hpx_comm FFTW_HPX_COMM_FN(comm_world)(void);
    void FFTW_HPX_COMM_FN(comm_rank)(fftw_hpx_comm, int *);
    void FFTW_HPX_COMM_FN(comm_size)(fftw_hpx_comm, int *);
    void FFTW_HPX_COMM_FN(comm_dup)(fftw_hpx_comm, fftw_hpx_comm *);
    void FFTW_HPX_COMM_FN(comm_free)(fftw_hpx_comm *);
    void FFTW_HPX_COMM_FN(comm_split)(fftw_hpx_comm, int, int, fftw_hpx_comm *);

    int FFTW_HPX_COMM_FN(allreduce_int)(int, int, fftw_hpx_comm);
    double FFTW_HPX_COMM_FN(allreduce_double)(double, int, fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(bcast)(void *, size_t, size_t, int, fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(alltoall)(void const *, size_t, size_t, void *, size_t, size_t,
                                    fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(alltoallv)(void const *, int const *, int const *, size_t, void *,
                                     int const *, int const *, size_t, fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(send)(void const *, size_t, size_t, int, int, fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(recv)(void *, size_t, size_t, int, int, fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(sendrecv)(void const *, size_t, size_t, int, int, void *, size_t, size_t,
                                    int, int, fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(abort)(fftw_hpx_comm, int);

    void FFTW_HPX_COMM_FN(parallel_loop)(void *(*)(char *), char *, size_t, int, void *);

    /* Helpers used only by the distributed verification program. */
    void FFTW_HPX_COMM_FN(bench_gather)(void const *, size_t, size_t, void *, size_t, size_t, int,
                                        fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(bench_gatherv)(void const *, size_t, size_t, void *, int const *,
                                         int const *, size_t, int, fftw_hpx_comm);
    void FFTW_HPX_COMM_FN(bench_scatterv)(void const *, int const *, int const *, size_t, void *,
                                          size_t, size_t, int, fftw_hpx_comm);

#ifdef __cplusplus
}
#endif

#endif

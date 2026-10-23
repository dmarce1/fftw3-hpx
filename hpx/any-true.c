/*
 * Copyright (c) 2003, 2007-14 Matteo Frigo
 * Copyright (c) 2003, 2007-14 Massachusetts Institute of Technology
 * Modified 2026 by Dominic C. Marcello: MPI communication replaced with HPX.
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
 *
 */

#include "ifftw-hpx.h"

/* During planning, if any process fails to create a plan then
   all of the processes must fail.  This synchronization is implemented
   by the following routine.

   Instead of 
        if (failure) goto nada;
   we instead do:
        if (any_true(failure, comm)) goto nada;
*/

int XM(any_true)(int condition, fftw_hpx_comm comm)
{
     int result;
     result = XM(allreduce_int)(condition, FFTW_HPX_LOR, comm);
     return result;
}

/***********************************************************************/

#if defined(FFTW_DEBUG)
/* for debugging, we include an assertion to make sure that
   HPX problems all produce equal hashes, as checked by this routine: */

int XM(md5_equal)(md5 m, fftw_hpx_comm comm)
{
     unsigned long s0[4];
     int i, eq_me, eq_all;

     X(md5end)(&m);
     for (i = 0; i < 4; ++i) s0[i] = m.s[i];
     XM(bcast)(s0, 4, sizeof(unsigned long), 0, comm);
     for (i = 0; i < 4 && s0[i] == m.s[i]; ++i) ;
     eq_me = i == 4;
     eq_all = XM(allreduce_int)(eq_me, FFTW_HPX_LAND, comm);
     return eq_all;
}
#endif

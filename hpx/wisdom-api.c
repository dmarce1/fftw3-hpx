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

#include "fftw3-hpx.h"
#include "ifftw-hpx.h"
#include <string.h>


/* Import wisdom from all processes to process 0, as prelude to
   exporting a single wisdom file (this is convenient when we are
   running on identical processors, to avoid the annoyance of having
   per-process wisdom files).  In order to make the time for this
   operation logarithmic in the number of processors (rather than
   linear), we employ a tree reduction algorithm.  This means that the
   wisdom is modified on processes other than root, which shouldn't
   matter in practice. */
void XM(gather_wisdom)(fftw_hpx_comm comm_)
{
     fftw_hpx_comm comm, comm2;
     int my_pe, n_pes;
     char *wis;
     size_t wislen;


     XM(comm_dup)(comm_, &comm);
     XM(comm_rank)(comm, &my_pe);
     XM(comm_size)(comm, &n_pes);

     if (n_pes > 2) { /* recursively split into even/odd processes */
	  XM(comm_split)(comm, my_pe % 2, my_pe, &comm2);
	  XM(gather_wisdom)(comm2);
	  XM(comm_free)(&comm2);
     }
     if (n_pes > 1 && my_pe < 2) { /* import process 1 -> 0 */
	  if (my_pe == 1) {
	       wis = X(export_wisdom_to_string)();
	       wislen = strlen(wis) + 1;
	       XM(send)(&wislen, 1, sizeof(size_t), 0, 111, comm);
	       XM(send)(wis, wislen, sizeof(char), 0, 222, comm);
	       free(wis);
	  }
	  else /* my_pe == 0 */ {
	       XM(recv)(&wislen, 1, sizeof(size_t), 1, 111, comm);
	       wis = (char *) MALLOC(wislen * sizeof(char), OTHER);
	       XM(recv)(wis, wislen, sizeof(char), 1, 222, comm);
	       if (!X(import_wisdom_from_string)(wis))
		    XM(abort)(comm, 1);
	       X(ifree)(wis);
	  }
     }
     XM(comm_free)(&comm);
}

/* broadcast wisdom from process 0 to all other processes; this
   is useful so that we can import wisdom once and not worry
   about parallel I/O or process-specific wisdom, although of
   course it assumes that all the processes have identical
   performance characteristics (i.e. identical hardware). */
void XM(broadcast_wisdom)(fftw_hpx_comm comm_)
{
     fftw_hpx_comm comm;
     int my_pe;
     char *wis;
     size_t wislen;

     XM(comm_dup)(comm_, &comm);
     XM(comm_rank)(comm, &my_pe);

     if (my_pe != 0) {
	  XM(bcast)(&wislen, 1, sizeof(size_t), 0, comm);
	  wis = (char *) MALLOC(wislen * sizeof(char), OTHER);
	  XM(bcast)(wis, wislen, sizeof(char), 0, comm);
	  if (!X(import_wisdom_from_string)(wis))
	       XM(abort)(comm, 1);
	  X(ifree)(wis);
     }
     else /* my_pe == 0 */ {
	  wis = X(export_wisdom_to_string)();
	  wislen = strlen(wis) + 1;
	  XM(bcast)(&wislen, 1, sizeof(size_t), 0, comm);
	  XM(bcast)(wis, wislen, sizeof(char), 0, comm);
	  X(free)(wis);
     }
     XM(comm_free)(&comm);
}

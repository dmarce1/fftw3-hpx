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

#include "hpx-transpose.h"

static void destroy(problem *ego_)
{
     problem_hpx_transpose *ego = (problem_hpx_transpose *) ego_;
     XM(comm_free)(&ego->comm);
     X(ifree)(ego_);
}

static void hash(const problem *p_, md5 *m)
{
     const problem_hpx_transpose *p = (const problem_hpx_transpose *) p_;
     int i;
     X(md5puts)(m, "hpx-transpose");
     X(md5int)(m, p->I == p->O);
     /* don't include alignment -- may differ between processes
	X(md5int)(m, X(ialignment_of)(p->I));
	X(md5int)(m, X(ialignment_of)(p->O));
	... note that applicability of HPX plans does not depend
	    on alignment (although optimality may, in principle). */
     X(md5INT)(m, p->vn);
     X(md5INT)(m, p->nx);
     X(md5INT)(m, p->ny);
     X(md5INT)(m, p->block);
     X(md5INT)(m, p->tblock);
     XM(comm_size)(p->comm, &i); X(md5int)(m, i);
     A(XM(md5_equal)(*m, p->comm));
}

static void print(const problem *ego_, printer *p)
{
     const problem_hpx_transpose *ego = (const problem_hpx_transpose *) ego_;
     int i;
     XM(comm_size)(ego->comm, &i);
     p->print(p, "(hpx-transpose %d %d %d %D %D %D %D %D %d)",
	      ego->I == ego->O,
	      X(ialignment_of)(ego->I),
	      X(ialignment_of)(ego->O),
	      ego->vn,
	      ego->nx, ego->ny,
	      ego->block, ego->tblock,
	      i);
}

static void zero(const problem *ego_)
{
     const problem_hpx_transpose *ego = (const problem_hpx_transpose *) ego_;
     R *I = ego->I;
     INT i, N = ego->vn * ego->ny;
     int my_pe;

     XM(comm_rank)(ego->comm, &my_pe);
     N *= XM(block)(ego->nx, ego->block, my_pe);

     for (i = 0; i < N; ++i) I[i] = K(0.0);
}

static const problem_adt padt =
{
     PROBLEM_HPX_TRANSPOSE,
     hash,
     zero,
     print,
     destroy
};

problem *XM(mkproblem_transpose)(INT nx, INT ny, INT vn,
				 R *I, R *O,
				 INT block, INT tblock,
				 fftw_hpx_comm comm,
				 unsigned flags)
{
     problem_hpx_transpose *ego =
          (problem_hpx_transpose *)X(mkproblem)(sizeof(problem_hpx_transpose), &padt);

     A(nx > 0 && ny > 0 && vn > 0);
     A(block > 0 && XM(num_blocks_ok)(nx, block, comm)
       && tblock > 0 && XM(num_blocks_ok)(ny, tblock, comm));

     /* enforce pointer equality if untainted pointers are equal */
     if (UNTAINT(I) == UNTAINT(O))
	  I = O = JOIN_TAINT(I, O);

     ego->nx = nx;
     ego->ny = ny;
     ego->vn = vn;
     ego->I = I;
     ego->O = O;
     ego->block = block > nx ? nx : block;
     ego->tblock = tblock > ny ? ny : tblock;

     /* canonicalize flags: we can freely assume that the data is
	"transposed" if one of the dimensions is 1. */
     if (ego->block == 1)
	  flags |= TRANSPOSED_IN;
     if (ego->tblock == 1)
	  flags |= TRANSPOSED_OUT;
     ego->flags = flags;

     XM(comm_dup)(comm, &ego->comm);

     return &(ego->super);
}

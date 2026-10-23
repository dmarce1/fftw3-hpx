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

#include "hpx-rdft.h"

static void destroy(problem *ego_)
{
     problem_hpx_rdft *ego = (problem_hpx_rdft *) ego_;
     XM(dtensor_destroy)(ego->sz);
     XM(comm_free)(&ego->comm);
#if !defined(STRUCT_HACK_C99) && !defined(STRUCT_HACK_KR)
     X(ifree0)(ego->kind);
#endif
     X(ifree)(ego_);
}

static void hash(const problem *p_, md5 *m)
{
     const problem_hpx_rdft *p = (const problem_hpx_rdft *) p_;
     int i;
     X(md5puts)(m, "hpx-dft");
     X(md5int)(m, p->I == p->O);
     /* don't include alignment -- may differ between processes
	X(md5int)(m, X(ialignment_of)(p->I));
	X(md5int)(m, X(ialignment_of)(p->O));
	... note that applicability of HPX plans does not depend
	    on alignment (although optimality may, in principle). */
     XM(dtensor_md5)(m, p->sz);
     X(md5INT)(m, p->vn);
     for (i = 0; i < p->sz->rnk; ++i)
	  X(md5int)(m, p->kind[i]);
     X(md5int)(m, p->flags);
     XM(comm_size)(p->comm, &i); X(md5int)(m, i);
     A(XM(md5_equal)(*m, p->comm));
}

static void print(const problem *ego_, printer *p)
{
     const problem_hpx_rdft *ego = (const problem_hpx_rdft *) ego_;
     int i;
     p->print(p, "(hpx-rdft %d %d %d ",
	      ego->I == ego->O,
	      X(ialignment_of)(ego->I),
	      X(ialignment_of)(ego->O));
     XM(dtensor_print)(ego->sz, p);
     for (i = 0; i < ego->sz->rnk; ++i)
          p->print(p, " %d", (int)ego->kind[i]);
     p->print(p, " %D %d", ego->vn, ego->flags);
     XM(comm_size)(ego->comm, &i); p->print(p, " %d)", i);
}

static void zero(const problem *ego_)
{
     const problem_hpx_rdft *ego = (const problem_hpx_rdft *) ego_;
     R *I = ego->I;
     INT i, N;
     int my_pe;

     XM(comm_rank)(ego->comm, &my_pe);
     N = ego->vn * XM(total_block)(ego->sz, IB, my_pe);
     for (i = 0; i < N; ++i) I[i] = K(0.0);
}

static const problem_adt padt =
{
     PROBLEM_HPX_RDFT,
     hash,
     zero,
     print,
     destroy
};

problem *XM(mkproblem_rdft)(const dtensor *sz, INT vn,
			    R *I, R *O,
			    fftw_hpx_comm comm,
			    const rdft_kind *kind, unsigned flags)
{
     problem_hpx_rdft *ego;
     int i, rnk = sz->rnk;
     int n_pes;

     A(XM(dtensor_validp)(sz) && FINITE_RNK(sz->rnk));
     XM(comm_size)(comm, &n_pes);
     A(n_pes >= XM(num_blocks_total)(sz, IB)
       && n_pes >= XM(num_blocks_total)(sz, OB));
     A(vn >= 0);

#if defined(STRUCT_HACK_KR)
     ego = (problem_hpx_rdft *) X(mkproblem)(sizeof(problem_hpx_rdft)
					     + sizeof(rdft_kind)
					     * (rnk > 0 ? rnk - 1 : 0), &padt);
#elif defined(STRUCT_HACK_C99)
     ego = (problem_hpx_rdft *) X(mkproblem)(sizeof(problem_hpx_rdft)
					     + sizeof(rdft_kind) * rnk, &padt);
#else
     ego = (problem_hpx_rdft *) X(mkproblem)(sizeof(problem_hpx_rdft), &padt);
     ego->kind = (rdft_kind *) MALLOC(sizeof(rdft_kind) * rnk, PROBLEMS);
#endif

     /* enforce pointer equality if untainted pointers are equal */
     if (UNTAINT(I) == UNTAINT(O))
	  I = O = JOIN_TAINT(I, O);

     ego->sz = XM(dtensor_canonical)(sz, 0);
     ego->vn = vn;
     ego->I = I;
     ego->O = O;
     for (i = 0; i< ego->sz->rnk; ++i)
	  ego->kind[i] = kind[i];

     /* canonicalize: replace TRANSPOSED_IN with TRANSPOSED_OUT by
        swapping the first two dimensions (for rnk > 1) */
     if ((flags & TRANSPOSED_IN) && ego->sz->rnk > 1) {
	  rdft_kind k = ego->kind[0];
	  ddim dim0 = ego->sz->dims[0];
	  ego->sz->dims[0] = ego->sz->dims[1];
	  ego->sz->dims[1] = dim0;
	  ego->kind[0] = ego->kind[1];
	  ego->kind[1] = k;
	  flags &= ~TRANSPOSED_IN;
	  flags ^= TRANSPOSED_OUT;
     }
     ego->flags = flags;

     XM(comm_dup)(comm, &ego->comm);

     return &(ego->super);
}

problem *XM(mkproblem_rdft_d)(dtensor *sz, INT vn,
			      R *I, R *O, 
			      fftw_hpx_comm comm,
			      const rdft_kind *kind, unsigned flags)
{
     problem *p = XM(mkproblem_rdft)(sz, vn, I, O, comm, kind, flags);
     XM(dtensor_destroy)(sz);
     return p;
}

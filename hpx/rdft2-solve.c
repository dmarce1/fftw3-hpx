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

#include "hpx-rdft2.h"

/* use the apply() operation for HPX_RDFT2 problems */
void XM(rdft2_solve)(const plan *ego_, const problem *p_)
{
     const plan_hpx_rdft2 *ego = (const plan_hpx_rdft2 *) ego_;
     const problem_hpx_rdft2 *p = (const problem_hpx_rdft2 *) p_;
     ego->apply(ego_, UNTAINT(p->I), UNTAINT(p->O));
}

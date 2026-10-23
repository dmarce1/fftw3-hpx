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
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mpi.h>

int main(int argc, char **argv)
{
    int provided, query, rank, failed, any_failed;
    int forced = argc == 2 && strcmp(argv[1], "--expect-multiple") == 0;
    char const *level = getenv("OMPI_MPI_THREAD_LEVEL");
    if (MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided) != MPI_SUCCESS) {
        return 1;
    }
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Query_thread(&query);
    failed = provided != query || (forced && provided != MPI_THREAD_MULTIPLE);
    printf("MPI_THREAD_PROBE rank=%d requested=%d provided=%d query=%d env_is_set=%d env=%s forced=%d status=%s\n",
           rank, MPI_THREAD_FUNNELED, provided, query, level != NULL,
           level == NULL ? "<unset>" : (*level == '\0' ? "<empty>" : level),
           forced, failed ? "FAIL" : "PASS");
    fflush(stdout);
    MPI_Allreduce(&failed, &any_failed, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
    MPI_Finalize();
    return any_failed ? 1 : 0;
}

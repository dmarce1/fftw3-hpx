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

#ifndef FFTW_REMAINING_PROFILE_H
#define FFTW_REMAINING_PROFILE_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Temporary diagnostics only. No HPX dependency in this shared C interface. */
enum FrpMetric {
    FRP_EXCHANGE, FRP_SEND_INIT, FRP_RECV_WAIT, FRP_SEND_WAIT,
    FRP_RECEIVE_COPY, FRP_POOL_ALLOCATE, FRP_POOL_HIT, FRP_POOL_MISS,
    FRP_HEAP_ALLOCATE, FRP_POOL_DEALLOCATE, FRP_POOL_KEEP, FRP_POOL_DELETE,
    FRP_RUN_JOBS, FRP_ENQUEUE, FRP_INLINE_WORK, FRP_JOIN,
    FRP_TASK_WALL, FRP_QUEUE_DELAY, FRP_TASK_CPU, FRP_TASK_CPU_MIGRATION,
    FRP_NESTED_JOBS, FRP_SEPARATE_SEND, FRP_SEPARATE_RECV,
    FRP_PAIRWISE_CHUNKS, FRP_PAIRWISE_COPY, FRP_PAIRWISE_ALLOCATE,
    FRP_PAIRWISE_FREE, FRP_LOCAL_TRANSPOSE,
    /* Append only: existing diagnostic C objects retain their metric IDs. */
    FRP_POST_ANNOUNCE, FRP_READY_WAIT, FRP_RECEIVE_FINISH,
    FRP_ANNOUNCE_WAIT, FRP_EXCHANGE_REST,
    FRP_MESSAGE_LOAD, FRP_DIRECT_LOAD, FRP_OWNED_LOAD, FRP_EMPTY_LOAD,
    FRP_REQUIRED_POSTED_LOAD, FRP_COUNT
};
typedef struct FrpToken {
    unsigned long long start;
    unsigned long long cpu;
    unsigned long long thread;
    unsigned long long generation;
    size_t bytes;
    int metric;
} FrpToken;
typedef struct FrpPartition {
    FrpToken total;
    unsigned long long phase_start;
    int phase;
} FrpPartition;
FrpToken frp_begin(int metric, size_t bytes);
void frp_end(FrpToken token);
void frp_event(int metric, size_t bytes);
FrpToken frp_task_begin(void);
void frp_task_end(FrpToken token);
void frp_jobs_enter(void);
void frp_jobs_leave(void);
void frp_reset(void);
void frp_sample_begin(void);
void frp_sample_end(double seconds);
void frp_report(char const * backend, int rank, int sample);
FrpPartition frp_partition_begin(int total, int phase, size_t bytes);
void frp_partition_next(FrpPartition * partition, int phase);
void frp_partition_end(FrpPartition partition);
void * frp_memcpy(void * destination, void const * source, size_t bytes);
void * frp_memmove(void * destination, void const * source, size_t bytes);
#ifdef __cplusplus
}
class FrpScope {
    FrpToken token;
public:
    explicit FrpScope(int const metric, size_t const bytes = 0)
        : token(frp_begin(metric, bytes)) {}
    ~FrpScope() { frp_end(token); }
    FrpScope(FrpScope const &) = delete;
    FrpScope & operator=(FrpScope const &) = delete;
};
class FrpPhases {
    FrpPartition partition;
public:
    explicit FrpPhases(int const total, int const phase, size_t const bytes = 0)
        : partition(frp_partition_begin(total, phase, bytes)) {}
    ~FrpPhases() noexcept { frp_partition_end(partition); }
    void next(int const phase) noexcept { frp_partition_next(&partition, phase); }
    FrpPhases(FrpPhases const &) = delete;
    FrpPhases & operator=(FrpPhases const &) = delete;
};
class FrpTask {
    FrpToken token;
public:
    FrpTask() : token(frp_task_begin()) {}
    ~FrpTask() { frp_task_end(token); }
};
class FrpJobs {
public:
    FrpJobs() { frp_jobs_enter(); }
    ~FrpJobs() { frp_jobs_leave(); }
};
#endif
#endif

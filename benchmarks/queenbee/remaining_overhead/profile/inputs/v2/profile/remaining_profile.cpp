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

#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <thread>

#include <time.h>

#include "remaining_profile.h"

namespace {
struct Counter {
    std::atomic<unsigned long long> ns{0}, calls{0}, bytes{0};
};
std::array<Counter, FRP_COUNT> counters;
std::atomic<bool> active{false};
std::atomic<unsigned long long> generation{0};
std::atomic<unsigned long long> scopes{0};
std::atomic<unsigned long long> jobs{0};
std::atomic<unsigned long long> lateScopes{0};
unsigned long long processStart = 0;
unsigned long long processElapsed = 0;
unsigned long long pendingAtEnd = 0;
double elapsed = 0;
char const * const names[] = {
    "exchange_wall", "send_initiation_wall", "receive_wait_wall", "send_completion_wait_wall",
    "receive_memcpy_wall", "pool_allocate_wall", "pool_hit", "pool_miss",
    "heap_allocate_wall", "pool_deallocate_wall", "pool_keep", "pool_delete",
    "run_jobs_wall", "enqueue_wall", "inline_work_wall", "join_wall",
    "task_wall_sum", "queue_delay_sum", "task_thread_cpu_observed", "task_cpu_migration",
    "nested_jobs", "separate_send_wall", "separate_receive_wall",
    "pairwise_chunks_wall", "pairwise_copy_wall", "pairwise_allocate_wall",
    "pairwise_free_wall", "local_transpose_children_wall"};
static_assert(sizeof(names) / sizeof(names[0]) == FRP_COUNT);
unsigned long long now()
{
    return static_cast<unsigned long long>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
unsigned long long cpu(clockid_t const clock)
{
    timespec value{};
    if (clock_gettime(clock, &value) != 0) { std::abort(); }
    return static_cast<unsigned long long>(value.tv_sec) * 1000000000ULL + value.tv_nsec;
}
unsigned long long thread()
{
    return std::hash<std::thread::id>{}(std::this_thread::get_id());
}
void add(int const metric, unsigned long long const ns, size_t const bytes)
{
    auto & counter = counters[static_cast<size_t>(metric)];
    counter.ns.fetch_add(ns, std::memory_order_relaxed);
    counter.bytes.fetch_add(bytes, std::memory_order_relaxed);
    counter.calls.fetch_add(1, std::memory_order_relaxed);
}
}
extern "C" FrpToken frp_begin(int const metric, size_t const bytes)
{
    FrpToken token{};
    if (active.load(std::memory_order_acquire)) {
        token.generation = generation.load(std::memory_order_relaxed);
        token.metric = metric;
        token.bytes = bytes;
        scopes.fetch_add(1, std::memory_order_relaxed);
        if (!active.load(std::memory_order_acquire) ||
            token.generation != generation.load(std::memory_order_relaxed)) {
            scopes.fetch_sub(1, std::memory_order_release);
            return FrpToken{};
        }
        token.start = now();
    }
    return token;
}
extern "C" void frp_end(FrpToken const token)
{
    if (token.generation != 0) {
        if (token.generation == generation.load(std::memory_order_relaxed)) {
            add(token.metric, now() - token.start, token.bytes);
        } else { lateScopes.fetch_add(1, std::memory_order_relaxed); }
        scopes.fetch_sub(1, std::memory_order_release);
    }
}
extern "C" void frp_event(int const metric, size_t const bytes)
{
    if (active.load(std::memory_order_relaxed)) { add(metric, 0, bytes); }
}
extern "C" FrpToken frp_task_begin(void)
{
    FrpToken token = frp_begin(FRP_TASK_WALL, 0);
    if (token.generation != 0) {
        token.thread = thread();
        token.cpu = cpu(CLOCK_THREAD_CPUTIME_ID);
    }
    return token;
}
extern "C" void frp_task_end(FrpToken const token)
{
    if (token.generation != 0) {
        auto const end = cpu(CLOCK_THREAD_CPUTIME_ID);
        if (token.thread == thread() && end >= token.cpu) {
            add(FRP_TASK_CPU, end - token.cpu, 0);
        } else { add(FRP_TASK_CPU_MIGRATION, 0, 0); }
    }
    frp_end(token);
}
extern "C" void frp_jobs_enter(void)
{
    if (jobs.fetch_add(1, std::memory_order_relaxed) != 0) { frp_event(FRP_NESTED_JOBS, 0); }
}
extern "C" void frp_jobs_leave(void) { jobs.fetch_sub(1, std::memory_order_relaxed); }
extern "C" void frp_reset(void)
{
    active.store(false, std::memory_order_release);
    if (scopes.load(std::memory_order_acquire) != 0 || jobs.load(std::memory_order_relaxed) != 0) {
        std::fprintf(stderr, "REMAINING_PROFILE_INVALID unfinished_scope_at_reset\n");
        std::abort();
    }
    for (auto & counter : counters) {
        counter.ns.store(0, std::memory_order_relaxed);
        counter.calls.store(0, std::memory_order_relaxed);
        counter.bytes.store(0, std::memory_order_relaxed);
    }
    generation.fetch_add(1, std::memory_order_relaxed);
    active.store(true, std::memory_order_release);
}
extern "C" void frp_sample_begin(void) { processStart = cpu(CLOCK_PROCESS_CPUTIME_ID); }
extern "C" void frp_sample_end(double const seconds)
{
    processElapsed = cpu(CLOCK_PROCESS_CPUTIME_ID) - processStart;
    active.store(false, std::memory_order_release);
    pendingAtEnd = scopes.load(std::memory_order_acquire);
    elapsed = seconds;
}
extern "C" void frp_report(char const * const backend, int const rank, int const sample)
{
    for (size_t index = 0; index < counters.size(); ++index) {
        auto const & counter = counters[index];
        std::fprintf(stderr, "PROFILE_DETAIL backend=%s rank=%d sample=%d metric=%s calls=%llu bytes=%llu seconds=%.17g\n",
                     backend, rank, sample, names[index], counter.calls.load(std::memory_order_relaxed),
                     counter.bytes.load(std::memory_order_relaxed),
                     static_cast<double>(counter.ns.load(std::memory_order_relaxed)) * 1e-9);
    }
    std::fprintf(stderr, "PROFILE_DETAIL_TOTAL backend=%s rank=%d sample=%d seconds=%.17g process_cpu_seconds=%.17g pending_scopes=%llu late_scopes=%llu\n",
                 backend, rank, sample, elapsed, static_cast<double>(processElapsed) * 1e-9,
                 pendingAtEnd, lateScopes.load(std::memory_order_relaxed));
    std::fflush(stderr);
}
extern "C" void * frp_memcpy(void * const destination, void const * const source, size_t const bytes)
{
    FrpScope const scope(FRP_PAIRWISE_COPY, bytes);
    return std::memcpy(destination, source, bytes);
}
extern "C" void * frp_memmove(void * const destination, void const * const source, size_t const bytes)
{
    FrpScope const scope(FRP_PAIRWISE_COPY, bytes);
    return std::memmove(destination, source, bytes);
}

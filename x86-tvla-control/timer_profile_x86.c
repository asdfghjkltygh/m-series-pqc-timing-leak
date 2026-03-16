/*
 * timer_profile_x86.c — RDTSC Timer Resolution Profiling
 *
 * Mirrors timer_profile.c from the Apple Silicon experiments but uses
 * x86 RDTSC/RDTSCP with CPUID serialization.
 *
 * Measures the empirical granularity and overhead of RDTSC by doing
 * millions of back-to-back reads.
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#define NUM_SAMPLES 10000000

static inline uint64_t rdtsc_fenced(void) {
    unsigned int aux;
    uint64_t tsc;
    __asm__ volatile(
        "cpuid\n\t"
        "rdtsc\n\t"
        "shl $32, %%rdx\n\t"
        "or %%rdx, %%rax"
        : "=a"(tsc)
        :
        : "%rbx", "%rcx", "%rdx"
    );
    return tsc;
}

int compare_u64(const void *a, const void *b) {
    uint64_t va = *(const uint64_t *)a;
    uint64_t vb = *(const uint64_t *)b;
    return (va > vb) - (va < vb);
}

int main(void) {
    printf("=== RDTSC Timer Resolution Profile ===\n\n");

    /* Estimate frequency: measure 100ms wall-clock vs TSC delta */
    /* (rough estimate — sufficient for our purposes) */
    uint64_t t0 = rdtsc_fenced();
    /* Busy-wait ~100ms worth of iterations */
    volatile double x = 1.0;
    for (int i = 0; i < 50000000; i++) x *= 1.0000001;
    uint64_t t1 = rdtsc_fenced();
    /* We can't easily get wall-clock time in pure C without platform headers,
       so we'll just report the TSC delta and let the user compute frequency */
    printf("  Calibration: %llu TSC ticks for ~50M FP ops\n",
           (unsigned long long)(t1 - t0));

    /* Measure back-to-back deltas */
    uint64_t *deltas = malloc(NUM_SAMPLES * sizeof(uint64_t));
    if (!deltas) { fprintf(stderr, "malloc failed\n"); return 1; }

    /* Warmup */
    for (int i = 0; i < 1000; i++) {
        uint64_t a = rdtsc_fenced();
        uint64_t b = rdtsc_fenced();
        (void)(b - a);
    }

    for (int i = 0; i < NUM_SAMPLES; i++) {
        uint64_t start = rdtsc_fenced();
        uint64_t end = rdtsc_fenced();
        deltas[i] = end - start;
    }

    /* Sort for percentile computation */
    qsort(deltas, NUM_SAMPLES, sizeof(uint64_t), compare_u64);

    /* Stats */
    uint64_t sum = 0;
    for (int i = 0; i < NUM_SAMPLES; i++) sum += deltas[i];
    double mean = (double)sum / NUM_SAMPLES;
    uint64_t min_d = deltas[0];
    uint64_t median = deltas[NUM_SAMPLES / 2];
    uint64_t p1 = deltas[(int)(NUM_SAMPLES * 0.01)];
    uint64_t p5 = deltas[(int)(NUM_SAMPLES * 0.05)];
    uint64_t p95 = deltas[(int)(NUM_SAMPLES * 0.95)];
    uint64_t p99 = deltas[(int)(NUM_SAMPLES * 0.99)];
    uint64_t max_d = deltas[NUM_SAMPLES - 1];

    /* Count unique values */
    int unique = 1;
    for (int i = 1; i < NUM_SAMPLES; i++)
        if (deltas[i] != deltas[i-1]) unique++;

    printf("\n  Back-to-back read deltas (%d million samples):\n", NUM_SAMPLES / 1000000);
    printf("    Min:    %llu cycles\n", (unsigned long long)min_d);
    printf("    P1:     %llu cycles\n", (unsigned long long)p1);
    printf("    P5:     %llu cycles\n", (unsigned long long)p5);
    printf("    Median: %llu cycles\n", (unsigned long long)median);
    printf("    Mean:   %.2f cycles\n", mean);
    printf("    P95:    %llu cycles\n", (unsigned long long)p95);
    printf("    P99:    %llu cycles\n", (unsigned long long)p99);
    printf("    Max:    %llu cycles\n", (unsigned long long)max_d);
    printf("    Unique values: %d\n", unique);

    /* Distribution of small values */
    printf("\n  Delta distribution (first 20 values):\n");
    int count = 0;
    uint64_t prev = deltas[0];
    for (int i = 0; i < NUM_SAMPLES && count < 20; i++) {
        if (i == 0 || deltas[i] != prev) {
            prev = deltas[i];
            int occ = 0;
            for (int j = i; j < NUM_SAMPLES && deltas[j] == deltas[i]; j++) occ++;
            printf("    %llu cycles: %d occurrences (%.1f%%)\n",
                   (unsigned long long)deltas[i], occ, 100.0 * occ / NUM_SAMPLES);
            count++;
        }
    }

    printf("\n  ============================================\n");
    printf("  RDTSC timer overhead: median %llu cycles\n",
           (unsigned long long)median);
    printf("  (Compare to Apple CNTVCT_EL0: 24 MHz, median 0 ticks)\n");
    printf("  ============================================\n");

    free(deltas);
    return 0;
}

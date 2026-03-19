/*
 * timer_profile.c — Phase 2: Timer Resolution Profiling
 *
 * Measures the empirical granularity and overhead of CNTVCT_EL0
 * by doing millions of back-to-back reads.
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <mach/mach_time.h>

#define NUM_SAMPLES 10000000

static inline uint64_t read_cntvct(void) {
    uint64_t val;
    __asm__ volatile("isb" ::: "memory");
    __asm__ volatile("mrs %0, CNTVCT_EL0" : "=r"(val));
    return val;
}

int compare_u64(const void *a, const void *b) {
    uint64_t va = *(const uint64_t *)a;
    uint64_t vb = *(const uint64_t *)b;
    return (va > vb) - (va < vb);
}

int main(void) {
    printf("=== CNTVCT_EL0 Timer Resolution Profile ===\n\n");

    /* Get timer frequency */
    mach_timebase_info_data_t info;
    mach_timebase_info(&info);
    /* CNTVCT_EL0 ticks at the same rate as mach_absolute_time on Apple Silicon */
    double ns_per_tick = (double)info.numer / (double)info.denom;
    double freq_mhz = 1000.0 / ns_per_tick;

    printf("  Timer frequency: %.2f MHz (%.4f ns/tick)\n", freq_mhz, ns_per_tick);

    /* Measure back-to-back deltas */
    uint64_t *deltas = malloc(NUM_SAMPLES * sizeof(uint64_t));
    if (!deltas) { fprintf(stderr, "malloc failed\n"); return 1; }

    /* Warmup */
    for (int i = 0; i < 1000; i++) {
        uint64_t a = read_cntvct();
        uint64_t b = read_cntvct();
        (void)(b - a);
    }

    for (int i = 0; i < NUM_SAMPLES; i++) {
        uint64_t start = read_cntvct();
        uint64_t end = read_cntvct();
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
    printf("    Min:    %llu ticks (%.1f ns)\n", (unsigned long long)min_d, min_d * ns_per_tick);
    printf("    P1:     %llu ticks (%.1f ns)\n", (unsigned long long)p1, p1 * ns_per_tick);
    printf("    P5:     %llu ticks (%.1f ns)\n", (unsigned long long)p5, p5 * ns_per_tick);
    printf("    Median: %llu ticks (%.1f ns)\n", (unsigned long long)median, median * ns_per_tick);
    printf("    Mean:   %.2f ticks (%.1f ns)\n", mean, mean * ns_per_tick);
    printf("    P95:    %llu ticks (%.1f ns)\n", (unsigned long long)p95, p95 * ns_per_tick);
    printf("    P99:    %llu ticks (%.1f ns)\n", (unsigned long long)p99, p99 * ns_per_tick);
    printf("    Max:    %llu ticks (%.1f ns)\n", (unsigned long long)max_d, max_d * ns_per_tick);
    printf("    Unique values: %d\n", unique);

    /* Distribution of small values */
    printf("\n  Delta distribution (first 20 values):\n");
    int count = 0;
    uint64_t prev = deltas[0];
    for (int i = 0; i < NUM_SAMPLES && count < 20; i++) {
        if (i == 0 || deltas[i] != prev) {
            if (i > 0) {
                int freq = i;
                for (int j = 0; j < i; j++) if (deltas[j] == prev) freq++;
            }
            prev = deltas[i];
            /* Count occurrences */
            int occ = 0;
            for (int j = i; j < NUM_SAMPLES && deltas[j] == deltas[i]; j++) occ++;
            printf("    %llu ticks: %d occurrences (%.1f%%)\n",
                   (unsigned long long)deltas[i], occ, 100.0 * occ / NUM_SAMPLES);
            count++;
        }
    }

    printf("\n  ============================================\n");
    printf("  FORMAL STATEMENT:\n");
    printf("  The measurement apparatus (ARM CNTVCT_EL0) has a\n");
    printf("  minimum resolvable threshold of %llu tick(s) (%.1f ns).\n",
           (unsigned long long)median, median * ns_per_tick);
    printf("  Timer overhead (back-to-back reads): median %llu ticks.\n",
           (unsigned long long)median);
    printf("  Effective timer frequency: %.2f MHz.\n", freq_mhz);
    printf("  ============================================\n");

    free(deltas);
    return 0;
}

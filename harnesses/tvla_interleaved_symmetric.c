/*
 * tvla_interleaved_symmetric.c
 *
 * INTERLEAVED SYMMETRIC TVLA harness for ML-KEM-768 on Apple Silicon.
 *
 * This is the strongest possible control harness. It eliminates:
 *   1. Harness asymmetry: both fixed and random inputs are pre-generated
 *      into memory arrays before measurement begins.
 *   2. Temporal drift: fixed and random measurements are interleaved
 *      within a single loop (fixed[i], random[i], fixed[i+1], random[i+1]...)
 *      so both groups experience identical environmental conditions.
 *
 * If TVLA STILL fails with this harness, the confound is genuinely
 * architectural — the CPU responds differently to repeated vs novel data
 * within the same measurement window. On Apple Silicon, this implicates
 * the Data-Dependent Prefetcher (DMP).
 *
 * If TVLA passes, the confound was entirely methodological (temporal drift
 * between sequential collection runs).
 *
 * Output format: one line per measurement, "F <cycles>" or "R <cycles>"
 * to tag fixed vs random traces.
 *
 * Uses CNTVCT_EL0 for timing on Apple Silicon.
 *
 * Usage: ./tvla_interleaved_symmetric <num_traces_per_group>
 *   Collects num_traces_per_group fixed AND num_traces_per_group random,
 *   interleaved. Total measurements = 2 * num_traces_per_group.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <oqs/oqs.h>

static inline uint64_t read_cntvct(void) {
    uint64_t val;
    __asm__ volatile("mrs %0, CNTVCT_EL0" : "=r"(val));
    return val;
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <num_traces_per_group>\n", argv[0]);
        fprintf(stderr, "  Collects N fixed + N random traces, interleaved.\n");
        return 1;
    }

    int num_traces = atoi(argv[1]);
    if (num_traces <= 0) {
        fprintf(stderr, "num_traces must be positive\n");
        return 1;
    }

    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    if (!kem) {
        fprintf(stderr, "ML-KEM-768 not available\n");
        return 1;
    }

    size_t sk_len = kem->length_secret_key;
    size_t ct_len = kem->length_ciphertext;
    size_t pk_len = kem->length_public_key;
    size_t ss_len = kem->length_shared_secret;

    uint8_t *pk = malloc(pk_len);
    uint8_t *ss_fixed = malloc(ss_len);
    uint8_t *ss_random = malloc(ss_len);

    /*
     * Pre-generate ALL inputs for both groups.
     * Fixed: every slot is the same (ct, sk) pair.
     * Random: every slot is a different (ct, sk) pair.
     */
    fprintf(stderr, "Pre-generating %d FIXED input tuples...\n", num_traces);

    uint8_t *fixed_sk_array = malloc((size_t)num_traces * sk_len);
    uint8_t *fixed_ct_array = malloc((size_t)num_traces * ct_len);
    uint8_t *random_sk_array = malloc((size_t)num_traces * sk_len);
    uint8_t *random_ct_array = malloc((size_t)num_traces * ct_len);

    if (!fixed_sk_array || !fixed_ct_array || !random_sk_array || !random_ct_array) {
        fprintf(stderr, "Failed to allocate arrays (%zu bytes total)\n",
                (size_t)num_traces * 2 * (sk_len + ct_len));
        return 1;
    }

    /* Fixed group: one keypair, replicated */
    OQS_KEM_keypair(kem, pk, fixed_sk_array);
    OQS_KEM_encaps(kem, fixed_ct_array, ss_fixed, pk);
    for (int i = 1; i < num_traces; i++) {
        memcpy(fixed_sk_array + (size_t)i * sk_len, fixed_sk_array, sk_len);
        memcpy(fixed_ct_array + (size_t)i * ct_len, fixed_ct_array, ct_len);
    }

    fprintf(stderr, "Pre-generating %d RANDOM input tuples...\n", num_traces);

    /* Random group: unique keypair per slot */
    for (int i = 0; i < num_traces; i++) {
        OQS_KEM_keypair(kem, pk, random_sk_array + (size_t)i * sk_len);
        OQS_KEM_encaps(kem, random_ct_array + (size_t)i * ct_len, ss_random, pk);
        if (i % 50000 == 0 && i > 0)
            fprintf(stderr, "  pre-gen random: %d/%d\n", i, num_traces);
    }

    fprintf(stderr, "Pre-generation complete. Starting interleaved measurements...\n");

    /* Warmup — alternate between fixed and random slots */
    for (int i = 0; i < 100; i++) {
        OQS_KEM_decaps(kem, ss_fixed, fixed_ct_array, fixed_sk_array);
        OQS_KEM_decaps(kem, ss_random, random_ct_array, random_sk_array);
    }

    /*
     * INTERLEAVED measurement loop.
     * For each index i:
     *   1. Measure decaps on fixed[i]
     *   2. Measure decaps on random[i]
     *
     * Both measurements occur under the same environmental conditions
     * (same thermal state, same system load, same cache pressure).
     * This eliminates temporal drift as a confound.
     */
    for (int i = 0; i < num_traces; i++) {
        uint8_t *f_sk = fixed_sk_array + (size_t)i * sk_len;
        uint8_t *f_ct = fixed_ct_array + (size_t)i * ct_len;
        uint8_t *r_sk = random_sk_array + (size_t)i * sk_len;
        uint8_t *r_ct = random_ct_array + (size_t)i * ct_len;

        /* Measure FIXED */
        uint64_t start_f = read_cntvct();
        OQS_KEM_decaps(kem, ss_fixed, f_ct, f_sk);
        uint64_t end_f = read_cntvct();

        /* Measure RANDOM — immediately after fixed, same environment */
        uint64_t start_r = read_cntvct();
        OQS_KEM_decaps(kem, ss_random, r_ct, r_sk);
        uint64_t end_r = read_cntvct();

        printf("F %llu\n", (unsigned long long)(end_f - start_f));
        printf("R %llu\n", (unsigned long long)(end_r - start_r));

        if (i % 50000 == 0 && i > 0)
            fprintf(stderr, "  interleaved: %d/%d\n", i, num_traces);
    }

    free(fixed_sk_array);
    free(fixed_ct_array);
    free(random_sk_array);
    free(random_ct_array);
    free(pk);
    free(ss_fixed);
    free(ss_random);
    OQS_KEM_free(kem);
    return 0;
}

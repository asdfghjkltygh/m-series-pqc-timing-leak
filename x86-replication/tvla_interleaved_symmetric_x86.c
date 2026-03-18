/*
 * tvla_interleaved_symmetric.c
 *
 * INTERLEAVED SYMMETRIC TVLA harness for ML-KEM-768 on x86-64.
 *
 * Pre-generates ALL inputs (both fixed and random sets) into memory arrays
 * BEFORE measurement. Then measures in strict interleaved order:
 *   fixed[0], random[0], fixed[1], random[1], ...
 *
 * This cancels out any temporal drift (thermal, frequency scaling, etc.)
 * that would bias sequential AAAA...BBBB... measurements.
 *
 * Uses RDTSC with CPUID serialization for timing.
 *
 * Usage: ./tvla_interleaved_symmetric <num_pairs>
 *   Outputs two cycle counts per line: "fixed_cycles random_cycles"
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <oqs/oqs.h>

#define WARMUP_ITERATIONS 10000

static inline uint64_t rdtsc_start(void) {
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

static inline uint64_t rdtsc_end(void) {
    uint64_t tsc;
    __asm__ volatile(
        "rdtscp\n\t"
        "shl $32, %%rdx\n\t"
        "or %%rdx, %%rax\n\t"
        "mov %%rax, %0\n\t"
        "cpuid"
        : "=r"(tsc)
        :
        : "%rax", "%rbx", "%rcx", "%rdx"
    );
    return tsc;
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <num_pairs>\n", argv[0]);
        fprintf(stderr, "  Outputs interleaved fixed/random measurements\n");
        return 1;
    }

    int num_pairs = atoi(argv[1]);
    if (num_pairs <= 0) {
        fprintf(stderr, "num_pairs must be positive\n");
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
    uint8_t *ss = malloc(ss_len);

    /* Allocate arrays for BOTH fixed and random inputs */
    uint8_t *fixed_sk_array = malloc((size_t)num_pairs * sk_len);
    uint8_t *fixed_ct_array = malloc((size_t)num_pairs * ct_len);
    uint8_t *random_sk_array = malloc((size_t)num_pairs * sk_len);
    uint8_t *random_ct_array = malloc((size_t)num_pairs * ct_len);

    if (!fixed_sk_array || !fixed_ct_array || !random_sk_array || !random_ct_array) {
        fprintf(stderr, "Failed to allocate arrays\n");
        return 1;
    }

    fprintf(stderr, "Pre-generating %d pairs of inputs...\n", num_pairs);

    /* Generate FIXED inputs: one keypair replicated across all slots */
    OQS_KEM_keypair(kem, pk, fixed_sk_array);
    OQS_KEM_encaps(kem, fixed_ct_array, ss, pk);
    for (int i = 1; i < num_pairs; i++) {
        memcpy(fixed_sk_array + (size_t)i * sk_len, fixed_sk_array, sk_len);
        memcpy(fixed_ct_array + (size_t)i * ct_len, fixed_ct_array, ct_len);
    }

    /* Generate RANDOM inputs: unique keypair for each slot */
    for (int i = 0; i < num_pairs; i++) {
        OQS_KEM_keypair(kem, pk, random_sk_array + (size_t)i * sk_len);
        OQS_KEM_encaps(kem, random_ct_array + (size_t)i * ct_len, ss, pk);
        if (i % 10000 == 0 && i > 0)
            fprintf(stderr, "  pre-gen random: %d/%d\n", i, num_pairs);
    }

    fprintf(stderr, "Pre-generation complete. Warming up (%d iterations)...\n", WARMUP_ITERATIONS);

    /* Warmup phase: stabilize CPU P-states and warm instruction cache */
    for (int i = 0; i < WARMUP_ITERATIONS; i++) {
        OQS_KEM_decaps(kem, ss, fixed_ct_array, fixed_sk_array);
        OQS_KEM_decaps(kem, ss, random_ct_array, random_sk_array);
    }

    fprintf(stderr, "Starting interleaved measurements (%d pairs)...\n", num_pairs);

    /* Interleaved measurement loop */
    for (int i = 0; i < num_pairs; i++) {
        uint8_t *fixed_sk = fixed_sk_array + (size_t)i * sk_len;
        uint8_t *fixed_ct = fixed_ct_array + (size_t)i * ct_len;
        uint8_t *random_sk = random_sk_array + (size_t)i * sk_len;
        uint8_t *random_ct = random_ct_array + (size_t)i * ct_len;

        /* Measure FIXED */
        uint64_t start_f = rdtsc_start();
        OQS_KEM_decaps(kem, ss, fixed_ct, fixed_sk);
        uint64_t end_f = rdtsc_end();

        /* Measure RANDOM */
        uint64_t start_r = rdtsc_start();
        OQS_KEM_decaps(kem, ss, random_ct, random_sk);
        uint64_t end_r = rdtsc_end();

        /* Output both on same line for perfect pairing */
        printf("%llu %llu\n",
               (unsigned long long)(end_f - start_f),
               (unsigned long long)(end_r - start_r));

        if (i % 50000 == 0 && i > 0)
            fprintf(stderr, "  interleaved: %d/%d\n", i, num_pairs);
    }

    free(fixed_sk_array);
    free(fixed_ct_array);
    free(random_sk_array);
    free(random_ct_array);
    free(pk);
    free(ss);
    OQS_KEM_free(kem);
    return 0;
}

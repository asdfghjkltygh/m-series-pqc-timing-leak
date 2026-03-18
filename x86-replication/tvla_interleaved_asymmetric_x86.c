/*
 * tvla_interleaved_asymmetric.c
 *
 * INTERLEAVED ASYMMETRIC TVLA harness for ML-KEM-768 on x86-64.
 *
 * This demonstrates the "Execution-Context Confound":
 * - FIXED mode: Uses pre-generated inputs (clean cache state)
 * - RANDOM mode: Does keygen+encaps RIGHT BEFORE decaps (polluted cache)
 *
 * Measures in strict interleaved order to cancel temporal drift,
 * isolating the cache pollution effect.
 *
 * Uses RDTSC with CPUID serialization for timing.
 *
 * Usage: ./tvla_interleaved_asymmetric <num_pairs>
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
        fprintf(stderr, "  Random mode does keygen+encaps before decaps (cache pollution)\n");
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

    /* Allocate buffers */
    uint8_t *pk = malloc(pk_len);
    uint8_t *ss = malloc(ss_len);

    /* Fixed inputs: pre-generated, reused every iteration */
    uint8_t *fixed_sk = malloc(sk_len);
    uint8_t *fixed_ct = malloc(ct_len);

    /* Random inputs: generated fresh each iteration */
    uint8_t *random_sk = malloc(sk_len);
    uint8_t *random_ct = malloc(ct_len);

    if (!pk || !ss || !fixed_sk || !fixed_ct || !random_sk || !random_ct) {
        fprintf(stderr, "Failed to allocate buffers\n");
        return 1;
    }

    fprintf(stderr, "Generating fixed inputs...\n");

    /* Generate FIXED inputs once */
    OQS_KEM_keypair(kem, pk, fixed_sk);
    OQS_KEM_encaps(kem, fixed_ct, ss, pk);

    fprintf(stderr, "Warming up (%d iterations)...\n", WARMUP_ITERATIONS);

    /* Warmup phase */
    for (int i = 0; i < WARMUP_ITERATIONS; i++) {
        /* Warmup with fixed inputs */
        OQS_KEM_decaps(kem, ss, fixed_ct, fixed_sk);
        /* Warmup with a random keygen+encaps+decaps cycle */
        OQS_KEM_keypair(kem, pk, random_sk);
        OQS_KEM_encaps(kem, random_ct, ss, pk);
        OQS_KEM_decaps(kem, ss, random_ct, random_sk);
    }

    fprintf(stderr, "Starting interleaved measurements (%d pairs)...\n", num_pairs);
    fprintf(stderr, "  Fixed: pre-generated inputs (clean cache)\n");
    fprintf(stderr, "  Random: keygen+encaps before decaps (polluted cache)\n");

    /* Interleaved measurement loop */
    for (int i = 0; i < num_pairs; i++) {

        /* Measure FIXED: just decaps with pre-generated inputs */
        uint64_t start_f = rdtsc_start();
        OQS_KEM_decaps(kem, ss, fixed_ct, fixed_sk);
        uint64_t end_f = rdtsc_end();

        /* Measure RANDOM: keygen + encaps (cache pollution) + timed decaps */
        OQS_KEM_keypair(kem, pk, random_sk);      /* Pollutes cache */
        OQS_KEM_encaps(kem, random_ct, ss, pk);   /* Pollutes cache more */

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

    free(fixed_sk);
    free(fixed_ct);
    free(random_sk);
    free(random_ct);
    free(pk);
    free(ss);
    OQS_KEM_free(kem);
    return 0;
}

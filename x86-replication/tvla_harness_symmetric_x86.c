/*
 * tvla_harness_symmetric_x86.c
 *
 * SYMMETRIC TVLA harness for ML-KEM-768 on x86-64.
 *
 * Pre-generates ALL random (keypair, ciphertext) tuples into memory arrays
 * BEFORE measurement. Both fixed and random modes execute identical code
 * paths during the timed loop: index into array -> decaps -> record timing.
 *
 * Uses RDTSC with CPUID serialization for timing.
 *
 * Usage: ./tvla_harness_symmetric_x86 <fixed|random> <num_traces>
 *   Outputs one cycle count per line to stdout.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <oqs/oqs.h>

static inline uint64_t rdtsc_start(void) {
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
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <fixed|random> <num_traces>\n", argv[0]);
        return 1;
    }

    int is_fixed = (strcmp(argv[1], "fixed") == 0);
    int num_traces = atoi(argv[2]);
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
    uint8_t *ss = malloc(ss_len);

    fprintf(stderr, "Pre-generating %d input tuples (%s mode)...\n",
            num_traces, is_fixed ? "fixed" : "random");

    uint8_t *sk_array = malloc((size_t)num_traces * sk_len);
    uint8_t *ct_array = malloc((size_t)num_traces * ct_len);
    if (!sk_array || !ct_array) {
        fprintf(stderr, "Failed to allocate arrays (%zu bytes)\n",
                (size_t)num_traces * (sk_len + ct_len));
        return 1;
    }

    if (is_fixed) {
        /* Generate one keypair + ciphertext, replicate across all slots */
        OQS_KEM_keypair(kem, pk, sk_array);
        OQS_KEM_encaps(kem, ct_array, ss, pk);
        for (int i = 1; i < num_traces; i++) {
            memcpy(sk_array + (size_t)i * sk_len, sk_array, sk_len);
            memcpy(ct_array + (size_t)i * ct_len, ct_array, ct_len);
        }
    } else {
        /* Generate a unique keypair + ciphertext for each slot */
        for (int i = 0; i < num_traces; i++) {
            OQS_KEM_keypair(kem, pk, sk_array + (size_t)i * sk_len);
            OQS_KEM_encaps(kem, ct_array + (size_t)i * ct_len, ss, pk);
            if (i % 10000 == 0 && i > 0)
                fprintf(stderr, "  pre-gen: %d/%d\n", i, num_traces);
        }
    }

    fprintf(stderr, "Pre-generation complete. Starting measurements...\n");

    /* Warmup */
    for (int i = 0; i < 100; i++)
        OQS_KEM_decaps(kem, ss, ct_array, sk_array);

    /* Measurement loop — identical code path for both modes */
    for (int i = 0; i < num_traces; i++) {
        uint8_t *use_sk = sk_array + (size_t)i * sk_len;
        uint8_t *use_ct = ct_array + (size_t)i * ct_len;

        uint64_t start = rdtsc_start();
        OQS_KEM_decaps(kem, ss, use_ct, use_sk);
        uint64_t end = rdtsc_end();

        printf("%llu\n", (unsigned long long)(end - start));

        if (i % 10000 == 0 && i > 0)
            fprintf(stderr, "  TVLA-symmetric [%s]: %d/%d\n",
                    argv[1], i, num_traces);
    }

    free(sk_array);
    free(ct_array);
    free(pk);
    free(ss);
    OQS_KEM_free(kem);
    return 0;
}

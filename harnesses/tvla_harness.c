/*
 * tvla_harness.c
 *
 * Test Vector Leakage Assessment (TVLA) harness for ML-KEM-768.
 * Implements Fixed-vs-Random methodology:
 *   - "fixed" mode: uses a single, fixed (ct, sk) pair for all measurements
 *   - "random" mode: generates a fresh keypair + ciphertext each measurement
 *
 * Uses CNTVCT_EL0 for cycle-accurate timing on Apple Silicon.
 *
 * Usage: ./tvla_harness <mode> <num_traces>
 *   mode: "fixed" or "random"
 *   Outputs one cycle count per line to stdout.
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

    uint8_t *pk = malloc(kem->length_public_key);
    uint8_t *sk = malloc(kem->length_secret_key);
    uint8_t *ct = malloc(kem->length_ciphertext);
    uint8_t *ss = malloc(kem->length_shared_secret);

    /* For fixed mode: generate one keypair + ciphertext up front */
    uint8_t *fixed_sk = NULL;
    uint8_t *fixed_ct = NULL;
    if (is_fixed) {
        fixed_sk = malloc(kem->length_secret_key);
        fixed_ct = malloc(kem->length_ciphertext);
        OQS_KEM_keypair(kem, pk, fixed_sk);
        OQS_KEM_encaps(kem, fixed_ct, ss, pk);
    }

    /* Warmup */
    OQS_KEM_keypair(kem, pk, sk);
    OQS_KEM_encaps(kem, ct, ss, pk);
    for (int i = 0; i < 100; i++)
        OQS_KEM_decaps(kem, ss, ct, sk);

    for (int i = 0; i < num_traces; i++) {
        uint8_t *use_ct, *use_sk;

        if (is_fixed) {
            use_ct = fixed_ct;
            use_sk = fixed_sk;
        } else {
            /* Generate fresh keypair and ciphertext each time */
            OQS_KEM_keypair(kem, pk, sk);
            OQS_KEM_encaps(kem, ct, ss, pk);
            use_ct = ct;
            use_sk = sk;
        }

        uint64_t start = read_cntvct();
        OQS_KEM_decaps(kem, ss, use_ct, use_sk);
        uint64_t end = read_cntvct();

        printf("%llu\n", (unsigned long long)(end - start));

        if (i % 10000 == 0 && i > 0)
            fprintf(stderr, "  TVLA [%s]: %d/%d\n", argv[1], i, num_traces);
    }

    free(pk); free(sk); free(ct); free(ss);
    if (fixed_sk) free(fixed_sk);
    if (fixed_ct) free(fixed_ct);
    OQS_KEM_free(kem);
    return 0;
}

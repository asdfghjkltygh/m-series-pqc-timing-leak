/*
 * tvla_harness_symmetric.c
 *
 * SYMMETRIC TVLA harness for ML-KEM-768.
 *
 * Unlike the standard harness, this version pre-generates ALL random
 * (keypair, ciphertext) tuples into memory arrays BEFORE measurement begins.
 * Both fixed and random modes then execute identical code paths during the
 * timed loop: index into an array, call decaps, record timing. No keygen
 * or encaps occurs inside the measurement loop in either mode.
 *
 * This isolates the architectural confound (DMP synchronization on repeated
 * data) from the harness-induced confound (cache pollution from keygen+encaps
 * in random mode).
 *
 * If the TVLA failure persists with this harness, the cause is architectural.
 * If it vanishes, the cause was harness asymmetry.
 *
 * Uses CNTVCT_EL0 for timing on Apple Silicon.
 *
 * Usage: ./tvla_harness_symmetric <fixed|random> <num_traces>
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

    size_t sk_len = kem->length_secret_key;
    size_t ct_len = kem->length_ciphertext;
    size_t pk_len = kem->length_public_key;
    size_t ss_len = kem->length_shared_secret;

    uint8_t *pk = malloc(pk_len);
    uint8_t *ss = malloc(ss_len);

    /*
     * Pre-generate ALL inputs into contiguous arrays.
     * For fixed mode: every slot contains the same (ct, sk) pair.
     * For random mode: every slot contains a different (ct, sk) pair.
     * Either way, the measurement loop just indexes into the arrays.
     */
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

    /* Warmup — use the first slot */
    for (int i = 0; i < 100; i++)
        OQS_KEM_decaps(kem, ss, ct_array, sk_array);

    /*
     * Measurement loop — identical code path for both modes.
     * The ONLY difference is the DATA in the arrays, not the code executed.
     */
    for (int i = 0; i < num_traces; i++) {
        uint8_t *use_sk = sk_array + (size_t)i * sk_len;
        uint8_t *use_ct = ct_array + (size_t)i * ct_len;

        uint64_t start = read_cntvct();
        OQS_KEM_decaps(kem, ss, use_ct, use_sk);
        uint64_t end = read_cntvct();

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

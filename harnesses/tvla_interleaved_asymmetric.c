/*
 * tvla_interleaved_asymmetric.c
 *
 * INTERLEAVED ASYMMETRIC TVLA harness for ML-KEM-768 on Apple Silicon.
 *
 * Uses interleaved collection (fixed[i], random[i] alternating) to
 * eliminate temporal drift, but keeps the standard asymmetric design
 * where random mode generates keygen+encaps live before each measurement.
 *
 * This isolates the harness asymmetry effect from temporal drift:
 * if this harness fails but the interleaved symmetric passes, the
 * failure is due to keygen+encaps cache pollution, not temporal drift.
 *
 * Fixed group: same (ct, sk) pair every time (pre-generated).
 * Random group: fresh keygen+encaps before each timed decaps.
 *
 * Output format: "F <cycles>" or "R <cycles>" per line.
 * Uses CNTVCT_EL0 for timing.
 *
 * Usage: ./tvla_interleaved_asymmetric <num_traces_per_group>
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

    /* Fixed group: pre-generate one (ct, sk) pair */
    uint8_t *fixed_pk = malloc(pk_len);
    uint8_t *fixed_sk = malloc(sk_len);
    uint8_t *fixed_ct = malloc(ct_len);
    uint8_t *ss_fixed = malloc(ss_len);
    uint8_t *ss_random = malloc(ss_len);

    /* Random group: allocate for live generation */
    uint8_t *rand_pk = malloc(pk_len);
    uint8_t *rand_sk = malloc(sk_len);
    uint8_t *rand_ct = malloc(ct_len);

    OQS_KEM_keypair(kem, fixed_pk, fixed_sk);
    OQS_KEM_encaps(kem, fixed_ct, ss_fixed, fixed_pk);

    fprintf(stderr, "Starting interleaved asymmetric measurements (%d per group)...\n",
            num_traces);

    /* Warmup */
    for (int i = 0; i < 100; i++) {
        OQS_KEM_decaps(kem, ss_fixed, fixed_ct, fixed_sk);
        OQS_KEM_keypair(kem, rand_pk, rand_sk);
        OQS_KEM_encaps(kem, rand_ct, ss_random, rand_pk);
        OQS_KEM_decaps(kem, ss_random, rand_ct, rand_sk);
    }

    /*
     * INTERLEAVED measurement loop.
     * For each i:
     *   1. Measure decaps on fixed (ct, sk) — no keygen/encaps
     *   2. Generate fresh random keypair + ciphertext (OUTSIDE timing window)
     *   3. Measure decaps on random (ct, sk)
     *
     * The keygen+encaps for random occurs between the fixed and random
     * measurements, polluting cache/branch predictor state before the
     * random measurement but not before the fixed measurement.
     */
    for (int i = 0; i < num_traces; i++) {
        /* Measure FIXED — clean cache state */
        uint64_t start_f = read_cntvct();
        OQS_KEM_decaps(kem, ss_fixed, fixed_ct, fixed_sk);
        uint64_t end_f = read_cntvct();

        /* Generate fresh random input (OUTSIDE timing window) */
        OQS_KEM_keypair(kem, rand_pk, rand_sk);
        OQS_KEM_encaps(kem, rand_ct, ss_random, rand_pk);

        /* Measure RANDOM — after keygen+encaps cache pollution */
        uint64_t start_r = read_cntvct();
        OQS_KEM_decaps(kem, ss_random, rand_ct, rand_sk);
        uint64_t end_r = read_cntvct();

        printf("F %llu\n", (unsigned long long)(end_f - start_f));
        printf("R %llu\n", (unsigned long long)(end_r - start_r));

        if (i % 50000 == 0 && i > 0)
            fprintf(stderr, "  interleaved-asymmetric: %d/%d\n", i, num_traces);
    }

    free(fixed_pk);
    free(fixed_sk);
    free(fixed_ct);
    free(rand_pk);
    free(rand_sk);
    free(rand_ct);
    free(ss_fixed);
    free(ss_random);
    OQS_KEM_free(kem);
    return 0;
}

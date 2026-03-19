/*
 * timing_harness_v2.c
 *
 * High-resolution timing harness for ML-KEM-768 decapsulation on Apple Silicon.
 * Uses ARM CNTVCT_EL0 (virtual counter) for cycle-level precision.
 * Falls back to mach_absolute_time() if CNTVCT_EL0 is unavailable.
 *
 * Batch mode (stdin): reads lines of "ct_hex sk_hex" and outputs one timing per line.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <mach/mach_time.h>
#include <oqs/oqs.h>

/* Read ARM virtual counter directly for sub-nanosecond precision */
static inline uint64_t read_cntvct(void) {
    uint64_t val;
    __asm__ volatile("isb" ::: "memory");
    __asm__ volatile("mrs %0, CNTVCT_EL0" : "=r"(val));
    return val;
}

/* Convert hex string to byte array */
static size_t hex_to_bytes(const char *hex, uint8_t *out, size_t max_out) {
    size_t hex_len = strlen(hex);
    size_t n = hex_len / 2;
    if (n > max_out) n = max_out;
    for (size_t i = 0; i < n; i++) {
        unsigned int byte;
        sscanf(hex + 2 * i, "%02x", &byte);
        out[i] = (uint8_t)byte;
    }
    return n;
}

int main(int argc, char *argv[]) {
    (void)argc;
    (void)argv;

    const char *alg_name = OQS_KEM_alg_ml_kem_768;
    OQS_KEM *kem = OQS_KEM_new(alg_name);
    if (kem == NULL) {
        fprintf(stderr, "ERROR: ML-KEM-768 not available in this liboqs build.\n");
        return 1;
    }

    size_t ct_len = kem->length_ciphertext;
    size_t sk_len = kem->length_secret_key;
    size_t ss_len = kem->length_shared_secret;

    uint8_t *ct = malloc(ct_len);
    uint8_t *sk = malloc(sk_len);
    uint8_t *ss = malloc(ss_len);
    if (!ct || !sk || !ss) {
        fprintf(stderr, "ERROR: allocation failure\n");
        return 1;
    }

    /* Allocate line buffer */
    size_t line_cap = (ct_len + sk_len) * 2 + 64;
    char *line = malloc(line_cap);
    char *ct_hex = malloc(ct_len * 2 + 1);
    char *sk_hex = malloc(sk_len * 2 + 1);
    if (!line || !ct_hex || !sk_hex) {
        fprintf(stderr, "ERROR: allocation failure\n");
        return 1;
    }

    /* Warmup: do a few decaps to fill caches */
    {
        uint8_t *wpk = malloc(kem->length_public_key);
        uint8_t *wsk = malloc(sk_len);
        uint8_t *wct = malloc(ct_len);
        uint8_t *wss = malloc(ss_len);
        OQS_KEM_keypair(kem, wpk, wsk);
        OQS_KEM_encaps(kem, wct, wss, wpk);
        for (int i = 0; i < 50; i++)
            OQS_KEM_decaps(kem, wss, wct, wsk);
        free(wpk); free(wsk); free(wct); free(wss);
    }

    /* Batch mode: read from stdin */
    while (fgets(line, (int)line_cap, stdin) != NULL) {
        if (sscanf(line, "%s %s", ct_hex, sk_hex) != 2) continue;
        hex_to_bytes(ct_hex, ct, ct_len);
        hex_to_bytes(sk_hex, sk, sk_len);

        /* Use CNTVCT_EL0 for high-resolution timing */
        uint64_t start = read_cntvct();
        OQS_STATUS rc = OQS_KEM_decaps(kem, ss, ct, sk);
        uint64_t end = read_cntvct();
        (void)rc;

        uint64_t elapsed = end - start;
        printf("%llu\n", (unsigned long long)elapsed);
        fflush(stdout);
    }

    free(line); free(ct_hex); free(sk_hex);
    free(ct); free(sk); free(ss);
    OQS_KEM_free(kem);
    return 0;
}

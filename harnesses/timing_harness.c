/*
 * timing_harness.c
 *
 * High-resolution timing harness for ML-KEM-768 decapsulation on Apple Silicon.
 * Uses mach_absolute_time() for nanosecond-precision userspace timing.
 *
 * Usage: ./timing_harness <ciphertext_hex> <secret_key_hex>
 *   Outputs: decapsulation time in nanoseconds (uint64) to stdout.
 *
 * Batch mode (stdin): reads lines of "ct_hex sk_hex" and outputs one timing per line.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mach/mach_time.h>
#include <oqs/oqs.h>

/* Convert a hex string to a byte array. Returns number of bytes written. */
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
    /* Get mach timebase for ns conversion */
    mach_timebase_info_data_t timebase;
    mach_timebase_info(&timebase);

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

    /* Batch mode: read from stdin */
    if (argc == 1) {
        /* Allocate line buffer large enough for two hex strings */
        size_t line_cap = (ct_len + sk_len) * 2 + 64;
        char *line = malloc(line_cap);
        char *ct_hex = malloc(ct_len * 2 + 1);
        char *sk_hex = malloc(sk_len * 2 + 1);
        if (!line || !ct_hex || !sk_hex) {
            fprintf(stderr, "ERROR: allocation failure\n");
            return 1;
        }

        while (fgets(line, (int)line_cap, stdin) != NULL) {
            if (sscanf(line, "%s %s", ct_hex, sk_hex) != 2) continue;
            hex_to_bytes(ct_hex, ct, ct_len);
            hex_to_bytes(sk_hex, sk, sk_len);

            /* Timing: decapsulation only */
            uint64_t start = mach_absolute_time();
            OQS_STATUS rc = OQS_KEM_decaps(kem, ss, ct, sk);
            uint64_t end = mach_absolute_time();
            (void)rc;

            uint64_t elapsed = end - start;
            uint64_t ns = elapsed * timebase.numer / timebase.denom;
            printf("%llu\n", (unsigned long long)ns);
            fflush(stdout);
        }

        free(line);
        free(ct_hex);
        free(sk_hex);
    }
    /* Single-shot mode */
    else if (argc == 3) {
        hex_to_bytes(argv[1], ct, ct_len);
        hex_to_bytes(argv[2], sk, sk_len);

        uint64_t start = mach_absolute_time();
        OQS_STATUS rc = OQS_KEM_decaps(kem, ss, ct, sk);
        uint64_t end = mach_absolute_time();
        (void)rc;

        uint64_t elapsed = end - start;
        uint64_t ns = elapsed * timebase.numer / timebase.denom;
        printf("%llu\n", (unsigned long long)ns);
    } else {
        fprintf(stderr, "Usage: %s [ct_hex sk_hex]\n", argv[0]);
        fprintf(stderr, "  No args = batch mode (read from stdin)\n");
        return 1;
    }

    free(ct);
    free(sk);
    free(ss);
    OQS_KEM_free(kem);
    return 0;
}

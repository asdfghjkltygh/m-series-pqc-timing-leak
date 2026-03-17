/*
 * timing_harness_vuln.c
 *
 * Timing harness for VULNERABLE liboqs (v0.9.0, pre-KyberSlash fix).
 * Uses Kyber-768 (old naming: OQS_KEM_alg_kyber_768).
 * Otherwise identical to timing_harness_v2.c.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <mach/mach_time.h>
#include <oqs/oqs.h>

static inline uint64_t read_cntvct(void) {
    uint64_t val;
    __asm__ volatile("mrs %0, CNTVCT_EL0" : "=r"(val));
    return val;
}

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
    (void)argc; (void)argv;

    /* v0.9.0 uses old Kyber naming */
    const char *alg_name = OQS_KEM_alg_kyber_768;
    OQS_KEM *kem = OQS_KEM_new(alg_name);
    if (kem == NULL) {
        fprintf(stderr, "ERROR: Kyber-768 not available.\n");
        return 1;
    }

    size_t ct_len = kem->length_ciphertext;
    size_t sk_len = kem->length_secret_key;
    size_t ss_len = kem->length_shared_secret;

    uint8_t *ct = malloc(ct_len);
    uint8_t *sk = malloc(sk_len);
    uint8_t *ss = malloc(ss_len);

    size_t line_cap = (ct_len + sk_len) * 2 + 64;
    char *line = malloc(line_cap);
    char *ct_hex = malloc(ct_len * 2 + 1);
    char *sk_hex = malloc(sk_len * 2 + 1);

    /* Warmup */
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

    while (fgets(line, (int)line_cap, stdin) != NULL) {
        if (sscanf(line, "%s %s", ct_hex, sk_hex) != 2) continue;
        hex_to_bytes(ct_hex, ct, ct_len);
        hex_to_bytes(sk_hex, sk, sk_len);

        uint64_t start = read_cntvct();
        OQS_STATUS rc = OQS_KEM_decaps(kem, ss, ct, sk);
        uint64_t end = read_cntvct();
        (void)rc;

        printf("%llu\n", (unsigned long long)(end - start));
        fflush(stdout);
    }

    free(line); free(ct_hex); free(sk_hex);
    free(ct); free(sk); free(ss);
    OQS_KEM_free(kem);
    return 0;
}

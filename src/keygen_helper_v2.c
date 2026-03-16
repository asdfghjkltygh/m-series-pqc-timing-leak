/*
 * keygen_helper_v2.c
 *
 * Generates ML-KEM-768 keypairs and encapsulated ciphertexts.
 * Outputs richer labeling: the first N secret key coefficients
 * (for Hamming weight and multi-byte targeting).
 *
 * ML-KEM-768 secret key layout:
 *   bytes [0..1151]    = secret vector s (768 coefficients, 12 bits each, packed)
 *   bytes [1152..2303] = public key
 *   bytes [2304..2335] = H(pk)
 *   bytes [2336..2367] = z (implicit rejection seed)
 *
 * We extract the first 16 packed 12-bit coefficients from s for labeling.
 *
 * Output format per sample (one line):
 *   CT_HEX SK_HEX COEFF0 COEFF1 ... COEFF15 HW_SUM
 *
 * Usage: ./keygen_helper_v2 <num_samples>
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <oqs/oqs.h>

static void print_hex(const uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; i++)
        printf("%02x", buf[i]);
}

/* Count bits set (Hamming weight) */
static int popcount16(uint16_t x) {
    int c = 0;
    while (x) { c += x & 1; x >>= 1; }
    return c;
}

/* Decode 12-bit packed coefficients from ML-KEM secret key.
 * Every 3 bytes encode 2 coefficients:
 *   coeff[2i]   = bytes[3i] | (bytes[3i+1] & 0x0F) << 8
 *   coeff[2i+1] = (bytes[3i+1] >> 4) | bytes[3i+2] << 4
 */
static void decode_coefficients(const uint8_t *sk, uint16_t *coeffs, int n) {
    for (int i = 0; i < n / 2; i++) {
        int off = 3 * i;
        coeffs[2 * i]     = (uint16_t)sk[off] | ((uint16_t)(sk[off + 1] & 0x0F) << 8);
        coeffs[2 * i + 1] = (uint16_t)(sk[off + 1] >> 4) | ((uint16_t)sk[off + 2] << 4);
    }
}

#define NUM_TARGET_COEFFS 16

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <num_samples>\n", argv[0]);
        return 1;
    }
    int n = atoi(argv[1]);
    if (n <= 0) { fprintf(stderr, "num_samples must be positive\n"); return 1; }

    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    if (!kem) { fprintf(stderr, "ML-KEM-768 not available\n"); return 1; }

    uint8_t *pk = malloc(kem->length_public_key);
    uint8_t *sk = malloc(kem->length_secret_key);
    uint8_t *ct = malloc(kem->length_ciphertext);
    uint8_t *ss = malloc(kem->length_shared_secret);
    uint16_t coeffs[NUM_TARGET_COEFFS];

    for (int i = 0; i < n; i++) {
        OQS_KEM_keypair(kem, pk, sk);
        OQS_KEM_encaps(kem, ct, ss, pk);

        /* Decode first NUM_TARGET_COEFFS coefficients from secret vector */
        decode_coefficients(sk, coeffs, NUM_TARGET_COEFFS);

        /* Compute total Hamming weight of these coefficients */
        int hw_sum = 0;
        for (int j = 0; j < NUM_TARGET_COEFFS; j++)
            hw_sum += popcount16(coeffs[j]);

        /* Output: CT_HEX SK_HEX COEFF0 ... COEFF15 HW_SUM */
        print_hex(ct, kem->length_ciphertext);
        printf(" ");
        print_hex(sk, kem->length_secret_key);
        for (int j = 0; j < NUM_TARGET_COEFFS; j++)
            printf(" %u", coeffs[j]);
        printf(" %d\n", hw_sum);
        fflush(stdout);
    }

    free(pk); free(sk); free(ct); free(ss);
    OQS_KEM_free(kem);
    return 0;
}

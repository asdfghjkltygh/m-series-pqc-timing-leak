/*
 * keygen_helper_v3.c
 *
 * KyberSlash-aware data generator for ML-KEM-768.
 *
 * Instead of targeting static secret key bits, this version generates
 * data that targets the operations implicated in KyberSlash:
 *
 * 1. "rejection" target: whether the FO transform's re-encryption
 *    comparison succeeds or fails (implicit rejection path).
 *    We create both valid ciphertexts AND mutated (invalid) ones
 *    to trigger the implicit rejection codepath.
 *
 * 2. "message_hw" target: Hamming weight of the decrypted intermediate
 *    message m', which feeds into the division-heavy compression step.
 *
 * Output format per sample (one line):
 *   CT_HEX SK_HEX VALID_CT MESSAGE_HW COEFF0_HW SK_BYTE0
 *
 * Where:
 *   VALID_CT = 1 if ciphertext is valid, 0 if mutated (triggers rejection)
 *   MESSAGE_HW = Hamming weight of the intermediate shared secret
 *   COEFF0_HW = Hamming weight of first secret coefficient
 *   SK_BYTE0 = first byte of secret key (legacy target for comparison)
 *
 * Usage: ./keygen_helper_v3 <num_samples> [mutation_rate]
 *   mutation_rate: fraction of ciphertexts to mutate (default: 0.5)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <oqs/oqs.h>

static void print_hex(const uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; i++)
        printf("%02x", buf[i]);
}

static int popcount_bytes(const uint8_t *buf, size_t len) {
    int hw = 0;
    for (size_t i = 0; i < len; i++) {
        uint8_t b = buf[i];
        while (b) { hw += b & 1; b >>= 1; }
    }
    return hw;
}

static int popcount16(uint16_t x) {
    int c = 0;
    while (x) { c += x & 1; x >>= 1; }
    return c;
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <num_samples> [mutation_rate]\n", argv[0]);
        return 1;
    }

    int n = atoi(argv[1]);
    double mutation_rate = 0.5;
    if (argc >= 3) mutation_rate = atof(argv[2]);

    srand((unsigned)time(NULL));

    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    if (!kem) { fprintf(stderr, "ML-KEM-768 not available\n"); return 1; }

    uint8_t *pk = malloc(kem->length_public_key);
    uint8_t *sk = malloc(kem->length_secret_key);
    uint8_t *ct = malloc(kem->length_ciphertext);
    uint8_t *ss = malloc(kem->length_shared_secret);

    for (int i = 0; i < n; i++) {
        /* Generate fresh keypair */
        OQS_KEM_keypair(kem, pk, sk);
        OQS_KEM_encaps(kem, ct, ss, pk);

        int valid_ct = 1;

        /* With probability mutation_rate, corrupt the ciphertext to trigger
         * the implicit rejection path in FO transform */
        if ((double)rand() / RAND_MAX < mutation_rate) {
            /* Flip random bytes in the ciphertext */
            int num_flips = 1 + rand() % 8;
            for (int f = 0; f < num_flips; f++) {
                size_t pos = rand() % kem->length_ciphertext;
                ct[pos] ^= (1 + rand() % 255);
            }
            valid_ct = 0;
        }

        /* Compute Hamming weight of the shared secret (proxy for message m') */
        int message_hw = popcount_bytes(ss, kem->length_shared_secret);

        /* Decode first coefficient from secret key for HW */
        uint16_t coeff0 = (uint16_t)sk[0] | ((uint16_t)(sk[1] & 0x0F) << 8);
        int coeff0_hw = popcount16(coeff0);

        /* Output */
        print_hex(ct, kem->length_ciphertext);
        printf(" ");
        print_hex(sk, kem->length_secret_key);
        printf(" %d %d %d %d\n", valid_ct, message_hw, coeff0_hw, sk[0]);
        fflush(stdout);
    }

    free(pk); free(sk); free(ct); free(ss);
    OQS_KEM_free(kem);
    return 0;
}

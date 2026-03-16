/*
 * keygen_helper.c
 *
 * Generates ML-KEM-768 keypairs and encapsulated ciphertexts.
 * Outputs hex-encoded: public_key, secret_key, ciphertext, shared_secret
 * Each on its own line, separated by "---" between samples.
 *
 * Usage: ./keygen_helper <num_samples>
 */

#include <stdio.h>
#include <stdlib.h>
#include <oqs/oqs.h>

static void print_hex(const uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; i++)
        printf("%02x", buf[i]);
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <num_samples>\n", argv[0]);
        return 1;
    }

    int n = atoi(argv[1]);
    if (n <= 0) {
        fprintf(stderr, "num_samples must be positive\n");
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

    for (int i = 0; i < n; i++) {
        OQS_STATUS rc;

        /* Generate a fresh keypair for each sample */
        rc = OQS_KEM_keypair(kem, pk, sk);
        if (rc != OQS_SUCCESS) {
            fprintf(stderr, "keypair generation failed at sample %d\n", i);
            return 1;
        }

        /* Encapsulate */
        rc = OQS_KEM_encaps(kem, ct, ss, pk);
        if (rc != OQS_SUCCESS) {
            fprintf(stderr, "encapsulation failed at sample %d\n", i);
            return 1;
        }

        /* Output: pk_hex sk_hex ct_hex ss_hex (one per line within a block) */
        printf("PK:");
        print_hex(pk, kem->length_public_key);
        printf("\n");

        printf("SK:");
        print_hex(sk, kem->length_secret_key);
        printf("\n");

        printf("CT:");
        print_hex(ct, kem->length_ciphertext);
        printf("\n");

        printf("SS:");
        print_hex(ss, kem->length_shared_secret);
        printf("\n");

        /* Extract the target byte from the secret key for labeling.
         * ML-KEM-768: the secret vector s is in the first 768 bytes of sk.
         * We target byte 0 of the secret key (the first coefficient's low byte).
         */
        printf("TARGET_BYTE:%d\n", sk[0]);

        printf("---\n");
        fflush(stdout);
    }

    free(pk);
    free(sk);
    free(ct);
    free(ss);
    OQS_KEM_free(kem);
    return 0;
}

/*
 * tvla_harness_x86.c — x86-64 TVLA Control Experiment
 *
 * Identical to the Apple Silicon TVLA harness, except:
 *   - Uses RDTSC (x86 timestamp counter) instead of CNTVCT_EL0
 *   - Uses CPUID as a serializing instruction to prevent out-of-order
 *     execution from skewing measurements
 *   - Portable across Intel and AMD processors
 *
 * Usage: ./tvla_harness_x86 <fixed|random> <num_traces>
 *        Outputs one cycle count per line to stdout.
 *
 * Build: see build.sh
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <oqs/oqs.h>

/*
 * RDTSC with CPUID serialization.
 * CPUID forces all prior instructions to retire before reading the TSC,
 * preventing out-of-order execution from contaminating the measurement.
 */
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

    /* Warmup — train branch predictor, fill caches */
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

        uint64_t start = rdtsc_start();
        OQS_KEM_decaps(kem, ss, use_ct, use_sk);
        uint64_t end = rdtsc_end();

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

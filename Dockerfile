FROM python:3.12-slim

# Install build dependencies for liboqs and harnesses
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build git \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy repo
COPY . /workspace/

# Build liboqs 0.15.0 from source
RUN git clone --depth 1 --branch 0.15.0 \
        https://github.com/open-quantum-safe/liboqs.git /tmp/liboqs-src && \
    cmake -S /tmp/liboqs-src -B /tmp/liboqs-build \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DCMAKE_C_FLAGS="-O2" \
        -DCMAKE_BUILD_TYPE=Release \
        -DOQS_BUILD_ONLY_LIB=ON \
        -DBUILD_SHARED_LIBS=OFF \
        -G Ninja && \
    ninja -C /tmp/liboqs-build install && \
    rm -rf /tmp/liboqs-src /tmp/liboqs-build

# Compile x86 TVLA harness (if on x86_64)
RUN if [ "$(uname -m)" = "x86_64" ]; then \
        gcc -O2 -march=native \
            -I/usr/local/include \
            -o /workspace/x86-replication/tvla_harness_x86 \
            /workspace/x86-replication/tvla_harness_x86.c \
            /usr/local/lib/liboqs.a \
            -lssl -lcrypto -lm -lpthread && \
        gcc -O2 -march=native \
            -I/usr/local/include \
            -o /workspace/x86-replication/tvla_harness_symmetric_x86 \
            /workspace/x86-replication/tvla_harness_symmetric_x86.c \
            /usr/local/lib/liboqs.a \
            -lssl -lcrypto -lm -lpthread && \
        gcc -O2 -march=native \
            -o /workspace/x86-replication/timer_profile_x86 \
            /workspace/x86-replication/timer_profile_x86.c \
            -lm && \
        gcc -O2 -march=native \
            -I/usr/local/include \
            -o /workspace/x86-replication/tvla_interleaved_symmetric_x86 \
            /workspace/x86-replication/tvla_interleaved_symmetric_x86.c \
            /usr/local/lib/liboqs.a \
            -lssl -lcrypto -lm -lpthread && \
        gcc -O2 -march=native \
            -I/usr/local/include \
            -o /workspace/x86-replication/tvla_interleaved_asymmetric_x86 \
            /workspace/x86-replication/tvla_interleaved_asymmetric_x86.c \
            /usr/local/lib/liboqs.a \
            -lssl -lcrypto -lm -lpthread; \
    fi

# Install sca-triage and analysis dependencies
RUN pip install --no-cache-dir \
    -e /workspace/sca-triage \
    xgboost \
    pandas

# Default: run all reproducible experiments
CMD ["bash", "-c", "\
    echo '=== dudect vs TVLA vs sca-triage ===' && \
    python scripts/dudect_comparison.py && \
    echo '' && \
    echo '=== Raw trace analysis (aggregation masking) ===' && \
    python scripts/phase6_raw_trace_analysis.py && \
    echo '' && \
    echo '=== Sensitivity curve ===' && \
    python scripts/phase7_sensitivity_curve.py && \
    echo '' && \
    echo '=== ML detection floor ===' && \
    python scripts/phase8_ml_detection_floor.py && \
    echo '' && \
    echo '=== Positive control (KyberSlash) ===' && \
    python scripts/analysis_positive_control.py && \
    echo '' && \
    echo '=== Validate all paper claims against data ===' && \
    python scripts/validate_paper_claims.py && \
    echo '' && \
    echo '=== All experiments complete ==='"]

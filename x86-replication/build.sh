#!/bin/bash
#
# build.sh — Build the x86-64 TVLA control experiment
#
# This script:
#   1. Installs liboqs 0.15.0 from source (if not already installed)
#   2. Compiles the TVLA harness against it
#   3. Compiles the timer profiler
#
# Prerequisites:
#   - Linux x86-64 with gcc/clang, cmake, ninja (or make)
#   - OpenSSL development headers (libssl-dev / openssl-devel)
#   - Python 3 with numpy, scipy
#
# Usage:
#   chmod +x build.sh && ./build.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_PREFIX="$SCRIPT_DIR/liboqs-install"

echo "=== x86-64 TVLA Control Experiment Build ==="
echo "  Script dir: $SCRIPT_DIR"
echo "  liboqs install prefix: $INSTALL_PREFIX"

# ---------------------------------------------------------------
# Step 1: Install liboqs 0.15.0 (same version as Apple Silicon experiments)
# ---------------------------------------------------------------
if [ ! -f "$INSTALL_PREFIX/lib/liboqs.a" ] && [ ! -f "$INSTALL_PREFIX/lib64/liboqs.a" ]; then
    echo ""
    echo "[Step 1] Building liboqs 0.15.0 from source..."

    if [ ! -d "$SCRIPT_DIR/liboqs-src" ]; then
        git clone --depth 1 --branch 0.15.0 \
            https://github.com/open-quantum-safe/liboqs.git \
            "$SCRIPT_DIR/liboqs-src"
    fi

    mkdir -p "$SCRIPT_DIR/liboqs-build"
    cd "$SCRIPT_DIR/liboqs-build"

    cmake ../liboqs-src \
        -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
        -DCMAKE_C_FLAGS="-O2" \
        -DCMAKE_BUILD_TYPE=Release \
        -DOQS_BUILD_ONLY_LIB=ON \
        -DBUILD_SHARED_LIBS=OFF

    make -j"$(nproc)" 2>&1 | tail -5
    make install 2>&1 | tail -3

    cd "$SCRIPT_DIR"
    echo "  liboqs installed to $INSTALL_PREFIX"
else
    echo "[Step 1] liboqs already installed at $INSTALL_PREFIX"
fi

# Find the actual lib directory (lib or lib64)
if [ -f "$INSTALL_PREFIX/lib/liboqs.a" ]; then
    LIB_DIR="$INSTALL_PREFIX/lib"
elif [ -f "$INSTALL_PREFIX/lib64/liboqs.a" ]; then
    LIB_DIR="$INSTALL_PREFIX/lib64"
else
    echo "ERROR: Cannot find liboqs.a"
    exit 1
fi

echo "  Using lib dir: $LIB_DIR"

# ---------------------------------------------------------------
# Step 2: Compile TVLA harness
# ---------------------------------------------------------------
echo ""
echo "[Step 2] Compiling TVLA harness..."

# Detect compiler
CC="${CC:-gcc}"
if ! command -v "$CC" &>/dev/null; then
    CC=clang
fi
echo "  Compiler: $CC"

$CC -O2 -march=native \
    -I"$INSTALL_PREFIX/include" \
    -o "$SCRIPT_DIR/tvla_harness_x86" \
    "$SCRIPT_DIR/tvla_harness_x86.c" \
    "$LIB_DIR/liboqs.a" \
    -lssl -lcrypto -lm -lpthread

echo "  Built: $SCRIPT_DIR/tvla_harness_x86"

# ---------------------------------------------------------------
# Step 2b: Compile symmetric TVLA harness
# ---------------------------------------------------------------
echo ""
echo "[Step 2b] Compiling symmetric TVLA harness..."

$CC -O2 -march=native \
    -I"$INSTALL_PREFIX/include" \
    -o "$SCRIPT_DIR/tvla_harness_symmetric_x86" \
    "$SCRIPT_DIR/tvla_harness_symmetric_x86.c" \
    "$LIB_DIR/liboqs.a" \
    -lssl -lcrypto -lm -lpthread

echo "  Built: $SCRIPT_DIR/tvla_harness_symmetric_x86"

# ---------------------------------------------------------------
# Step 3: Compile timer profiler
# ---------------------------------------------------------------
echo ""
echo "[Step 3] Compiling timer profiler..."

$CC -O2 -march=native \
    -o "$SCRIPT_DIR/timer_profile_x86" \
    "$SCRIPT_DIR/timer_profile_x86.c" \
    -lm

echo "  Built: $SCRIPT_DIR/timer_profile_x86"

# ---------------------------------------------------------------
# Done
# ---------------------------------------------------------------
echo ""
echo "=== Build complete ==="
echo ""
echo "To run experiments:"
echo "  python3 tvla_analysis_x86.py --traces 500000    # Asymmetric TVLA"
echo "  python3 ../scripts/intel_symmetric_control.py    # Symmetric control"

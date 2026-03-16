#!/bin/bash
# Build a known-vulnerable version of liboqs (v0.9.0) with KyberSlash timing leaks.
# Compiles with the same Apple Clang -O2 flags as our production build.
# Installs to a local prefix so it doesn't interfere with the system liboqs.

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VULN_DIR="$PROJECT_DIR/liboqs-vulnerable"
INSTALL_PREFIX="$VULN_DIR/install"

echo "=== Building vulnerable liboqs (v0.9.0, pre-KyberSlash fix) ==="
echo "  Project dir: $PROJECT_DIR"
echo "  Install prefix: $INSTALL_PREFIX"

# Clone if not already present
if [ ! -d "$VULN_DIR/liboqs-src" ]; then
    echo "[Step 1] Cloning liboqs v0.9.0..."
    git clone --depth 1 --branch 0.9.0 https://github.com/open-quantum-safe/liboqs.git "$VULN_DIR/liboqs-src"
else
    echo "[Step 1] liboqs source already cloned."
fi

# Build
echo "[Step 2] Building with Apple Clang -O2..."
mkdir -p "$VULN_DIR/build"
cd "$VULN_DIR/build"

cmake ../liboqs-src \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DCMAKE_C_COMPILER=clang \
    -DCMAKE_C_FLAGS="-O2" \
    -DCMAKE_BUILD_TYPE=Release \
    -DOQS_BUILD_ONLY_LIB=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -GUnix\ Makefiles

make -j$(sysctl -n hw.ncpu) 2>&1 | tail -5
make install 2>&1 | tail -3

echo "[Step 3] Verifying installation..."
ls -la "$INSTALL_PREFIX/lib/liboqs.a"
ls "$INSTALL_PREFIX/include/oqs/" | head -5

echo ""
echo "=== Vulnerable liboqs built successfully ==="
echo "  Static lib: $INSTALL_PREFIX/lib/liboqs.a"
echo "  Headers: $INSTALL_PREFIX/include/oqs/"

# Build our harnesses against the vulnerable library
echo ""
echo "[Step 4] Building harnesses against vulnerable liboqs..."

VULN_CFLAGS="-O2 -I$INSTALL_PREFIX/include -I/opt/homebrew/opt/openssl@3/include"
VULN_LDFLAGS="$INSTALL_PREFIX/lib/liboqs.a -L/opt/homebrew/opt/openssl@3/lib -lssl -lcrypto"

echo "  Building timing_harness_vuln..."
clang $VULN_CFLAGS -o "$PROJECT_DIR/src/timing_harness_vuln" \
    "$PROJECT_DIR/src/timing_harness_v2.c" \
    $VULN_LDFLAGS 2>&1

echo "  Building keygen_helper_vuln..."
clang $VULN_CFLAGS -o "$PROJECT_DIR/src/keygen_helper_vuln" \
    "$PROJECT_DIR/src/keygen_helper_v3.c" \
    $VULN_LDFLAGS 2>&1

echo ""
echo "=== All binaries built ==="
echo "  $PROJECT_DIR/src/timing_harness_vuln"
echo "  $PROJECT_DIR/src/keygen_helper_vuln"

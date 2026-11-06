#!/usr/bin/env bash
# Line coverage of firmware/port/ under the host tests: builds an instrumented copy in
# firmware/build-cov, runs the tests against it, and prints gcov's figures per file and in total.
#
#   firmware/tests/coverage.sh
set -euo pipefail

FIRMWARE="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$FIRMWARE/build-cov"
rm -rf "$BUILD"
PETRO_BUILD="$BUILD" PETRO_COVERAGE=ON TEST_MAX_WORKERS="${TEST_MAX_WORKERS:-2}" \
  python -m pytest -q "$FIRMWARE/tests"

if command -v xcrun >/dev/null 2>&1; then GCOV=(xcrun llvm-cov gcov); else GCOV=(gcov); fi
cd "$BUILD/CMakeFiles/petro_port.dir/port"
"${GCOV[@]}" ./*.gcda 2>/dev/null | awk '
  /^File .*\/port\/.*\.c/ { file = $2; gsub(/\047/, "", file); next }
  file && /^Lines executed/ {
    split($2, a, ":"); pct = a[2] + 0; n = $4 + 0
    printf "%-20s %6.2f%% of %d\n", substr(file, match(file, /port\//)), pct, n
    hit += pct * n / 100; total += n; file = ""
  }
  END { if (total) printf "%-20s %6.2f%% of %d\n", "total", 100 * hit / total, total }'

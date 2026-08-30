#!/bin/sh
# Resolves JAVA_HOME at container START time rather than baking an
# architecture-specific path (e.g. .../java-17-openjdk-amd64) in at build
# time. apt installs openjdk under a path that includes the CPU
# architecture (amd64, arm64, ...), so a hardcoded ENV JAVA_HOME would
# silently break on Apple Silicon / arm64 Docker hosts building this same
# Dockerfile. `readlink -f` on the `java` binary that's already on PATH
# works identically on every architecture.
set -e

JAVA_BIN="$(readlink -f "$(command -v java)")"
export JAVA_HOME="$(dirname "$(dirname "$JAVA_BIN")")"

exec "$@"

# syntax=docker/dockerfile:1.4
#
# Nightjar — multi-stage Docker image
# Bundles Dafny 4.x (self-contained .NET 8) + Python 3.11 + Nightjar CLI
#
# Usage:
#   docker run --rm -v $(pwd):/workspace ghcr.io/nightjar-dev/nightjar verify
#   docker run --rm -v $(pwd):/workspace ghcr.io/nightjar-dev/nightjar scan src/ --approve-all
#   docker run --rm -v $(pwd):/workspace ghcr.io/nightjar-dev/nightjar build --target py
#
# NOTE: Do NOT use Alpine — Dafny's self-contained .NET 8 binary requires glibc (musl incompatible).

# Dafny version — verify latest 4.x release at https://github.com/dafny-lang/dafny/releases
ARG DAFNY_VERSION=4.8.0
ARG PYTHON_VERSION=3.11

# ── Stage 1: Download Dafny binary ──────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS dafny-downloader

ARG DAFNY_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /dafny-tmp
RUN curl -fsSL \
    "https://github.com/dafny-lang/dafny/releases/download/v${DAFNY_VERSION}/dafny-${DAFNY_VERSION}-x64-linux.zip" \
    -o dafny.zip \
  && unzip dafny.zip \
  && rm dafny.zip \
  && ls -la

# ── Stage 2: Final image ─────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS final

# Dafny runtime deps.
# libicu-dev installs the correct version for the base image's Debian release.
# libssl3: required for .NET TLS.
# zlib1g: required for .NET compression.
# ca-certificates: required for HTTPS calls in verification pipeline.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libicu-dev \
    libssl3 \
    zlib1g \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Copy Dafny self-contained binary from downloader stage
COPY --from=dafny-downloader /dafny-tmp/dafny /usr/local/dafny

# Symlink and smoke-test
RUN ln -s /usr/local/dafny/dafny /usr/local/bin/dafny \
  && dafny --version

# Install Nightjar
WORKDIR /app
COPY pyproject.toml nightjar.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[dev]"

# Mount point for user's project
VOLUME /workspace
WORKDIR /workspace

ENTRYPOINT ["nightjar"]
CMD ["--help"]

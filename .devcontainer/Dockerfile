FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

ARG TERRAFORM_VERSION=1.17.2
ARG TFLINT_VERSION=0.66.0

RUN apt-get update && apt-get install -y --no-install-recommends unzip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Terraform from HashiCorp releases (verified against the published SHA256SUMS)
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    cd /tmp; \
    curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${arch}.zip"; \
    curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS"; \
    grep "linux_${arch}.zip" "terraform_${TERRAFORM_VERSION}_SHA256SUMS" | sha256sum -c -; \
    unzip -o "terraform_${TERRAFORM_VERSION}_linux_${arch}.zip" -d /usr/local/bin; \
    rm -f /tmp/terraform_*

# tflint (optional lint stage), checked against SHA-256 values pinned here for v0.66.0
# (from the release's checksums.txt). Update them together with TFLINT_VERSION.
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) sum=22be11cadc25cd02401e94c0ccc91aa63467debb8485c2a755d98f4c0a9d1e2e ;; \
      arm64) sum=1105a0a5ddee7cdac7957a3475571a946b839192ea1bc0c722c6c4686001067e ;; \
      *) echo "no pinned tflint checksum for $arch"; exit 1 ;; \
    esac; \
    cd /tmp; \
    curl -fsSLo tflint.zip "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_${arch}.zip"; \
    echo "$sum  tflint.zip" | sha256sum -c -; \
    unzip -o tflint.zip -d /usr/local/bin; \
    rm -f tflint.zip

RUN terraform version && tflint --version

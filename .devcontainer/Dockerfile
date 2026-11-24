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

# tflint (optional lint stage)
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    cd /tmp; \
    curl -fsSLo tflint.zip "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_${arch}.zip"; \
    unzip -o tflint.zip -d /usr/local/bin; \
    rm -f tflint.zip

RUN terraform version && tflint --version

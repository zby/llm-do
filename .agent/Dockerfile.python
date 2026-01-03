FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

# Core tools: git + vim + curl + node for installing uv and AI CLIs
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        vim \
        less \
        bash-completion \
        tzdata \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv (standalone) into /usr/local/bin
# UV_INSTALL_DIR controls destination.
RUN curl -LsSf https://astral.sh/uv/install.sh | \
    env UV_INSTALL_DIR="/usr/local/bin" UV_NO_MODIFY_PATH=1 sh

# Install AI coding agents (preinstall CLI tooling)
RUN npm install -g \
        @anthropic-ai/claude-code \
        @openai/codex

# Writable locations so the container can run as *your* host UID/GID
RUN mkdir -p /uv-cache /uv-python /tmp/home && \
    chmod 777 /uv-cache /uv-python /tmp/home

# Defaults; you can override in compose
ENV UV_CACHE_DIR=/uv-cache \
    UV_PYTHON_INSTALL_DIR=/uv-python \
    UV_PROJECT_ENVIRONMENT=/workspace/.venv

WORKDIR /workspace
CMD ["bash"]

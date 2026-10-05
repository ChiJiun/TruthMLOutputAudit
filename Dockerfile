FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/root/.cargo/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential ca-certificates curl pkg-config libssl-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements-core.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-core.txt

COPY . .

# The default image check covers the fixed-profile accountant and actual Halo2
# circuit. Full EZKL/ML experiments use requirements.txt and are intentionally
# kept outside this smaller reproducibility image.
CMD ["bash", "-lc", "python -m unittest discover -s experiments/discrete_noise_accounting -p 'test*.py' -v && cargo test --release --manifest-path experiments/halo2_verifiable_randomness/Cargo.toml"]

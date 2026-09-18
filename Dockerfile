# CALIPER, deployed.
#
# Two stages, because the interface needs node to build and the server does not
# need node to run. The runtime image carries Python, the package, and the built
# bundle, and nothing else.
#
# What this image deliberately does NOT contain is the supplied case package.
# That is confidential and does not leave the machine that holds it. A deployed
# instance is handed the de-identified item score matrix through the
# CALIPER_OBSERVATIONS_GZ_B64 environment variable, about six kilobytes gzipped,
# and recomputes every figure from it at request time. Nothing here is
# precomputed and nothing is mocked.

FROM node:22-slim AS interface
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=optional
COPY frontend/ ./
RUN npx vite build


FROM python:3.13-slim AS runtime

# Unbuffered so a crash loop shows its reason in the host's log rather than
# dying with the output still in a buffer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY caliper/ ./caliper/
RUN pip install --no-cache-dir .

COPY --from=interface /build/dist ./frontend/dist

# The interface is served from the SAME origin as the API, so there is one
# address for a judge, one QR code for a phone, and no cross origin story.
EXPOSE 8000

# A shell form is needed because the host supplies the port at runtime.
CMD uvicorn caliper.api.main:app --host 0.0.0.0 --port ${PORT:-8000}

# Basis API
#
# Single process, no database, no cache tier. The corpus ships inside the image because the
# product is unintelligible without it and it is only 7.5 MB — fetching it at boot would add
# a network dependency to startup for no benefit.
#
# Measured footprint: 49 MB RSS with the corpus loaded and indexed, 6.5 s to ingest 206 pages
# at startup, ~1.5 ms per search. It fits a free tier.

FROM python:3.12-slim

# PyMuPDF is a hard dependency, not an optional one: without it the unreadable-page surface
# degrades to a placeholder instead of the actual rendered page, which removes the single
# most important interaction in the product. The wheels are manylinux and need no build
# toolchain, so no compiler is installed here.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so the layer caches across code changes.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY data ./data

# Fixtures ride along: they are verbatim recorded provider responses, and they are what makes
# the deployed demo survive Overpass being rate-limited or down — which, during development,
# it repeatedly was.

# Non-root. Nothing here needs privileges.
RUN useradd --create-home --uid 10001 basis \
    && mkdir -p /app/data/corpus/rmp2031-pages \
    && chown -R basis:basis /app
USER basis

EXPOSE 8000

# The platform supplies $PORT; 8000 is the local default. Single worker on purpose: the
# corpus and its index are held in process memory, so a second worker would double the
# footprint and re-ingest for no gain at this scale.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

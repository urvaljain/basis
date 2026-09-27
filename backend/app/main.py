"""Basis API.

The corpus is ingested once at startup and held in memory. That is a deliberate choice for
this slice rather than an oversight: the document is 7.5 MB and yields ~1,000 chunks, the
index is a few hundred kilobytes, and a single process serves a search in ~1.5 ms at 49 MB
resident. Introducing Postgres and pgvector here would add a deployment dependency, a
migration story and a network hop in exchange for capability this scope does not use.

``docs/13-technical-architecture.md`` records the threshold at which that stops being true —
multiple corpora, multiple tenants, or a corpus large enough that startup ingestion becomes
noticeable.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.agents.orchestrator import Orchestrator
from app.api.compare import compare_sites, serialise_comparison
from app.api.uploads import STORE
from app.api.schemas import AnalyseRequest, CompareRequest, CorpusOut, FindingOut
from app.api.serialise import finding_out
from app.ingest.chunker import chunk_document
from app.ingest.pdf_extract import DocumentExtraction, extract_document, render_page_image
from app.ingest.retriever import RegulationIndex
from app.ingest.table_risk import analyse_page
from app.providers import disk_cache
from app.providers.geocode import geocode
from app.providers.llm import get_llm

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("basis")


def _find_data_dir() -> Path:
    """Locate the data directory, which sits at a different depth in the container.

    Locally the layout is ``<repo>/backend/app/main.py`` with data at ``<repo>/data``. The
    image flattens that to ``/app/app/main.py`` with data at ``/app/data``, so a fixed
    ``parents[2]`` resolves to ``/`` and every corpus path silently points at nothing.

    Walking up to find the directory handles both, and `BASIS_DATA_DIR` overrides it for any
    layout neither anticipates. Failing loudly here is deliberate: a missing corpus makes
    every answer wrong rather than absent, and that is far worse than refusing to boot.
    """
    if override := os.getenv("BASIS_DATA_DIR"):
        return Path(override).resolve()

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "corpus"
        if candidate.is_dir():
            return parent / "data"

    raise RuntimeError(
        f"Could not locate the data directory from {here}. Set BASIS_DATA_DIR to the "
        f"directory containing corpus/ and fixtures/."
    )


DATA_DIR = _find_data_dir()
CORPUS_PATH = DATA_DIR / "corpus" / "bengaluru-rmp-2031-vol6-zoning-regulations.pdf"
PAGE_IMAGE_DIR = DATA_DIR / "corpus" / "rmp2031-pages"
EVAL_RESULTS = DATA_DIR / "eval" / "results.json"

CORPUS_TITLE = "Revised Master Plan for Bengaluru 2031 (Draft) — Volume 6: Zoning Regulations"
CORPUS_SOURCE_URL = "https://data.opencity.in/dataset/bda-revised-master-plan-2031"


class AppState:
    doc: DocumentExtraction | None = None
    index: RegulationIndex | None = None
    orchestrator: Orchestrator | None = None
    chunk_count: int = 0
    risky_tables: list[dict[str, Any]] = []
    ingest_ms: int = 0


state = AppState()


@asynccontextmanager
async def lifespan(_: FastAPI):
    started = time.monotonic()
    logger.info("ingesting corpus %s", CORPUS_PATH.name)

    doc = extract_document(
        CORPUS_PATH,
        title=CORPUS_TITLE,
        image_dir=PAGE_IMAGE_DIR,
        render_unreadable=False,  # rendered on first request; see /api/corpus/page/{n}/image
    )
    chunks = chunk_document(doc, "rmp2031")
    index = RegulationIndex(chunks)

    risky = []
    for page in doc.pages:
        if not page.is_readable:
            continue
        for region in analyse_page(page.text):
            if region.is_risky:
                risky.append(
                    {
                        "page": page.page_number,
                        "caption": region.caption,
                        "risk": region.risk.value,
                        "explanation": region.explanation,
                    }
                )

    state.doc = doc
    state.index = index
    state.orchestrator = Orchestrator(index, get_llm())
    state.chunk_count = len(chunks)
    state.risky_tables = risky
    state.ingest_ms = int((time.monotonic() - started) * 1000)

    logger.info(
        "ready: %d pages, %.1f%% text coverage, %d chunks, %d risky tables, %d ms",
        doc.page_count,
        doc.text_coverage * 100,
        len(chunks),
        len(risky),
        state.ingest_ms,
    )
    yield


app = FastAPI(
    title="Basis",
    description="Evidence-first site and regulation intelligence.",
    version="0.1.0",
    lifespan=lifespan,
)

# Origins come from the environment in deployment, with localhost always permitted so a
# developer never has to set anything to run this. `ALLOWED_ORIGINS` is a comma-separated
# list; `ALLOW_ORIGIN_REGEX` covers Vercel's per-deployment preview URLs, which are generated
# per commit and cannot be enumerated in advance.
_LOCAL_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
_configured = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_LOCAL_ORIGINS, *_configured],
    allow_origin_regex=os.getenv("ALLOW_ORIGIN_REGEX") or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def _require_ready() -> tuple[DocumentExtraction, RegulationIndex, Orchestrator]:
    if state.doc is None or state.index is None or state.orchestrator is None:
        raise HTTPException(503, "corpus is still loading")
    return state.doc, state.index, state.orchestrator


@app.get("/api/health")
async def health() -> dict[str, Any]:
    llm = get_llm()
    return {
        "ok": state.doc is not None,
        "corpus_loaded": state.doc is not None,
        "ingest_ms": state.ingest_ms,
        # The interface shows which mode produced any given output, so it must be able to
        # ask. Extractive is a supported mode, not a degraded one.
        "mode": "generative" if llm.available else "extractive",
        "model": llm.model if llm.available else None,
        "fixtures": disk_cache.summary(),
    }


@app.get("/api/corpus", response_model=CorpusOut)
async def corpus() -> CorpusOut:
    doc, _, _ = _require_ready()
    report = doc.coverage_report()
    return CorpusOut(
        title=CORPUS_TITLE,
        sha256=doc.source_sha256,
        page_count=report["page_count"],
        readable_page_count=report["readable_page_count"],
        unreadable_page_count=report["unreadable_page_count"],
        text_coverage=report["text_coverage"],
        total_chars=report["total_chars"],
        total_substitutions=report["total_substitutions"],
        pages_needing_repair=report["pages_needing_repair"],
        unreadable_ranges=[list(r) for r in report["unreadable_ranges"]],
        quality_breakdown=report["quality_breakdown"],
        chunk_count=state.chunk_count,
        risky_tables=state.risky_tables,
        is_draft=True,
    )


@app.get("/api/corpus/page/{page_number}")
async def page_detail(page_number: int) -> dict[str, Any]:
    """One page, with everything known about how well it was read."""
    doc, _, _ = _require_ready()
    page = doc.page(page_number)
    if page is None:
        raise HTTPException(404, f"page {page_number} not found")
    return {
        "page_number": page.page_number,
        "quality": page.quality.value,
        "is_readable": page.is_readable,
        "char_count": page.char_count,
        "substitutions": page.substitutions,
        "corruption_rate": page.corruption_rate,
        "caveat": page.citation_caveat,
        "text": page.text,
        # The raw extraction is exposed so a reader can see exactly what repair changed.
        # Showing only the repaired text would ask them to take the repair on trust, which
        # is the posture this product argues against.
        "raw_text": page.raw_text if page.was_transformed else None,
        "has_image": bool(page.image_path),
        "image_url": f"/api/corpus/page/{page_number}/image" if page.image_path else None,
        "source_url": CORPUS_SOURCE_URL,
    }


@app.get("/api/corpus/page/{page_number}/image")
async def page_image(page_number: int) -> FileResponse:
    """The rendered page — what a human must read when the machine could not.

    Rendered on first request and cached on disk. Pre-rendering all 54 unreadable pages at
    startup cost 108 MB to serve the one or two anyone actually opens.
    """
    doc, _, _ = _require_ready()
    page = doc.page(page_number)
    if page is None or not page.image_path:
        raise HTTPException(404, f"page {page_number} has no rendered image")

    path = PAGE_IMAGE_DIR / page.image_path
    if not path.exists():
        rendered = render_page_image(CORPUS_PATH, page_number, PAGE_IMAGE_DIR)
        if rendered is None:
            raise HTTPException(
                500,
                f"page {page_number} could not be rendered — PDF rasterisation is "
                f"unavailable on this deployment",
            )
        path = PAGE_IMAGE_DIR / rendered

    return FileResponse(path, media_type="image/png")


@app.get("/api/geocode")
async def geocode_endpoint(q: str = Query(min_length=2, max_length=200)) -> dict[str, Any]:
    """Return candidates rather than an answer.

    Silently picking the top hit is how an analysis ends up describing a different place
    with total confidence, and nothing downstream can detect it.
    """
    result = await geocode(q)
    if not result.ok or result.data is None:
        return {"ok": False, "reason": result.unavailable_message(), "candidates": []}
    return {
        "ok": True,
        "ambiguous": result.data.is_ambiguous,
        "limitation": result.limitation,
        "candidates": [
            {
                "display_name": c.display_name,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "place_type": c.place_type,
                "is_area_centroid": c.is_area_centroid,
                "extent_km": c.approximate_extent_km,
                "precision_note": c.precision_note,
            }
            for c in result.data.candidates
        ],
    }


@app.post("/api/analyse", response_model=FindingOut)
async def analyse(request: AnalyseRequest) -> FindingOut:
    _, _, orchestrator = _require_ready()
    finding = await orchestrator.run(
        question=request.question,
        location_query=request.location,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    return finding_out(finding)


@app.post("/api/compare")
async def compare(request: CompareRequest) -> dict[str, Any]:
    """Compare several sites on one question, as an evidence matrix.

    There is no score in the response and no ranking. See ``app/api/compare.py`` for why.
    """
    _, _, orchestrator = _require_ready()
    result = await compare_sites(orchestrator, request.question, request.sites)
    return serialise_comparison(result)


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    """Ingest a user PDF and return an honest report of what could not be read.

    The report comes back before any question is asked, because it is the most useful thing
    the system knows about a document it has just met.
    """
    data = await file.read()
    try:
        document = STORE.add(file.filename or "untitled.pdf", data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001 - a malformed PDF is user input, not a server fault
        logger.exception("upload failed")
        raise HTTPException(
            422,
            f"That PDF could not be read: {type(e).__name__}. It may be encrypted, "
            f"corrupt, or use a structure this pipeline does not handle.",
        ) from e
    return document.report()


@app.get("/api/documents")
async def list_documents() -> dict[str, Any]:
    return {"documents": [d.report() for d in STORE.list()]}


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str) -> dict[str, Any]:
    if not STORE.remove(document_id):
        raise HTTPException(404, "no such document")
    return {"deleted": document_id}


@app.post("/api/documents/{document_id}/ask")
async def ask_document(document_id: str, request: AnalyseRequest) -> dict[str, Any]:
    """Ask a question of an uploaded document.

    Uses the same retrieval and the same honesty rules as the bundled corpus: passage-level
    citations, blind-spot reporting, and table-damage warnings.
    """
    document = STORE.get(document_id)
    if document is None:
        raise HTTPException(404, "no such document")

    result = document.index.search(request.question, top_k=6)
    return {
        "document_id": document_id,
        "filename": document.filename,
        "question": request.question,
        "coverage_note": result.coverage_note(),
        "evidence": [
            {
                "page_number": hit.chunk.page_number,
                "char_start": hit.chunk.char_start,
                "char_end": hit.chunk.char_end,
                "quote": " ".join(hit.chunk.text.split()),
                "citation_label": hit.chunk.citation_label,
                "section": hit.chunk.section_number,
                "text_was_repaired": hit.chunk.text_was_repaired,
                "is_safe_verbatim": hit.chunk.is_safe_to_quote_verbatim,
                "table_risk": hit.chunk.table_risk,
                "caveats": hit.chunk.caveats,
                "why_matched": hit.why_matched(),
                "score": hit.score,
            }
            for hit in result.readable_hits
        ],
        "blind_spots": [
            {
                "page_start": s.page_start,
                "page_end": s.page_end,
                "page_count": s.page_count,
                "descriptor": s.descriptor,
                "matched_terms": s.matched_terms,
            }
            for s in result.relevant_blind_spots
        ],
        "no_evidence_reason": (
            None
            if result.has_usable_evidence
            else (
                "No passage in this document matched the question strongly enough to "
                "present as evidence. Basis does not assemble an answer from loosely "
                "related text."
            )
        ),
    }


@app.get("/api/eval")
async def evaluation() -> dict[str, Any]:
    """The most recent evaluation run.

    Returns 404 rather than placeholder numbers when no run exists. A metrics panel with
    invented figures would be the single most damaging thing this product could ship.
    """
    if not EVAL_RESULTS.exists():
        raise HTTPException(
            404,
            "No evaluation has been run. Execute `python -m app.eval.harness "
            "--json data/eval/results.json` to generate results.",
        )
    import json

    return json.loads(EVAL_RESULTS.read_text(encoding="utf-8"))


@app.get("/api/sources")
async def sources() -> dict[str, Any]:
    """Every data source, its licence and its stated limitation."""
    return {
        "document": {
            "title": CORPUS_TITLE,
            "url": CORPUS_SOURCE_URL,
            "status": "draft",
            "limitation": (
                "A draft master plan. Interpretation of development control regulations is "
                "a licensed professional activity and local authority discretion may "
                "override the written rule."
            ),
        },
        "providers": [
            {
                "name": "Nominatim",
                "provides": "geocoding",
                "licence": "ODbL — © OpenStreetMap contributors",
                "limitation": "Returns area centroids for place names; 1 request/second.",
            },
            {
                "name": "Overpass / OpenStreetMap",
                "provides": "spatial features",
                "licence": "ODbL — © OpenStreetMap contributors",
                "limitation": (
                    "Crowd-sourced. Counts are what has been mapped, not what exists. "
                    "Public instances rate-limit and return 504 under load."
                ),
            },
            {
                "name": "Open-Meteo (ERA5)",
                "provides": "historical climate",
                "licence": "Free for non-commercial use; ERA5 © Copernicus",
                "limitation": (
                    "~9 km reanalysis grid. Values describe the grid cell, not the site."
                ),
            },
            {
                "name": "OpenTopoData (SRTM 30 m)",
                "provides": "elevation",
                "licence": "Public domain — NASA/USGS",
                "limitation": "Cannot resolve plot-level grade; may reflect canopy or rooftops.",
            },
        ],
        "absent": [
            "Zoning / land-use class per parcel — no machine-readable source",
            "FAR, setbacks, ground coverage per plot — published inside PDFs",
            "Valley-zone and eco-sensitive overlay — master-plan drawings only",
            "Official flood hazard layer — none found open",
            "Parcel geometry and ownership — held in revenue records",
        ],
        "fixtures": disk_cache.summary(),
    }

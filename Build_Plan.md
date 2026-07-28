# Project Brief: Diagram-to-draw.io Reconstruction Agent

**Handoff document for autonomous build (Antigravity). Read this whole file before writing any code.**

---

## 0. Mission Statement

Build an agent that takes a **static architecture diagram** (PNG/JPG/PDF/screenshot — typically AI-generated and non-editable) and produces a **fully editable `.drawio` file** that visually and structurally matches the source: same components, same icons, same connections, same layout, same grouping.

**Core design law — do not violate this at any phase:**

> The LLM is only ever allowed to *understand* the diagram (produce structured JSON). It must **never** be asked to directly author `.drawio` XML. All XML is produced by deterministic code from a validated intermediate representation (IR).

Reasoning: LLM-generated XML is unreliable (malformed tags, broken IDs, invalid mxGraph geometry, escaping bugs). A deterministic compiler + validator is the only way to guarantee 100% structurally valid output every time. Every phase below enforces this separation.

---

## 1. Success Criteria (what "done" means)

A run is successful only if all of the following hold for the generated `.drawio`:

1. **XML validity: 100%** — opens in draw.io/diagrams.net with zero errors, no orphaned nodes/edges.
2. **Component completeness** — node count in output == node count detected in input (within confidence threshold).
3. **Connection completeness** — edge count, direction, and (where present) labels match the source.
4. **Editability** — every shape is a real draw.io shape (mxCell) with the correct stencil/icon, not a flattened image.
5. **Visual similarity ≥ 90%** — automated re-render of the output compared against the original image scores above threshold on layout/position/color similarity.
6. **Every field in the IR is traceable** — you can point at any generated shape and say which detected component it came from, with a confidence score.

If any of these fail, the job is "incomplete," not "done with caveats" — it should go through the correction loop (Phase 5+) or be flagged for human review.

---

## 2. Non-Negotiable Architecture

```
Input Image/PDF
      │
      ▼
Preprocessing (OpenCV: denoise, upscale, contrast)
      │
      ▼
OCR (text + bounding boxes)         CV shape/line/arrow detection
      │                                     │
      └───────────────┬─────────────────────┘
                       ▼
        Multimodal LLM (vision) — structured JSON only
                       ▼
              Diagram IR (validated Pydantic model)
                       │
          ┌────────────┼─────────────┐
          ▼            ▼             ▼
   Icon Resolver  Edge Resolver  Layout Normalizer
          └────────────┬─────────────┘
                       ▼
              draw.io XML Compiler (deterministic)
                       ▼
              Structural Validator (schema/XML)
                       ▼
              Headless Render (drawio-desktop CLI / mxgraph)
                       ▼
              Visual Comparator (orig vs rendered)
                       │
              similarity ≥ threshold?
               ┌───────┴────────┐
              YES               NO (max 3 retries)
               │                 │
        Return .drawio     Correction Agent → patch IR → recompile
```

---

## 3. Diagram Intermediate Representation (IR)

This is the contract between "AI understanding" and "deterministic generation." Define it as a **Pydantic model** (backend is Python) so it can double as the LLM's structured-output schema and as the input validated before compiling.

```python
# core/diagram_ir/schema.py
from pydantic import BaseModel, Field
from typing import Literal, Optional

class Style(BaseModel):
    fill: str = "#ffffff"
    stroke: str = "#000000"
    line_style: Literal["solid", "dashed", "dotted"] = "solid"
    font_size: int = 12
    font_color: str = "#000000"

class Node(BaseModel):
    id: str
    type: str                 # e.g. "azure_app_service" — key into icon registry
    label: str
    x: float
    y: float
    width: float
    height: float
    parent: Optional[str] = None   # id of enclosing group, or None for root
    style: Style = Style()
    confidence: float = 1.0
    source_bbox: Optional[list[float]] = None  # original-image pixel bbox, for traceability

class Group(BaseModel):
    id: str
    type: str                 # "azure_vnet", "subnet", "generic_container"
    label: str
    x: float
    y: float
    width: float
    height: float
    parent: Optional[str] = None
    style: Style = Style()

class Edge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    direction: Literal["forward", "backward", "bidirectional", "none"] = "forward"
    style: Literal["solid", "dashed"] = "solid"
    waypoints: list[list[float]] = []
    confidence: float = 1.0

class Canvas(BaseModel):
    width: float
    height: float

class DiagramIR(BaseModel):
    canvas: Canvas
    nodes: list[Node]
    groups: list[Group]
    edges: list[Edge]
    source_image_size: Optional[list[int]] = None  # [w, h] for coordinate normalization
```

Rules to enforce with Pydantic validators (fail fast, don't let bad IR reach the compiler):
- every `edge.source` / `edge.target` must reference an existing node id
- every `node.parent` / `group.parent` must reference an existing group id (or be `None`)
- no cycles in the parent hierarchy
- widths/heights must be > 0
- ids must be unique across nodes + groups combined

---

## 4. Icon Registry

A static, versioned mapping — not something the LLM invents on the fly.

```
assets/icons/
├── azure/     (app-service.svg, front-door.svg, key-vault.svg, postgresql.svg, ...)
├── aws/
├── gcp/
└── generic/   (box, cloud, database-cylinder, actor, arrow-only)

assets/icons/registry.json
{
  "azure_app_service": {
    "aliases": ["app service", "web app", "azure webapp", "app svc"],
    "provider": "azure",
    "drawio_shape": "mscae/App_Services.svg;fillColor=#0078D4;...",
    "default_size": [120, 80]
  }
}
```

The vision model returns a free-text-ish `type` guess; a **fuzzy matcher against `aliases`** (e.g. rapidfuzz) resolves it to a registry key. If similarity < threshold, mark `confidence` low and fall back to a "generic box + label" shape rather than guessing wrong — a labeled generic box is recoverable by the user; a wrong icon is misleading.

---

## 5. draw.io Compiler (the deterministic core — build this FIRST, before any AI)

`core/drawio/compiler.py` — pure functions, fully unit-testable without any AI in the loop:

```
create_canvas(width, height) -> mxGraphModel root
add_node(node: Node) -> mxCell
add_group(group: Group) -> mxCell
add_edge(edge: Edge) -> mxCell
set_parent(cell_id, parent_id)
generate_xml(ir: DiagramIR) -> str
```

Requirements:
- Output must be valid `mxfile > diagram > mxGraphModel > root > mxCell` XML.
- Geometry (`x,y,width,height`) written as `mxGeometry` with correct `relative`/`as="geometry"` attributes.
- Groups become parent `mxCell` with `style="group"` or a container style; children reference `parent="<group-id>"`.
- Escape all label text (XML entity escaping) — this is a common failure point for LLM-authored XML, so the compiler must own it.
- Every generated file must pass `xml.etree.ElementTree.parse()` without error as a first gate.

**Milestone / acceptance test for this phase:** hand-write 5 sample `DiagramIR` JSON files by hand (no AI involved) covering: flat nodes, nested groups (2 levels), edges with waypoints, dashed edges, mixed icon+generic nodes. Compile each, open in draw.io desktop or diagrams.net, and confirm they render correctly and every shape is independently draggable/editable.

---

## 6. Vision / Understanding Stage

Once the compiler is proven, build the "image → IR" side.

### 6.1 Preprocessing
- OpenCV: check resolution, upscale small images, denoise, boost contrast.
- Line/shape/arrow detection (Hough transform for lines, contour detection for boxes) — this gives the LLM a scaffold instead of asking it to eyeball pixel coordinates from scratch.

### 6.2 OCR
- Start with PaddleOCR or EasyOCR (local, free, good multilingual support) for labels + bounding boxes.
- Evaluate Azure AI Document Intelligence layout model as a fallback/comparison if OCR accuracy on real client diagrams is insufficient.

### 6.3 Multimodal LLM call
- Send: original image + OCR text/boxes + detected shape/line boxes.
- **Force structured output** (JSON schema matching a "detection" shape, not the final IR directly) — ask for: component type guess, label, bounding box, parent-container guess, and a relationship list (source/target/label/style) with confidence per item.
- Do not let the model free-write prose in this call; if using an API that supports schema-constrained generation, use it. Otherwise validate + reject/retry on malformed JSON.

### 6.4 IR Assembly
- A deterministic Python step turns the LLM's detection JSON into a `DiagramIR`:
  - resolve `type` via the icon registry fuzzy-matcher
  - normalize LLM's pixel bboxes into layout coordinates (divide by `source_image_size`, then scale to canvas)
  - assign parent-child relationships from nesting/containment logic (a node's bbox contained inside a group's bbox ⇒ parent) — don't just trust the LLM's stated parent, cross check with bbox containment
  - generate stable unique ids

---

## 7. Validation Layers

1. **Structural (cheap, always run):** Pydantic validation of the IR (see §3 rules) + XML parse check on compiled output.
2. **Semantic (count-based):** detected-node-count vs IR-node-count vs compiled-node-count must match at every stage; log a warning/error if any stage drops items.
3. **Visual (expensive, the real signal):** render the compiled `.drawio` back to a PNG (headless draw.io desktop `--export`, or an mxgraph-compatible renderer) and compare against the original:
   - structural similarity (SSIM) on the overall image
   - per-region color histogram comparison
   - text similarity (Levenshtein) between OCR-of-original and OCR-of-generated
   - combine into a single weighted score; threshold e.g. ≥ 0.90 to accept

If visual score is below threshold, emit a structured diff (which node/edge is off, expected vs actual position) and hand it to the **Correction Agent**, which patches only the affected fields in the IR and recompiles. Hard-cap retries (e.g. 3) to bound cost/latency — after that, return the best attempt flagged for human review rather than looping forever.

---

## 8. MVP Scope (do not boil the ocean)

**In scope for v1:**
- Input: PNG/JPG (add PDF page-rasterization after PNG/JPG work reliably)
- Cloud provider: **Azure only**
- Shapes: App Service, VM, VNet/Subnet, Private Endpoint, PostgreSQL/SQL, Storage, Key Vault, Azure OpenAI, AI Search, Front Door, APIM, Load Balancer, Application Gateway, plus a generic box/cloud fallback
- Connections: straight and orthogonal arrows, solid/dashed, single labels
- Nesting: up to 2 levels (region → VNet → subnet → resource)

**Explicitly out of scope for v1** (defer to v2+): AWS/GCP/Kubernetes icon sets, UML/BPMN/ER diagrams, hand-drawn/whiteboard-style diagrams, multi-page PDFs with cross-page connections, real-time collaborative editing.

---

## 9. Human-in-the-Loop UI (don't try for 100% automation in v1)

After generation, show:
- side-by-side original vs. reconstructed preview
- a checklist: "18 components detected / 22 connections detected / 2 uncertain icons"
- click-to-fix on any low-confidence node: dropdown of registry candidates + "other" (manual label)
- buttons: Regenerate, Download `.drawio`

This is both a UX safety net and a **data collection mechanism**: every manual correction a user makes should be logged (`predicted_type` → `corrected_type`) into a `corrections` table. This becomes your fine-tuning/eval dataset later — a genuinely valuable asset over time.

---

## 10. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js + Tailwind | upload, preview, correction UI |
| Backend API | FastAPI (Python) | matches Pydantic IR, easy OpenCV/OCR interop |
| Orchestration | LangGraph or a hand-rolled state machine | keep it simple until you actually need branching complexity |
| Vision LLM | multimodal model via API, schema-constrained JSON output | |
| OCR | PaddleOCR (start), benchmark vs Azure Document Intelligence | |
| CV | OpenCV | line/shape/contour detection |
| Diagram compiler | custom Python module, no external "AI XML" library | this is your core IP |
| Data validation | Pydantic | |
| DB | PostgreSQL | projects, jobs, diagram_versions, corrections |
| Object storage | S3-compatible or Azure Blob | original + every intermediate artifact, versioned |
| Queue | Celery (Redis broker) or Azure Service Bus | vision calls + rendering are slow, don't block the request thread |
| Containers | Docker / docker-compose for local dev | |
| CI/CD | GitHub Actions | run the compiler unit tests + XML validity tests on every PR |
| IaC | Terraform | only once you actually deploy, not for local MVP |

Run everything locally with `docker-compose` first (Next.js + FastAPI + Postgres + Redis + worker). Do not stand up cloud infra until the local pipeline hits the Phase-4 acceptance criteria below.

---

## 11. Repository Structure

```
architecture-agent/
├── frontend/                 Next.js app
├── backend/
│   ├── api/                  FastAPI routes
│   ├── auth/
│   └── jobs/                 Celery task definitions
├── agents/
│   ├── vision_agent/
│   ├── ocr_agent/
│   ├── cv_detector/
│   ├── icon_resolver/
│   ├── edge_resolver/
│   ├── layout_normalizer/
│   ├── correction_agent/
│   └── orchestrator.py
├── core/
│   ├── diagram_ir/            schema.py, validators.py
│   └── drawio/
│       ├── compiler.py
│       ├── styles.py
│       └── xml_validator.py
├── assets/icons/{azure,aws,gcp,generic}/ + registry.json
├── evaluation/
│   ├── benchmark_set/         hand-labeled test diagrams (start with 20)
│   ├── visual_similarity.py
│   └── run_benchmark.py
├── infrastructure/terraform/  (later)
├── tests/
│   ├── test_compiler.py       no-AI, deterministic, run in CI on every commit
│   ├── test_ir_validators.py
│   └── test_end_to_end.py     runs against benchmark_set, checks thresholds
├── docker-compose.yml
└── README.md
```

---

## 12. Known Failure Modes to Design Against

Build tests / guards for each of these explicitly — don't discover them in production:

- **Malformed/garbled LLM JSON** → validate against schema, retry once with a repair prompt, else fail the job cleanly (never pass unvalidated data to the compiler).
- **Duplicate or colliding IDs** from the LLM → always regenerate IDs deterministically in the IR-assembly step; never trust LLM-provided IDs directly.
- **Orphaned edges** (source/target not in node list) → Pydantic validator rejects before compile; log which edge and why.
- **Wrong icon guessed with high confidence** → keep the fuzzy-match threshold conservative; below-threshold matches fall back to a labeled generic shape, never a wrong specific icon.
- **Nested-group misassignment** (LLM says "child of X" but bbox says otherwise) → bbox-containment check overrides stated parent; log a warning if they disagree.
- **Text overlapping shapes / OCR misreads** (e.g. "PostgreSQL" read as "PostgresQL") → cross-check OCR text against the icon-alias list with fuzzy matching, not exact match.
- **Diagram larger than one screen / very dense diagrams** → coordinate normalization must be resolution-independent (see §13); test explicitly with a "30+ component" diagram, not just simple 5-node examples.
- **PDF input with vector-drawn (not raster) diagrams** → rasterize each page at high DPI before the same pipeline; don't try to parse PDF vector paths directly in v1.
- **Multi-page or paginated diagrams** → out of scope for v1; explicitly detect and reject with a clear error rather than silently producing a wrong result.
- **Rendering/validation step itself failing** (headless draw.io export crashes) → treat this as a pipeline error state, not a silent pass; a job must not report "success" if visual comparison couldn't run.
- **Infinite correction loops** → hard cap retries (3), always return the best-scoring attempt with a flag, never hang.

---

## 13. Coordinate Normalization

Normalize every detected bbox against the source image dimensions before laying out on the draw.io canvas, so the pipeline works the same regardless of input resolution:

```
normalized_x = pixel_x / source_image_width
normalized_y = pixel_y / source_image_height
canvas_x = normalized_x * target_canvas_width
canvas_y = normalized_y * target_canvas_height
```

Store `source_image_size` on the IR so this is always traceable/debuggable.

---

## 14. Testing & Benchmark Strategy

Build a benchmark set before scaling AI complexity, so you have a real number to improve against:

- Start with 20 hand-picked Azure architecture diagrams (mix: 8 simple 5-10 components, 8 medium, 4 complex 20+ components) and hand-build the "correct" `.drawio` for each.
- Track per-run metrics: component detection accuracy, icon accuracy, connection accuracy, direction accuracy, container/nesting accuracy, layout similarity (SSIM), XML validity (must stay 100%).
- Run this benchmark in CI (or at least before every significant pipeline change) so regressions are caught immediately, not discovered on a client's diagram.

---

## 15. Build Order (do it in this sequence — do not parallelize prematurely)

1. **draw.io compiler + IR schema**, tested entirely with hand-written IR JSON, zero AI involved. *Exit criterion: 5 hand-crafted diagrams compile to valid, fully-editable `.drawio` files opened and confirmed in draw.io.*
2. **Vision POC**: image → LLM → detection JSON → (manual/simple) IR assembly → compile. Test on 3-5 very simple diagrams. *Exit criterion: end-to-end works for simple cases without OCR/CV yet.*
3. **Add OCR + CV** to improve detection accuracy and give the LLM scaffolding instead of raw pixels.
4. **Icon registry + fuzzy resolver**, coordinate normalization, hierarchy/containment logic.
5. **Structural + semantic validators**, wired into the pipeline as hard gates (not optional checks).
6. **Visual render-and-compare loop** + correction agent, capped retries.
7. **Frontend**: upload, job status, side-by-side preview, click-to-fix, download.
8. **Benchmark suite** running against the growing test set; only now start tuning prompts/thresholds against real numbers.
9. **Containerize, then deploy** (only after local pipeline consistently clears the benchmark thresholds).
10. **Corrections logging** feeding a proprietary dataset for future fine-tuning/eval.

Do not start step 7 (frontend) before steps 1-2 produce a working CLI-level prototype (`python run.py architecture.png -> architecture.drawio`). A UI on top of a broken pipeline just hides the real problem.

---

## 16. First Task for the Agent (start here)

Implement **Build Order step 1** only, as a standalone, dependency-light Python package:

1. `core/diagram_ir/schema.py` — the Pydantic models in §3, with the validators in the bullet list under §3.
2. `core/drawio/compiler.py` — implement `generate_xml(ir: DiagramIR) -> str` per §5.
3. `core/drawio/xml_validator.py` — parses the output XML and checks: well-formed, unique ids, all edge endpoints exist, all parents exist, no negative geometry.
4. `tests/test_compiler.py` — pytest cases for: flat nodes only; one nested group; two-level nested groups; edges with waypoints; dashed edge + label; a node using a real icon vs. a generic fallback box.
5. A tiny `assets/icons/registry.json` with ~10 Azure entries to prove the icon-lookup path works end to end.
6. A README section documenting how to manually open the generated `.drawio` files in diagrams.net to visually confirm correctness.

Do not touch OCR, CV, or any LLM/vision code in this first task. Report back with the test results and at least one generated `.drawio` file so it can be manually opened and verified before proceeding to Build Order step 2.
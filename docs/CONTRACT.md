# CV Writer — Contract

> Write this **before** building. If you can't fill in Inputs / Output
> without naming another module, the boundary is wrong — redraw it.

## Responsibility

Given a candidate's existing CV / career history and a specific job
posting, produce a CV rewritten and reordered to target that role, plus
a short note on what it targeted. The source material is the factual
spine — every role, date, achievement, and skill in the output traces
back to it; tailoring is selection, ordering, and reframing, never
invention. Gaps between what the posting asks for and what the
candidate's record shows are recorded in the note, not filled.

## Inputs — required

- `cv` (str) — the candidate's current CV or career history as plain
  text: one document, the authoritative factual account of their
  history. Plain text only; the caller extracts text from a pasted
  document, a PDF, or another file before calling. This module is never
  handed a file path or a blob. Any identity / contact details at the
  top (name, email, phone, location) are part of this string.
- `job_posting` (str) — the target role as raw posting text: title,
  company, responsibilities, requirements, whatever the posting
  contains. One long string.

## Inputs — optional

Most optional inputs are the candidate's (`tone`, `emphasis`,
`target_length`, `region`, `previous_*`). `house_style` and
`expert_guidance` are different — they are operator configuration,
supplied by whoever runs the module.

- `background_documents` (list[str], default `[]`) — extra written
  context beyond the CV: portfolio notes, project write-ups, a personal
  bio, older roles left off the current CV, detail on a project the CV
  only names. One string per document. The module produces a valid CV
  from `cv` alone; these only enrich it, and every claim they support is
  still held to the grounding rule. The module does no research of its
  own — any company or market context it should use must be supplied
  here.
- `job_title` (str | None, default `None`) — the role title, when it
  isn't obvious from `job_posting`.
- `job_company` (str | None, default `None`) — the hiring company, when
  it isn't obvious from `job_posting`.
- `tone` (str | None, default `None`) — desired voice, e.g.
  "conservative", "punchy", "academic". Free text. Without it the module
  uses a standard professional register.
- `target_length` (str | None, default `None`) — desired finished
  length as free text, e.g. "1 page", "2 pages". A soft target the
  module works toward by trimming or expanding detail. Without it the
  module uses its judgement, guided by `region`.
- `region` (str | None, default `None`) — the CV conventions to follow,
  e.g. "UK", "US", "Germany". Free text. Governs length norms, section
  expectations, and whether to include or strip photo / date of birth /
  nationality / marital status. Defaults to **UK** conventions when
  unset; the module does not infer the region from the posting.
- `emphasis` (list[Emphasis], default `[]`) — points the candidate
  wants led with or foregrounded, most important first. Each `Emphasis`
  has:
  - `point` (str) — the instruction, e.g. "lead with the platform
    migration work".
  - `quote` (str | None, default `None`) — the span of the job posting
    the point answers. Omitted for a point not tied to specific posting
    text.
- `previous_draft` (str | None, default `None`) — a prior tailored CV,
  when this is a revision pass. The module writes a fresh CV without it.
- `previous_feedback` (list[Feedback], default `[]`) — feedback on
  `previous_draft`, one `Feedback` per note (e.g. rows from a UI or a
  database). Ignored unless `previous_draft` is set. Each `Feedback`
  has:
  - `comment` (str) — the change the candidate is asking for.
  - `quote` (str | None, default `None`) — the exact span of the
    previous CV the comment is about. Omitted for general feedback like
    "make it shorter" or "less jargon".
- `house_style` (str | None, default `None`) — the **style**: how the
  prose reads — register, spelling and language locale (British vs
  American English), date format in prose, words to avoid. Cross-cutting:
  the same string an operator hands to every text module. When set it
  replaces the module's bundled default style
  (`cv_writer/prompts/style.md`) wholesale. It governs voice and
  language, not how the CV is built or how long it is (`expert_guidance`)
  and not the country's CV-format conventions (`region`). An explicit
  `tone` overrides it for register. Without it the module uses its
  bundled default style.
- `expert_guidance` (str | None, default `None`) — the **method**: how to
  build the CV — section order, evidence selection, achievement-bullet
  craft, gap handling, and how long and how detailed the CV is.
  Operator-supplied (you, a colleague, or an orchestrator that has
  assembled CV-writing expertise) — never the candidate's. When set it
  replaces the module's built-in method wholesale. It governs structure
  and length, not voice or language (`house_style`); it never overrides
  the standards or the output format; an explicit `tone` /
  `target_length` / `region` still wins. Without it the module uses its
  default, bundled at `cv_writer/prompts/expert_guidance.md`.

### Precedence

The prompt is layered; each layer owns a disjoint domain. Full detail,
and the protocol for changing a layer, is in `docs/PROMPT-LAYERS.md`.

- **Truth, grounding, output shape** — the standards and the output
  format. Nothing overrides them.
- **Structure and length** — `expert_guidance` (or its bundled default).
  An explicit `target_length` / `region` still wins.
- **Voice and language** — `house_style` (or its bundled default). An
  explicit `tone` still wins for register.
- **CV-format conventions** (page norm, photo/DOB/nationality, "CV" vs
  "résumé") — `region`, else UK. Separate from the style's language
  locale.

## Output

- `tailored_cv` (str) — the finished CV, in Markdown, as one document
  with headings. The candidate's identity / contact block from `cv` is
  reproduced verbatim at the top, unchanged; if `cv` contained none, the
  output has none and the note says so. The caller shows it to the
  candidate, renders it, or passes it back in for a further revision
  pass.
- `tailoring_note` (str) — a short "what I targeted" note, in Markdown:
  which requirements from the job posting the CV now addresses and where,
  what was cut or de-emphasised to make room, and any requirement the
  `cv` and `background_documents` don't evidence. A factual record of the
  tailoring and the gaps — not advice, a critique, or a quality
  judgement. Lets the candidate sanity-check the CV, and it's where
  feedback attaches later.
- `cost` (Cost) — what the LLM work behind this CV cost. Present on every
  result. For observability and budgeting; it has no effect on the CV
  itself. Fields:
  - `usd` (float) — estimated dollar cost: the token counts below priced
    against the model's published rate card, which is frozen as
    constants in `_core.py`. A close estimate, not a billing record —
    Anthropic's invoice is authoritative, and the estimate drifts if
    prices move before the constants are updated.
  - `input_tokens` (int) — uncached prompt tokens, billed at the full
    input rate.
  - `output_tokens` (int) — completion tokens, including the model's
    internal thinking tokens (which also bill at the output rate).
  - `cache_read_input_tokens` (int) — prompt tokens served from the
    cache (~0.1x input).
  - `cache_write_input_tokens` (int) — prompt tokens written to the
    cache (~1.25x input).

## Out of scope

- Storing anything — no database, no cache.
- Reading files, PDFs, or DOCX — the caller passes text in.
- Researching the company or the candidate (web search, LinkedIn or
  profile scraping) — extra context arrives as a `background_document`
  or not at all.
- PDF / DOCX / HTML rendering, visual layout, templates, typography —
  the output is Markdown.
- Inventing or inflating experience, skills, dates, or titles to fill
  gaps in the posting's requirements — gaps are recorded in the note
  (strict grounding).
- Giving feedback, critique, coaching, or an assessment of the CV or its
  contents — the module rewrites, it does not evaluate. The
  `tailoring_note` is a factual record of what changed and what the
  source doesn't cover, nothing more.
- ATS score simulation or guaranteeing a keyword-match percentage.
- Writing the cover letter — that is `cover-letter-writer`.
- Judging whether the candidate should apply, or scoring fit for the
  role.
- Translating the CV — it is written in the language of the inputs.
- Managing multiple jobs, applications, or stored CV versions — one CV,
  one posting, per call.

## Storage

None.

## Observability

The module logs one line per call at `INFO` on the `cv_writer` logger —
model, effort, estimated USD, and the token breakdown. It installs no
handlers; the host decides where, or whether, that surfaces. The same
figures are returned on `Output.cost`.

## Open questions

- Structured input. `cv` and `job_posting` are plain text today. A
  separate OCR / extraction module is planned that will hand over
  structured data instead; moving this module to a structured `cv` input
  is a major contract change, deferred until that module is real.
- Structured output. Whether `tailored_cv` should become typed sections
  (so a downstream module can recompose or re-render it) rather than one
  Markdown string. Decide when the first consumer needs it.
- `expert_guidance` default. The bundled CV method
  (`cv_writer/prompts/expert_guidance.md`) still needs writing — section
  order, bullet style, how gaps are handled.
- Company context. The tailoring may benefit from the hiring company's
  priorities. Today that only works if the caller supplies it as a
  `background_document`. Whether an upstream "company brief" module feeds
  it in is an orchestration decision, not this module's — the same open
  question as `cover-letter-writer`.

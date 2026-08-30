# Progress log

Dated entries, newest first. What's done, what's deferred, decisions
made. Read this before assuming anything about the module's current
state.

## 2026-08-30 — Split the prompt into four layers (v0.2.0)

- The single `system.md` mixed identity, rules, and format, and
  `expert_guidance.md` restated rules it should only point at. Split by
  *kind of statement*, one Markdown file per layer in `cv_writer/prompts/`:
  - `system.md` — **who the model is**: role, expertise, mindset,
    orientation. Descriptive only; no rules, no steps, nothing checkable.
  - `standards.md` — **the invariants** the output is held to (grounding,
    no inflation, identity block preserved, every role kept, gaps
    recorded, no evaluation) written as testable assertions, plus the
    **precedence map** (conflicts resolved by domain, with the
    house-style-vs-method tie-break going to the method).
  - `output_contract.md` — **the reply shape** only. Carries the
    `{{SENTINEL}}` placeholder (marker string still owned by `_core.py`).
  - `expert_guidance.md` — **the method** (section order, bullet craft,
    situational calls). Still replaced wholesale by
    `Input.expert_guidance`.
- `_core.py`: `SYSTEM_PROMPT` is now `system.md + standards.md +
  output_contract.md` joined and sentinel-resolved (the cached block);
  `DEFAULT_EXPERT_GUIDANCE` unchanged in role. Prompt section header
  `## How to build this CV` → `## Method`.
- `docs/PROMPT-LAYERS.md` — new. The scope of each file (definition,
  discriminator, "must not contain", example) and the **change protocol**
  the assistant runs on every edit to `cv_writer/prompts/*.md`: mood
  check against per-file red flags, duplication check, precedence
  integrity, mechanics (`test_prompt_layers.py`), verdict. `CLAUDE.md`
  and `README.md` point at it.
- `tests/test_prompt_layers.py` — new. Mechanics only: every layer file
  loads and opens with a heading; `{{SENTINEL}}` lives only in
  `output_contract.md` and resolves; the method stays out of the cached
  system block. `tests/test_run.py` assertions updated to the new
  structure. `uv run pytest` (36) and `uv run lint-imports` pass.
- **Minor bump, not major.** The prompt is restructured but the contract
  in `docs/CONTRACT.md` is unchanged — same inputs, same outputs, same
  guarantees, just sourced from four files instead of two. 0.1.0 → 0.2.0.
- The same four-layer split is to be mirrored in `cover-letter-writer`.

## 2026-08-30 — First working implementation (v0.1.0)

- `docs/CONTRACT.md` agreed first: given a plain-text `cv` and
  `job_posting`, return a `tailored_cv` (Markdown, identity block carried
  through verbatim), a factual `tailoring_note`, and a `cost`. Strict
  grounding — select, reorder, reframe, never invent. Job-tailored, a
  sibling of `cover-letter-writer`.
- Renamed the `capability/` package to `cv_writer/`; updated
  `pyproject.toml` (`name`, `packages`, description; added
  `python-dotenv` to the dev group), `.importlinter`, and the imports in
  `cli.py` / `tests/`. (Committed separately as "Rename to cv-writer".)
- `cv_writer/_contract.py`: `Input` (required `cv`, `job_posting`;
  optional `background_documents`, `job_title`, `job_company`, `tone`,
  `target_length` (str), `region` (str), `emphasis`, `previous_draft`,
  `previous_feedback`, `house_style`, `expert_guidance`). Public
  dataclasses `Emphasis` (point + optional job-posting `quote`),
  `Feedback` (comment + optional previous-CV `quote`), `Cost`. `Output`:
  `tailored_cv`, `tailoring_note`, `cost`.
- `cv_writer/_core.py`: one `claude-sonnet-5` call, `EFFORT="medium"`,
  system prompt cached (`cache_control: ephemeral`). `_render_prompt`
  assembles only the sections with content; the `## Region conventions`
  section always renders, defaulting to UK when none is given. `_parse`
  splits the reply on `SENTINEL` (`===WHAT-I-TARGETED===`) and degrades
  gracefully if it's missing. `_price` turns API token counts into a
  `Cost` off a rate card frozen in `_core.py` (`_USD_PER_*_TOKEN`,
  Sonnet 5 values — update when `MODEL` or prices move). `_generate`
  logs one line per call at `INFO` on the `cv_writer` logger.
- `cv_writer/prompts/`: `system.md` (immutable identity, grounding
  rules, identity-block rule, keep-every-role-header rule, no
  feedback/critique, region default, output format with a `{{SENTINEL}}`
  placeholder) and `expert_guidance.md` (default method: shortlist
  drivers first, summary → skills → experience → education order,
  achievement bullets, region length norms, no invented sections). Read
  at import via `importlib.resources`; ship in the wheel as package data
  (hatchling includes them with no `pyproject.toml` change).
- **Decisions.** Dropped `salary_expectation` / `availability` from the
  `cover-letter-writer` shape (not standard CV content). `max_words`
  became `target_length` (free text — CVs are page-constrained, "2
  pages" beats a word count). `region` is explicit config, never
  inferred from the posting. No `must_include_keywords` input —
  ATS-keyword matching is implicit in the tailoring, not a field.
- **Deferred / open** (in `docs/CONTRACT.md`): structured `cv` input
  from the planned OCR module (a major contract change); structured
  `tailored_cv` output for a downstream recomposer; writing a shipped
  `expert_guidance.md` we're fully happy with; whether company context
  should arrive from an upstream brief (an orchestration decision).
- `cli.py`: flag interface plus interactive mode (`-i`, or auto on a TTY
  with no flags). Flags are task-worded: `--job-posting`, `--cv`,
  `--background` (repeatable), `--tone`, `--target-length`, `--region`,
  `--emphasis` / `--emphasis-file`, `--role-title`, `--company`,
  `--previous-cv`, `--feedback` / `--feedback-on`, `--house-style`,
  `--expert-guidance`. CV to stdout; tailoring note and a one-line cost
  estimate to stderr. `python-dotenv` auto-loads `.env`.
- `examples/`: `job-posting.md` (Senior Platform Engineer, Northwind
  Logistics), `cv.md` (Priya Nair, infra engineer), `emphasis.md`
  (bullet + `>` anchors), `house-style.md` (test copy; the real one is
  the orchestrator's).
- `tests/test_run.py` (23) stubs `_core._generate` so the suite runs
  offline — output shape, sentinel split, required-input validation,
  every optional input's presence/absence, region default + override,
  `expert_guidance` override, cost pass-through, rate-card arithmetic.
  `tests/test_cli.py` (5) pins the emphasis bullet-list parser.
- `uv run pytest` (28) and `uv run lint-imports` pass.
- Live end-to-end run on the bundled demo confirmed: identity block
  carried verbatim, roles reordered to the posting (Argo CD migration
  and cost work pulled up), Halliwell role compressed but its header
  kept, British English + date format from `house_style` applied, Istio
  not oversold, gaps (freight domain, FinOps) recorded in the note, no
  critique in the output. ~$0.026 for the call.

# CV Writer

A standalone capability module. Given a candidate's current CV and a
specific job posting, it rewrites and reorders the CV to target that
role, plus a short note on what it targeted. It works on its own and can
be composed into larger workflows later without changing.

> Part of a larger system. The rules every capability module follows are
> in `CLAUDE.md`. The input/output spec is `docs/CONTRACT.md`. The
> ready-to-run commands are in `docs/USAGE.md`.

## What it does

You hand it the candidate's current CV and one job posting, both as plain
text. It reads the posting the way a recruiter would — past the wording
to the few things that decide the shortlist — and returns a CV rewritten
to put the candidate's evidence for those things where it gets read
first.

Concretely, one call will:

- **Reorder** the experience section so the most relevant role, and the
  most relevant bullets within it, come first.
- **Reweight** roles — four to six bullets on a directly relevant recent
  role, one or two on an old or unrelated one — while keeping every
  role's title / employer / dates line, so no role silently disappears.
- **Rewrite** each bullet to foreground the part this posting cares
  about, using the figures the source gives and inventing none.
- **Rebuild the summary and skills** around the posting's priorities,
  using the posting's own terms where the source supports the same skill
  under another name.
- **Follow a region's CV conventions** (length norm, expected sections,
  whether a photo / DOB / nationality belong). Defaults to UK.
- **Honour explicit steering** — points to lead with (optionally anchored
  to a span of the posting), a tone, a target length, house style — and
  a previous draft plus feedback for a revision pass.

It returns two things:

- `tailored_cv`: the finished CV, in Markdown. The candidate's identity
  block (name, contact details) is carried through verbatim.
- `tailoring_note`: a factual record of which posting requirements the CV
  now addresses and where, what was cut or de-emphasised, and any
  requirement the source doesn't evidence.

### What it will not do

Every claim traces back to the source — tailoring is selection,
ordering, and reframing, never invention; gaps against the posting are
recorded in the note, not filled. It never fetches anything: every input
arrives as an argument, so PDF/DOCX extraction and company research
happen upstream. It gives no feedback, critique, coaching, or assessment
of the candidate. It does not render to PDF/DOCX, simulate an ATS score,
write the cover letter, judge whether to apply, or translate the CV.

## Inputs

Required: `cv` (text) and `job_posting` (text).

Optional (full spec in `docs/CONTRACT.md`):

- The candidate's: `background_documents`, `tone`, `target_length` (free
  text, e.g. "2 pages"), `region` (CV conventions to follow; defaults to
  UK), `emphasis` (points, each optionally anchored to a span of the
  posting), `previous_draft` + `previous_feedback` (for a revision pass),
  `job_title`, `job_company`.
- The operator's: `house_style` (cross-cutting spelling, punctuation and
  phrasing rules, the same file you would give every text tool),
  `expert_guidance` (replaces the built-in method for how to build the
  CV).

## Run it

Needs `uv` and an Anthropic API key in `.env` (`cp .env.example .env`,
then paste the key).

```
# bundled demo
uv run python cli.py \
    --job-posting examples/job-posting.md \
    --cv examples/cv.md \
    --emphasis-file examples/emphasis.md \
    --house-style examples/house-style.md > cv.md

# answer prompts one at a time
uv run python cli.py -i
```

The CV goes to stdout; the tailoring note and a one-line cost estimate go
to stderr, so `> cv.md` saves just the CV. `docs/USAGE.md` covers the
rest (your own files, stdin, revising a draft). `uv run python cli.py -h`
lists every flag.

## Use it from Python

`run(Input(...))` is the whole public surface.

```python
from cv_writer import Input, run

result = run(Input(
    cv=open("cv.md").read(),
    job_posting=open("posting.md").read(),
    house_style=open("house-style.md").read(),   # optional
))
print(result.tailored_cv)
print(result.tailoring_note)
```

Also public: `Emphasis` and `Feedback`, the shapes for the `emphasis` and
`previous_feedback` lists, and `Cost`, returned on `result.cost`.

## Checks

```
uv run pytest          # proves run() honours docs/CONTRACT.md
uv run lint-imports    # fails if an orchestration framework sneaks in
```

## How it composes

A consumer (an orchestrator, or the dashboard) imports `cv_writer.run`
and calls it, pinning this repo as a git tag
(`cv-writer @ git+https://.../cv-writer.git@v0.1.0`). Nothing here
reaches into the consumer.

- `house_style` is meant to be one file the orchestrator owns and passes
  to every text module, so voice stays consistent across the system.
- Company context (mission, strategy, culture) comes in as a
  `background_document`. A sibling `company-researcher` module is
  scaffolded to produce that brief; this module does no research itself.
- A planned OCR/extraction module will hand structured text to `cv`;
  today `cv` is plain text (see `docs/CONTRACT.md` open questions).

## Layout

```
cv_writer/        the module: run(), Input, Output, Emphasis, Feedback, Cost
  _contract.py    the input/output shapes
  _core.py        one LLM call, prompt assembly, reply parsing
  prompts/        editable prompt text, read at import — one file per layer
    system.md           who the model is: role, expertise, mindset
    standards.md        the output invariants + the precedence map
    output_contract.md  the exact reply shape (carries {{SENTINEL}})
    expert_guidance.md  the method — a caller can replace it wholesale
cli.py            run it from a terminal (flags or interactive)
docs/
  CONTRACT.md      the input/output spec
  PROMPT-LAYERS.md what each prompt file may hold + the change protocol
  USAGE.md         ready-to-run commands
  PROGRESS.md      dated change log, newest first
examples/         demo inputs (job-posting.md, cv.md, emphasis.md) and house-style.md
tests/            test_run.py (contract), test_cli.py (parser),
                  test_prompt_layers.py (prompt-file mechanics)
```

## Tuning the prompts

The prompt text is four Markdown files in `cv_writer/prompts/`, split by
**what kind of statement** each holds. `docs/PROMPT-LAYERS.md` is the full
spec; in short:

- `system.md` — who the model is: role, expertise, mindset, orientation.
  No rules, no steps, nothing checkable.
- `standards.md` — the invariants the output is held to (grounding,
  identity block, every role kept, gaps recorded, no evaluation) and the
  precedence map. A caller cannot loosen these.
- `output_contract.md` — the exact reply shape. Keep the `{{SENTINEL}}`
  marker exactly once; `_core.py` fills it with the value `_parse` splits
  on.
- `expert_guidance.md` — the method (section order, bullet craft,
  situational calls). `Input.expert_guidance` replaces it wholesale at
  call time, so edits here only change the default.

`_core.py` builds the cached system block from the first three;
`expert_guidance.md` is sent per call.

**When you edit any of these, run the change protocol in
`docs/PROMPT-LAYERS.md`** — it checks each new line sits in the right
layer, nothing is duplicated, and precedence still resolves.
`tests/test_prompt_layers.py` covers the mechanics (`uv run pytest`).
Prompt-only change, contract unchanged → release as a **patch**; a change
to `standards.md` or `output_contract.md` that alters what a caller can
rely on is a **contract change** (update `docs/CONTRACT.md`, bump major).

There is no default house style: that is cross-cutting config the
orchestrator owns and passes in as `house_style` (see `docs/CONTRACT.md`).

## Releasing a change

Consumers pin a git tag, so every change worth picking up is a tagged
release:

1. `uv run pytest` and `uv run lint-imports` pass.
2. Bump `version` in `pyproject.toml`: patch for a prompt tweak, minor
   for a new optional input, major if `docs/CONTRACT.md` changed in a way
   that breaks callers.
3. Add a `docs/PROGRESS.md` entry, commit, `git tag vX.Y.Z`, push the
   tag.

Full detail in `CLAUDE.md` under "Releasing a new version".

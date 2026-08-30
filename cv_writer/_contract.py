"""The shapes of what goes in and what comes out.

A "type" here just means: the written, named shape of a piece of data —
so the computer (and the next reader) can see exactly what's expected,
instead of everything passing loose bags of values around.

Keep this file small and readable; it mirrors docs/CONTRACT.md. If you
want incoming data validated automatically, swap these dataclasses for
Pydantic models — the rest of the module doesn't change.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Emphasis:
    """One point the candidate wants the CV to lead with or foreground.

    `point` is the instruction ("lead with the platform migration work",
    "surface the team-leadership scope"). `quote`, when present, is the
    exact span of the JOB POSTING the point is anchored to — the
    requirement it answers. Omit `quote` for a general point that isn't
    tied to specific posting text.
    """

    point: str
    quote: str | None = None


@dataclass
class Feedback:
    """One note on `previous_draft`, for a revision pass.

    `comment` is the change the candidate is asking for. `quote`, when
    present, is the exact span of the previous CV the comment is about —
    the "feedback origin". Omit `quote` for general feedback that targets
    nothing specific, e.g. "make it shorter", "less jargon".
    """

    comment: str
    quote: str | None = None


@dataclass
class Input:
    """Everything run() needs to write one tailored CV.

    Required fields first, optional after. Every optional field has a
    default; the module produces a valid CV with only the required two
    supplied.
    """

    # --- required ---
    cv: str
    """The candidate's current CV or career history, as plain text — one
    document, the authoritative factual account of their history. The
    caller extracts text from PDFs/files before calling; this module is
    handed plain text. Any identity / contact details at the top (name,
    email, phone, location) are part of this string."""

    job_posting: str
    """The target role, as raw posting text (title, company,
    responsibilities, requirements — whatever the posting contains). One
    long string."""

    # --- optional: must have a default; the module works without them ---
    background_documents: list[str] = field(default_factory=list)
    """Extra written context beyond the CV — portfolio notes, project
    write-ups, a bio, older roles left off the current CV, detail on a
    project the CV only names. One string per document. The module
    produces a valid CV from `cv` alone; these only enrich it, and every
    claim they support is still held to the grounding rule. The module
    does no research of its own: any company or market context it should
    use must arrive here."""

    job_title: str | None = None
    """The role title, if it isn't obvious from `job_posting`."""

    job_company: str | None = None
    """The hiring company, if it isn't obvious from `job_posting`."""

    tone: str | None = None
    """Desired voice, e.g. "conservative", "punchy", "academic". Free
    text. Without it the module uses a standard professional register."""

    target_length: str | None = None
    """Desired finished length as free text, e.g. "1 page", "2 pages". A
    soft target the module works toward by trimming or expanding detail.
    Without it the module uses its judgement, guided by `region`."""

    region: str | None = None
    """The CV conventions to follow, e.g. "UK", "US", "Germany". Free
    text. Governs length norms, section expectations, and whether to
    include or strip photo / date of birth / nationality / marital
    status. Defaults to UK conventions when unset; the module does not
    infer the region from the posting."""

    emphasis: list[Emphasis] = field(default_factory=list)
    """Points the candidate wants led with or foregrounded, most
    important first. Each `Emphasis` has a `point` and an optional `quote`
    of the job-posting text it answers."""

    previous_draft: str | None = None
    """A prior tailored CV, when this is a revision pass. Optional —
    without it the module writes a fresh CV."""

    previous_feedback: list[Feedback] = field(default_factory=list)
    """Feedback on `previous_draft`, one `Feedback` per note (e.g. rows
    from a UI or database). Each has a `comment` and an optional `quote`
    of the CV text it refers to. Ignored unless `previous_draft` is
    set."""

    # --- operator configuration (not the candidate's input) ---
    house_style: str | None = None
    """Cross-cutting writing conventions — spelling, punctuation,
    phrasing, date format — that apply to all of the operator's generated
    text, not just this CV. Operator-supplied, typically the same string
    handed to every text module. Applied throughout; it outranks the
    method (`expert_guidance` / the default), but not the grounding rules
    or the output format. Without it the module uses its own judgement on
    style."""

    expert_guidance: str | None = None
    """The method for *how* to build the CV — section order, what to lead
    with, how to write an achievement bullet, how to weigh evidence, how
    to handle gaps. Supplied by whoever operates the module (you, a
    colleague, or an orchestrator that has assembled CV-writing
    expertise), not by the candidate. When set it replaces the module's
    built-in guidance wholesale. It does NOT override the grounding
    rules, `house_style`, or the output format, and an explicit `tone` /
    `target_length` / `region` still wins. Without it the module uses its
    default."""


@dataclass
class Cost:
    """What the single LLM call behind one CV cost.

    The token counts are exact, taken straight from the API response.
    `usd` is those counts priced against the model's published rate
    card, which is frozen as constants in `_core.py` — a close estimate
    for budgeting and observability, not a billing record. Anthropic's
    invoice is authoritative, and the estimate drifts if prices change
    before the constants are updated.
    """

    usd: float
    """Estimated dollar cost of the call."""

    input_tokens: int
    """Uncached prompt tokens, billed at the full input rate."""

    output_tokens: int
    """Completion tokens. Includes the model's internal thinking tokens,
    which also bill at the output rate."""

    cache_read_input_tokens: int
    """Prompt tokens served from the cache, billed at ~0.1x input."""

    cache_write_input_tokens: int
    """Prompt tokens written to the cache, billed at ~1.25x input."""


@dataclass
class Output:
    """Everything run() hands back."""

    tailored_cv: str
    """The finished CV, in Markdown, as one document with headings. The
    candidate's identity / contact block from `cv` is reproduced verbatim
    at the top. The caller shows it to the candidate, renders it, or
    passes it on for a further revision pass."""

    tailoring_note: str
    """A short "what I targeted" note, in Markdown: which requirements
    from the job posting the CV now addresses and where, what was cut or
    de-emphasised, and any requirement the CV and background documents
    don't evidence. A factual record of the tailoring and the gaps — not
    advice or a critique. Lets the candidate sanity-check the CV, and
    it's where feedback attaches later."""

    cost: Cost
    """What the LLM call cost — token counts and an estimated dollar
    figure. Present on every result. For observability and budgeting; it
    has no effect on the CV."""

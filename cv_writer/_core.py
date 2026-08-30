"""Internal implementation. Nothing here is public — callers only ever
touch cv_writer.run().

The job: given an Input, produce an Output. One LLM call does the work;
everything around it is prompt assembly and parsing the two-part reply.
"""

from __future__ import annotations

import logging
from importlib import resources

import anthropic

from ._contract import Cost, Emphasis, Feedback, Input, Output

_log = logging.getLogger("cv_writer")

MODEL = "claude-sonnet-5"
MAX_TOKENS = 16_000

# Tailoring a CV from supplied material is a drafting task, not a hard
# reasoning one. "medium" effort keeps the model's thinking budget
# modest — thinking tokens bill at the output rate — without visibly
# hurting quality. Raise to "high" if drafts start missing the brief.
EFFORT = "medium"

# USD per token for MODEL, from Anthropic's published rate card. Update
# these whenever MODEL changes or the prices move — they are the only
# thing that makes Cost.usd more than a guess. Cache reads bill at ~0.1x
# the input rate; 5-minute cache writes at ~1.25x.
_USD_PER_INPUT_TOKEN = 2.00 / 1_000_000
_USD_PER_OUTPUT_TOKEN = 10.00 / 1_000_000
_USD_PER_CACHE_READ_TOKEN = 0.20 / 1_000_000
_USD_PER_CACHE_WRITE_TOKEN = 2.50 / 1_000_000

# The model returns the CV, this marker, then the tailoring note.
SENTINEL = "===WHAT-I-TARGETED==="

# The prompt text lives in editable Markdown alongside this module, in
# prompts/ — one file per layer. It ships in the wheel as package data and
# is read once here, at import. The scope of each file, and the protocol
# for changing one, is in docs/PROMPT-LAYERS.md.
#
# Cached system block (immutable, identical on every call):
#   system.md          — who the model is: role, expertise, mindset,
#                        orientation. No rules, no steps, nothing checkable.
#   standards.md       — the invariants the output is held to, and the
#                        precedence map. A caller cannot loosen these.
#   output_contract.md — the exact reply shape. Carries a {{SENTINEL}}
#                        placeholder, filled below with the value _parse
#                        splits on.
#
# Per call (not cached):
#   expert_guidance.md — the default method. Input.expert_guidance replaces
#                        it wholesale; the three files above still hold.
_PROMPTS = resources.files(__package__) / "prompts"
_SYSTEM_FILES = ("system.md", "standards.md", "output_contract.md")
SYSTEM_PROMPT = "\n\n".join(
    (_PROMPTS / name).read_text(encoding="utf-8").strip() for name in _SYSTEM_FILES
).replace("{{SENTINEL}}", SENTINEL)
DEFAULT_EXPERT_GUIDANCE = (_PROMPTS / "expert_guidance.md").read_text(encoding="utf-8")


def _build(data: Input) -> Output:
    _validate(data)
    raw, cost = _generate(SYSTEM_PROMPT, _render_prompt(data))
    return _parse(raw, cost)


def _validate(data: Input) -> None:
    if not data.cv.strip():
        raise ValueError("cv is empty")
    if not data.job_posting.strip():
        raise ValueError("job_posting is empty")


def _render_prompt(data: Input) -> str:
    parts: list[str] = []

    house_style = (data.house_style or "").strip()
    if house_style:
        parts.append(f"## House style\n\n{house_style}")

    guidance = (data.expert_guidance or "").strip() or DEFAULT_EXPERT_GUIDANCE
    parts.append(f"## Method\n\n{guidance}")

    region = (data.region or "").strip()
    if region:
        parts.append(f"## Region conventions\n\nFollow {region} CV conventions.")
    else:
        parts.append(
            "## Region conventions\n\n"
            "Follow United Kingdom CV conventions (no region was supplied)."
        )

    header = "\n".join(
        line
        for line in (
            f"Title: {data.job_title}" if data.job_title else "",
            f"Company: {data.job_company}" if data.job_company else "",
        )
        if line
    )
    posting = f"{header}\n\n{data.job_posting}".strip() if header else data.job_posting.strip()
    parts.append(f"## Job posting\n\n{posting}")

    parts.append(f"## Candidate CV / career history\n\n{data.cv.strip()}")

    extras = [doc.strip() for doc in data.background_documents if doc.strip()]
    if extras:
        rendered = "\n\n".join(
            f"### Document {i}\n\n{doc}" for i, doc in enumerate(extras, start=1)
        )
        parts.append(
            "## Supplementary background (context only; the CV is authoritative)\n\n"
            + rendered
        )

    if data.tone:
        parts.append(f"## Tone\n\n{data.tone}")

    if data.target_length and data.target_length.strip():
        parts.append(
            f"## Target length\n\nAim for about {data.target_length.strip()}."
        )

    emphasis = _render_emphasis(data.emphasis)
    if emphasis:
        parts.append(
            f"## Points to emphasise or foreground (most important first)\n\n{emphasis}"
        )

    if data.previous_draft and data.previous_draft.strip():
        parts.append(f"## Previous draft (revise this)\n\n{data.previous_draft.strip()}")
        notes = _render_feedback(data.previous_feedback)
        if notes:
            parts.append(f"## Feedback on the previous draft\n\n{notes}")

    return "\n\n".join(parts)


def _render_emphasis(items: list[Emphasis]) -> str:
    lines: list[str] = []
    for i, item in enumerate((it for it in items if it.point.strip()), start=1):
        lines.append(f"{i}. {item.point.strip()}")
        quote = (item.quote or "").strip()
        if quote:
            lines.append(f'   (answers this in the job posting: "{quote}")')
    return "\n".join(lines)


def _render_feedback(items: list[Feedback]) -> str:
    lines: list[str] = []
    for item in items:
        comment = item.comment.strip()
        if not comment:
            continue
        quote = (item.quote or "").strip()
        if quote:
            lines.append(f'- On this text — "{quote}":\n  {comment}')
        else:
            lines.append(f"- General: {comment}")
    return "\n".join(lines)


def _generate(system: str, prompt: str) -> tuple[str, Cost]:
    """The one outbound call: the LLM this module uses internally.

    Returns the raw reply text and what the call cost. The cost is also
    logged, at INFO on the `cv_writer` logger, so it can be seen without
    threading the Output all the way back.
    """
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        output_config={"effort": EFFORT},
        # The system prompt is identical on every call; caching it means
        # runs that cluster (a batch, a revision pass) re-read the fixed
        # prefix at a fraction of the input price.
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    cost = _price(message.usage)
    _log.info(
        "cv generated on %s (effort=%s): $%.4f est. — "
        "%d input, %d output, %d cache-read, %d cache-write tokens",
        MODEL,
        EFFORT,
        cost.usd,
        cost.input_tokens,
        cost.output_tokens,
        cost.cache_read_input_tokens,
        cost.cache_write_input_tokens,
    )
    return text, cost


def _price(usage: anthropic.types.Usage) -> Cost:
    """Turn the API's token counts into a Cost, priced off the rate card."""
    read = getattr(usage, "cache_read_input_tokens", None) or 0
    write = getattr(usage, "cache_creation_input_tokens", None) or 0
    usd = (
        usage.input_tokens * _USD_PER_INPUT_TOKEN
        + usage.output_tokens * _USD_PER_OUTPUT_TOKEN
        + read * _USD_PER_CACHE_READ_TOKEN
        + write * _USD_PER_CACHE_WRITE_TOKEN
    )
    return Cost(
        usd=round(usd, 6),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_input_tokens=read,
        cache_write_input_tokens=write,
    )


def _parse(raw: str, cost: Cost) -> Output:
    cv, _, note = raw.partition(SENTINEL)
    return Output(
        tailored_cv=cv.strip(),
        tailoring_note=note.strip(),
        cost=cost,
    )

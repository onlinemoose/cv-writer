"""Internal implementation. Nothing here is public — callers only ever
touch cv_writer.run().

The job: given an Input, produce an Output. One LLM call does the work;
everything around it is prompt assembly and parsing the two-part reply.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from importlib import resources

import anthropic

from ._contract import Cost, Emphasis, Feedback, Input, Output, Progress

_log = logging.getLogger("cv_writer")

ProgressFn = Callable[[Progress], None]

# How often, at most, to ping an on_progress callback while text streams.
_PROGRESS_EVERY_S = 0.5

MODEL = "claude-sonnet-5"
# Room for a long regional CV (a German Lebenslauf runs long), the
# tailoring note, and medium-effort thinking — without the 16k tail that
# let a slow run overrun a caller's request timeout. The reply is
# streamed (see _generate), so this is a size bound, not a latency guard.
MAX_TOKENS = 8_000

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
# Per call (not cached, because a caller can replace either):
#   style.md           — the default voice and language conventions.
#                        Input.house_style replaces it wholesale.
#   expert_guidance.md — the default method. Input.expert_guidance
#                        replaces it wholesale.
# The three files above still hold whichever of these is in play.
_PROMPTS = resources.files(__package__) / "prompts"
_SYSTEM_FILES = ("system.md", "standards.md", "output_contract.md")
SYSTEM_PROMPT = "\n\n".join(
    (_PROMPTS / name).read_text(encoding="utf-8").strip() for name in _SYSTEM_FILES
).replace("{{SENTINEL}}", SENTINEL)
DEFAULT_STYLE = (_PROMPTS / "style.md").read_text(encoding="utf-8")
DEFAULT_EXPERT_GUIDANCE = (_PROMPTS / "expert_guidance.md").read_text(encoding="utf-8")


def _build(data: Input, on_progress: ProgressFn | None = None) -> Output:
    _validate(data)
    raw, cost = _generate(SYSTEM_PROMPT, _render_prompt(data), on_progress)
    return _parse(raw, cost)


def _validate(data: Input) -> None:
    if not data.cv.strip():
        raise ValueError("cv is empty")
    if not data.job_posting.strip():
        raise ValueError("job_posting is empty")


def _render_prompt(data: Input) -> str:
    parts: list[str] = []

    style = (data.house_style or "").strip() or DEFAULT_STYLE
    parts.append(f"## Style\n\n{style}")

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


def _generate(
    system: str, prompt: str, on_progress: ProgressFn | None = None
) -> tuple[str, Cost]:
    """The one outbound call: the LLM this module uses internally.

    Returns the raw reply text and what the call cost. The cost is also
    logged, at INFO on the `cv_writer` logger, so it can be seen without
    threading the Output all the way back.
    """
    # A full-length CV is minutes of generation. Stream the reply so a
    # large max_tokens can't trip the HTTP read timeout, and bound the
    # wait: a stalled request should fail in minutes, not ride the SDK's
    # 10-minute default. One retry rides out a transient 429 / 5xx.
    client = anthropic.Anthropic(
        timeout=anthropic.Timeout(300.0, connect=10.0),
        max_retries=1,
    )
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        output_config={"effort": EFFORT},
        # The system prompt is identical on every call; caching it means
        # runs that cluster (a batch, a revision pass) re-read the fixed
        # prefix at a fraction of the input price.
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        if on_progress is None:
            message = stream.get_final_message()
        else:
            message = _drain_with_progress(stream, on_progress)
    if message.stop_reason == "max_tokens":
        # The reply was cut off mid-document; _parse would silently yield a
        # half CV and an empty note. Fail loudly so the caller can retry
        # with a shorter target length.
        raise RuntimeError(
            "the model hit the length cap before finishing — try a shorter "
            "target length"
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


def _drain_with_progress(stream: anthropic.MessageStream, on_progress: ProgressFn):
    """Consume the text stream, pinging `on_progress` at most every
    `_PROGRESS_EVERY_S`, then return the finalised message. Only the
    ping cadence is added; the message the SDK assembles is unchanged."""
    parts: list[str] = []
    started = time.monotonic()
    last = 0.0
    for chunk in stream.text_stream:
        parts.append(chunk)
        now = time.monotonic()
        if now - last >= _PROGRESS_EVERY_S:
            last = now
            _ping(on_progress, "".join(parts), now - started)
    _ping(on_progress, "".join(parts), time.monotonic() - started)
    return stream.get_final_message()


def _ping(on_progress: ProgressFn, text: str, seconds: float) -> None:
    try:
        on_progress(
            Progress(
                characters=len(text),
                words=len(text.split()),
                seconds=round(seconds, 1),
            )
        )
    except Exception:
        # A caller's progress sink must never break generation.
        _log.warning("on_progress raised; continuing without it", exc_info=True)


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

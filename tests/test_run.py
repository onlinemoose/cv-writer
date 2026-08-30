"""Proves run() honours the contract in docs/CONTRACT.md.

The LLM call is stubbed (`_core._generate`) so these run offline and
assert on how the module assembles the prompt and parses the reply —
one test per promise the module makes.
"""

import pytest

from cv_writer import Cost, Emphasis, Feedback, Input, Output, run
from cv_writer import _core

JOB = "Senior Backend Engineer at Acme. You will own our payments service. Requires Python and Postgres."
CV = (
    "Jane Doe\njane@example.com | +44 7700 900000 | London\n\n"
    "8 years building payment systems in Python. Led the Stripe migration at Fintech Co. "
    "Deep Postgres experience."
)

REPLY = (
    f"# Jane Doe\njane@example.com | +44 7700 900000 | London\n\n"
    f"## Experience\n\nMy tailored CV body.\n"
    f"{_core.SENTINEL}\n- Python: 8 years at Fintech Co\n- Gap: no Go experience"
)

STUB_COST = Cost(
    usd=0.0123,
    input_tokens=1000,
    output_tokens=200,
    cache_read_input_tokens=0,
    cache_write_input_tokens=1500,
)


@pytest.fixture
def stub_llm(monkeypatch):
    """Capture the prompt sent to the model; return a canned two-part reply."""
    seen = {}

    def fake_generate(system: str, prompt: str) -> tuple[str, Cost]:
        seen["system"] = system
        seen["prompt"] = prompt
        return REPLY, STUB_COST

    monkeypatch.setattr(_core, "_generate", fake_generate)
    return seen


def test_run_returns_the_output_type(stub_llm):
    result = run(Input(cv=CV, job_posting=JOB))
    assert isinstance(result, Output)
    assert isinstance(result.tailored_cv, str)
    assert isinstance(result.tailoring_note, str)


def test_run_splits_cv_from_tailoring_note(stub_llm):
    result = run(Input(cv=CV, job_posting=JOB))
    assert "My tailored CV body." in result.tailored_cv
    assert _core.SENTINEL not in result.tailored_cv
    assert "no Go experience" in result.tailoring_note


def test_run_works_with_only_the_required_inputs(stub_llm):
    # Rule 7: the module must produce a valid result when only the
    # required inputs (cv + job_posting) are supplied.
    result = run(Input(cv=CV, job_posting=JOB))
    assert result.tailored_cv != ""
    assert result.tailoring_note != ""


def test_required_inputs_reach_the_model(stub_llm):
    run(Input(cv=CV, job_posting=JOB))
    assert JOB in stub_llm["prompt"]
    assert CV in stub_llm["prompt"]


def test_background_documents_are_optional_and_passed_through(stub_llm):
    # Absent by default...
    run(Input(cv=CV, job_posting=JOB))
    assert "## Supplementary background" not in stub_llm["prompt"]

    # ...included, and clearly subordinate to the CV, when supplied.
    run(
        Input(
            cv=CV,
            job_posting=JOB,
            background_documents=["Portfolio: built an idempotent ledger.", ""],
        )
    )
    prompt = stub_llm["prompt"]
    assert "## Candidate CV / career history" in prompt
    assert "## Supplementary background" in prompt
    assert "built an idempotent ledger" in prompt


def test_emphasis_carries_points_and_optional_job_posting_anchors(stub_llm):
    run(
        Input(
            cv=CV,
            job_posting=JOB,
            emphasis=[
                Emphasis(point="lead with payments", quote="own our payments service"),
                Emphasis(point="foreground the team-leadership scope"),
            ],
        )
    )
    prompt = stub_llm["prompt"]
    assert "## Points to emphasise or foreground (most important first)" in prompt
    assert "1. lead with payments" in prompt  # priority order preserved
    assert '"own our payments service"' in prompt  # the anchor is shown
    assert "2. foreground the team-leadership scope" in prompt


def test_target_length_is_optional_and_rendered_when_present(stub_llm):
    run(Input(cv=CV, job_posting=JOB))
    assert "## Target length" not in stub_llm["prompt"]

    run(Input(cv=CV, job_posting=JOB, target_length="2 pages"))
    prompt = stub_llm["prompt"]
    assert "## Target length" in prompt
    assert "2 pages" in prompt


def test_region_defaults_to_uk_and_is_overridable(stub_llm):
    # No region supplied -> the section still renders, defaulting to UK.
    run(Input(cv=CV, job_posting=JOB))
    prompt = stub_llm["prompt"]
    assert "## Region conventions" in prompt
    assert "United Kingdom" in prompt

    # Region supplied -> carried through as given.
    run(Input(cv=CV, job_posting=JOB, region="US"))
    prompt = stub_llm["prompt"]
    assert "Follow US CV conventions." in prompt
    assert "United Kingdom" not in prompt


def test_default_expert_guidance_is_used_when_none_is_supplied(stub_llm):
    run(Input(cv=CV, job_posting=JOB))
    prompt = stub_llm["prompt"]
    assert "## Method" in prompt
    assert "Reverse-chronological" in prompt  # from DEFAULT_EXPERT_GUIDANCE


def test_house_style_is_optional_and_precedes_the_method(stub_llm):
    # Absent by default.
    run(Input(cv=CV, job_posting=JOB))
    assert "## House style" not in stub_llm["prompt"]

    # Supplied: rendered, and ahead of the method so its precedence reads.
    run(Input(cv=CV, job_posting=JOB, house_style="Write in British English. No em dashes."))
    prompt = stub_llm["prompt"]
    assert "## House style" in prompt
    assert "No em dashes." in prompt
    assert prompt.index("## House style") < prompt.index("## Method")
    # The standards state the house style's place in the precedence order.
    assert "house style" in stub_llm["system"]


def test_system_block_is_assembled_from_the_three_immutable_layers(stub_llm):
    run(Input(cv=CV, job_posting=JOB))
    system = stub_llm["system"]
    # system.md — mindset, not rules
    assert "You write for that reader." in system
    # standards.md — the invariants and the precedence map
    assert "**Grounding.**" in system
    assert "**Identity block preserved.**" in system
    assert "**Every role kept.**" in system
    assert "**No evaluation of the candidate.**" in system
    assert "## Precedence" in system
    assert "United Kingdom" in system  # region default lives in precedence
    # output_contract.md — the reply shape, with the sentinel resolved
    assert "Return exactly this and nothing else:" in system
    assert "This format is fixed." in system


def test_prompts_are_loaded_from_package_data(stub_llm):
    # The prompt text lives in cv_writer/prompts/*.md, read at import.
    # The {{SENTINEL}} placeholder in output_contract.md must be resolved.
    run(Input(cv=CV, job_posting=JOB))
    system = stub_llm["system"]
    assert "{{SENTINEL}}" not in system
    assert _core.SENTINEL in system
    assert _core.DEFAULT_EXPERT_GUIDANCE.strip() in stub_llm["prompt"]


def test_expert_guidance_replaces_the_method_but_not_the_immutable_layers(stub_llm):
    run(
        Input(
            cv=CV,
            job_posting=JOB,
            expert_guidance="List every role as a single line, no bullets.",
        )
    )
    prompt = stub_llm["prompt"]
    assert "List every role as a single line, no bullets." in prompt
    assert "Reverse-chronological" not in prompt  # the default method is gone
    # the standards and the output contract still hold — they are in the system block
    assert "**Grounding.**" in stub_llm["system"]
    assert "**No inflation.**" in stub_llm["system"]
    assert _core.SENTINEL in stub_llm["system"]


def test_optional_inputs_are_passed_through_when_present(stub_llm):
    run(
        Input(
            cv=CV,
            job_posting=JOB,
            tone="conservative",
            emphasis=[Emphasis(point="lead with the Stripe migration")],
            target_length="1 page",
            previous_draft="An earlier attempt.",
            previous_feedback=[Feedback(comment="too generic")],
        )
    )
    prompt = stub_llm["prompt"]
    assert "conservative" in prompt
    assert "lead with the Stripe migration" in prompt
    assert "1 page" in prompt
    assert "An earlier attempt." in prompt
    assert "too generic" in prompt


def test_feedback_carries_general_notes_and_quoted_notes(stub_llm):
    run(
        Input(
            cv=CV,
            job_posting=JOB,
            previous_draft="## Summary\nA highly motivated professional.",
            previous_feedback=[
                Feedback(comment="make it shorter"),
                Feedback(
                    quote="A highly motivated professional",
                    comment="cut this — it says nothing",
                ),
            ],
        )
    )
    prompt = stub_llm["prompt"]
    assert "## Feedback on the previous draft" in prompt
    assert "General: make it shorter" in prompt
    assert '"A highly motivated professional"' in prompt
    assert "cut this — it says nothing" in prompt


def test_feedback_is_ignored_without_a_previous_draft(stub_llm):
    run(
        Input(
            cv=CV,
            job_posting=JOB,
            previous_feedback=[Feedback(comment="make it shorter")],
        )
    )
    assert "## Feedback on the previous draft" not in stub_llm["prompt"]


def test_optional_sections_absent_when_not_supplied(stub_llm):
    run(Input(cv=CV, job_posting=JOB))
    prompt = stub_llm["prompt"]
    assert "## Tone" not in prompt
    assert "## Target length" not in prompt
    assert "## Previous draft" not in prompt


def test_reply_without_sentinel_becomes_the_cv(stub_llm, monkeypatch):
    monkeypatch.setattr(
        _core, "_generate", lambda system, prompt: ("Just a CV, no marker.", STUB_COST)
    )
    result = run(Input(cv=CV, job_posting=JOB))
    assert result.tailored_cv == "Just a CV, no marker."
    assert result.tailoring_note == ""


def test_output_carries_the_call_cost(stub_llm):
    result = run(Input(cv=CV, job_posting=JOB))
    assert isinstance(result.cost, Cost)
    assert result.cost.usd == STUB_COST.usd
    assert result.cost.output_tokens == 200
    assert result.cost.cache_write_input_tokens == 1500


def test_price_uses_the_rate_card(monkeypatch):
    # A fake usage object standing in for anthropic.types.Usage.
    from types import SimpleNamespace

    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    cost = _core._price(usage)
    # Sonnet 5 rate card: $2 in + $10 out + $0.20 cache-read + $2.50 cache-write.
    assert cost.usd == pytest.approx(14.70)
    assert cost.input_tokens == 1_000_000
    assert cost.cache_write_input_tokens == 1_000_000


def test_price_tolerates_missing_cache_fields():
    from types import SimpleNamespace

    usage = SimpleNamespace(input_tokens=100, output_tokens=50)
    cost = _core._price(usage)
    assert cost.cache_read_input_tokens == 0
    assert cost.cache_write_input_tokens == 0
    assert cost.usd == pytest.approx(100 * 2e-6 + 50 * 10e-6)


def test_empty_cv_is_rejected(stub_llm):
    with pytest.raises(ValueError):
        run(Input(cv="   ", job_posting=JOB))


def test_empty_job_posting_is_rejected(stub_llm):
    with pytest.raises(ValueError):
        run(Input(cv=CV, job_posting="   "))

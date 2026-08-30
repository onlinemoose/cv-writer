"""Structural guards for the five prompt layers in cv_writer/prompts/.

These check the *mechanics* only — the files exist, load, and land in the
right part of the request. The semantic check (does each line belong in
its layer?) is the review protocol in docs/PROMPT-LAYERS.md, run by the
assistant on every change to a prompt file.
"""

from importlib import resources

import pytest

from cv_writer import Input, run
from cv_writer import _core

_PROMPTS = resources.files("cv_writer") / "prompts"
_IMMUTABLE = ("system.md", "standards.md", "output_contract.md")
_REPLACEABLE = ("style.md", "expert_guidance.md")
_LAYER_FILES = _IMMUTABLE + _REPLACEABLE


@pytest.mark.parametrize("name", _LAYER_FILES)
def test_every_layer_file_exists_and_has_content(name):
    text = (_PROMPTS / name).read_text(encoding="utf-8").strip()
    assert text, f"{name} is empty"
    assert text.startswith("#"), f"{name} should open with a Markdown heading"


def test_sentinel_placeholder_lives_only_in_the_output_contract():
    holders = [
        name
        for name in _LAYER_FILES
        if "{{SENTINEL}}" in (_PROMPTS / name).read_text(encoding="utf-8")
    ]
    assert holders == ["output_contract.md"], holders
    contract = (_PROMPTS / "output_contract.md").read_text(encoding="utf-8")
    assert contract.count("{{SENTINEL}}") == 1


def test_system_block_is_the_three_immutable_layers_with_the_sentinel_resolved():
    system = _core.SYSTEM_PROMPT
    assert "{{" not in system and "}}" not in system  # no unresolved placeholders
    assert _core.SENTINEL in system
    for name in _IMMUTABLE:
        head = (_PROMPTS / name).read_text(encoding="utf-8").strip().splitlines()[0]
        assert head in system, f"{name} heading missing from the system block"


def test_replaceable_layers_are_not_baked_into_the_cached_system_block():
    # style.md and expert_guidance.md are per-call (a caller can replace
    # either), so neither may be part of the immutable, cached system prompt.
    assert _core.DEFAULT_STYLE.strip() not in _core.SYSTEM_PROMPT
    assert _core.DEFAULT_EXPERT_GUIDANCE.strip() not in _core.SYSTEM_PROMPT


def test_default_style_and_method_reach_the_user_prompt_not_the_system_block(monkeypatch):
    seen = {}

    def fake_generate(system, prompt):
        seen["system"] = system
        seen["prompt"] = prompt
        return f"CV{_core.SENTINEL}note", _core.Cost(0.0, 0, 0, 0, 0)

    monkeypatch.setattr(_core, "_generate", fake_generate)
    run(Input(cv="Jane Doe\njane@example.com\n\nExperience: 5 years.", job_posting="A role."))
    for text in (_core.DEFAULT_STYLE.strip(), _core.DEFAULT_EXPERT_GUIDANCE.strip()):
        assert text in seen["prompt"]
        assert text not in seen["system"]

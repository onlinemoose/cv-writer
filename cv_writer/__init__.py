"""CV writer — one discrete piece of functionality.

Given a candidate's CV / career history and a specific job posting, write
a CV tailored to that role plus a short note on what it targeted.

Public surface: run(), Input, Output, Emphasis, Feedback, Cost, Progress.
Nothing else. See docs/CONTRACT.md for what this module promises.
"""

from __future__ import annotations

from collections.abc import Callable

from ._contract import Cost, Emphasis, Feedback, Input, Output, Progress
from ._core import _build

__all__ = ["run", "Input", "Output", "Emphasis", "Feedback", "Cost", "Progress"]


def run(
    data: Input, *, on_progress: Callable[[Progress], None] | None = None
) -> Output:
    """The one front door. Given an Input, return an Output.

    Does not read files, databases, or other modules — everything it
    needs is in `data`. The only outbound call is to the LLM used
    internally.

    `on_progress`, if given, is called with a `Progress` value about
    twice a second while the model streams the CV — for a caller that
    wants to show a live word count. It is a side channel, not part of
    `Input`, and has no effect on the Output; an exception from it is
    logged and swallowed.
    """
    return _build(data, on_progress=on_progress)

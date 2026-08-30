"""CV writer — one discrete piece of functionality.

Given a candidate's CV / career history and a specific job posting, write
a CV tailored to that role plus a short note on what it targeted.

Public surface: run(), Input, Output, Emphasis, Feedback, Cost. Nothing
else. See docs/CONTRACT.md for what this module promises.
"""

from ._contract import Cost, Emphasis, Feedback, Input, Output
from ._core import _build

__all__ = ["run", "Input", "Output", "Emphasis", "Feedback", "Cost"]


def run(data: Input) -> Output:
    """The one front door. Given an Input, return an Output.

    Does not read files, databases, or other modules — everything it
    needs is in `data`. The only outbound call is to the LLM used
    internally.
    """
    return _build(data)

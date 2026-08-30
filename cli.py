"""Tailor a CV to a job posting, from the candidate's current CV.

You must provide two things: the job posting and the candidate's current
CV or career history, each as a file path (or "-" to read from stdin).
Everything else is optional — extra background documents, tone, a target
length, a region, points to emphasise, or a previous draft to revise.

Inputs must be plain text or Markdown; convert PDF/DOCX to text first
(that is a separate concern — this tool only takes text).

Run with no flags to be asked for each field interactively.

The tailored CV is printed to stdout; the "what I targeted" note and a
one-line cost estimate go to stderr, so `> cv.md` saves just the CV.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:  # load ANTHROPIC_API_KEY from a local .env when running in isolation
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

from cv_writer import Emphasis, Feedback, Input, run


EXAMPLES = """\
examples
--------
  # try it now, on the bundled demo files
  uv run python cli.py \\
      --job-posting examples/job-posting.md \\
      --cv examples/cv.md \\
      --emphasis-file examples/emphasis.md \\
      --house-style examples/house-style.md

  # the two required inputs, your own files; CV saved to cv.md
  uv run python cli.py \\
      --job-posting ~/Documents/applications/acme.md \\
      --cv ~/Documents/cv.md > cv.md

  # paste the posting from the clipboard instead of a file (macOS)
  pbpaste | uv run python cli.py --job-posting - --cv ~/Documents/cv.md > cv.md

  # be asked for each field, one at a time (same as passing no flags)
  uv run python cli.py -i

  # with optional context: an extra background doc, tone, length, region, priorities
  uv run python cli.py \\
      --job-posting ~/Documents/applications/acme.md \\
      --cv ~/Documents/cv.md \\
      --background ~/Documents/portfolio-notes.md \\
      --tone conservative --target-length "2 pages" --region UK \\
      --emphasis "lead with the platform migration work" \\
      --emphasis-file ~/Documents/applications/acme-emphasis.md

  # revise an earlier draft — general feedback, and feedback tied to a quote
  uv run python cli.py \\
      --job-posting ~/Documents/applications/acme.md --cv ~/Documents/cv.md \\
      --previous-cv cv.md \\
      --feedback "make it shorter" \\
      --feedback-on "A highly motivated professional" "cut this, it says nothing"

notes
-----
  * --job-posting, --cv, --background and --previous-cv each take a file
    path, or "-" to read that field from stdin. The files are yours and
    live outside this repo; the module only ever receives their text.
  * --emphasis adds one quick point; --emphasis-file takes a bullet list,
    where a ">" line under a bullet anchors that point to a job-posting
    span:
        - lead with the platform migration work
          > own our payments and payouts services
        - foreground the team-leadership scope
  * --feedback is general ("make it shorter"); --feedback-on QUOTE COMMENT
    ties a comment to an exact span of the previous CV. Repeat either.
  * --target-length is free text ("1 page", "2 pages"). --region sets the
    CV conventions to follow ("UK", "US", ...); it defaults to UK and is
    not inferred from the posting.
  * --house-style and --expert-guidance are operator config, not the
    candidate's. --house-style is cross-cutting spelling / punctuation /
    phrasing rules (the same file you'd hand every text tool); it
    outranks the method. --expert-guidance is a file of method (section
    order, bullet style, how to handle gaps) that replaces the built-in
    guidance. Neither can override the grounding rules, the identity-block
    rule, the output format, or an explicit --tone / --target-length /
    --region.
  * Inputs must be plain text or Markdown. Convert PDF/DOCX to text first.
  * For a long posting or CV, use a file. Pasting a big block into a
    prompt is unreliable across terminals.
  * Needs ANTHROPIC_API_KEY. Put it in .env (copy .env.example).
"""


# Bundled demo inputs, offered as [d] at the interactive prompts.
_DEMO_DIR = Path(__file__).parent / "examples"
DEMO_JOB_POSTING = _DEMO_DIR / "job-posting.md"
DEMO_CV = _DEMO_DIR / "cv.md"
DEMO_EMPHASIS = _DEMO_DIR / "emphasis.md"
DEMO_HOUSE_STYLE = _DEMO_DIR / "house-style.md"


# --- interactive prompts ---------------------------------------------------
# All prompts and notes go to stderr, so stdout stays a clean CV even in
# interactive mode (`cli.py -i > cv.md` still works).


def _say(msg: str = "") -> None:
    print(msg, file=sys.stderr)


def _prompt(label: str) -> str:
    print(label, end="", file=sys.stderr, flush=True)
    return input()


def _ask(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    return _prompt(f"{label}{suffix}: ").strip() or (default or "")


def _ask_document(label: str, example: str, demo: Path | None = None) -> str:
    """A long text field. Give a file path (reliable for anything long),
    [d] for the bundled demo file, or leave it blank and paste the text
    ending with Ctrl-D."""
    demo_hint = ", [d] for the demo file" if demo else ""
    while True:
        raw = _prompt(
            f"{label}\n  file path (e.g. {example}){demo_hint}, or blank to paste: "
        ).strip()
        if demo and raw.lower() == "d":
            try:
                return demo.read_text()
            except OSError as exc:
                _say(f"  demo file unavailable: {exc}")
                continue
        if raw:
            try:
                return Path(raw).expanduser().read_text()
            except OSError as exc:
                _say(f"  can't read that: {exc}")
                continue
        _say("  paste the text, then Ctrl-D on a blank line to finish:")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            line = line.replace("\x1b[200~", "").replace("\x1b[201~", "")
            lines.append(line)
        text = "\n".join(lines).strip()
        if text:
            return text
        _say("  nothing captured — try a file path instead.")


def _ask_optional_file(label: str, demo: Path | None = None) -> str | None:
    """An optional file input: a path, [d] for the bundled demo, or blank
    to skip. Returns the file's text, or None."""
    demo_hint = ", [d] for the demo" if demo else ""
    raw = _ask(f"{label} — file path{demo_hint}, or blank to skip")
    if demo and raw.lower() == "d":
        try:
            return demo.read_text()
        except OSError as exc:
            _say(f"  demo file unavailable, skipping: {exc}")
            return None
    if raw:
        try:
            return Path(raw).expanduser().read_text()
        except OSError as exc:
            _say(f"  can't read that, skipping: {exc}")
    return None


_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _parse_emphasis_file(text: str) -> list[Emphasis]:
    """Bullet list -> Emphasis points. A line (optionally led by -, *, +,
    or "1.") is a point; a following line starting with ">" anchors it to
    a span of the job posting. Blank lines and "#" headings are skipped.

        - lead with the platform migration work
          > own our payments and payouts services
        - foreground the team-leadership scope
    """
    items: list[Emphasis] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(">"):
            quote = line.lstrip(">").strip()
            if items and quote:
                items[-1].quote = (
                    f"{items[-1].quote} {quote}".strip() if items[-1].quote else quote
                )
            continue
        point = _BULLET.sub("", raw).strip()
        if point:
            items.append(Emphasis(point=point))
    return items


def _ask_emphasis() -> list[Emphasis]:
    choice = _ask("Points to emphasise — [d] for the demo file, Enter to add by hand")
    if choice.lower() == "d":
        try:
            return _parse_emphasis_file(DEMO_EMPHASIS.read_text())
        except OSError as exc:
            _say(f"  demo file unavailable: {exc}")
    _say("Points to lead with or foreground, most important first.")
    _say("For each: the point, then optionally the job-posting line it answers.")
    items: list[Emphasis] = []
    while True:
        point = _prompt("  point (blank to finish): ").strip()
        if not point:
            return items
        quote = _prompt("  job-posting line it answers? (blank = general): ").strip()
        items.append(Emphasis(point=point, quote=quote or None))


def _ask_feedback() -> list[Feedback]:
    _say("Feedback on the draft. For each note: the comment, then the exact")
    _say("text from the CV it is about (leave blank for general feedback).")
    items: list[Feedback] = []
    while True:
        comment = _prompt("  comment (blank to finish): ").strip()
        if not comment:
            return items
        quote = _prompt("  quoting which text? (blank = general): ").strip()
        items.append(Feedback(comment=comment, quote=quote or None))


def _prompt_for_input() -> Input:
    _say("CV writer — interactive mode.\n")
    _say("Required: the job posting, and the candidate's current CV.")
    _say("Optional: extra background documents, tone, a target length, a")
    _say("          region, points to emphasise, a draft to revise.")
    _say("Press Enter to skip any optional field. [d] at a file prompt loads")
    _say("the bundled demo. Ctrl-C aborts.")
    _say("For the flag-based form and examples, run:  uv run python cli.py -h\n")

    job = _ask_document(
        "Job posting  (required) — the role being applied for",
        "~/Documents/applications/acme.md",
        demo=DEMO_JOB_POSTING,
    )
    while not job.strip():
        _say("The job posting is required.\n")
        job = _ask_document(
            "Job posting  (required)", "~/Documents/applications/acme.md", demo=DEMO_JOB_POSTING
        )

    _say("")
    cv = _ask_document(
        "Current CV  (required) — the candidate's CV or career history",
        "~/Documents/cv.md",
        demo=DEMO_CV,
    )
    while not cv.strip():
        _say("A CV is required.\n")
        cv = _ask_document("Current CV  (required)", "~/Documents/cv.md", demo=DEMO_CV)

    _say("")
    background: list[str] = []
    while _ask(
        "Add a background document (portfolio notes, project write-up, bio)? (y/N)", "N"
    ).lower() in ("y", "yes"):
        extra = _ask_document("Background document", "~/Documents/portfolio-notes.md")
        if extra.strip():
            background.append(extra)

    _say("\nOptional — press Enter to skip each.")
    role_title = _ask("Role title (only if the posting doesn't state it)") or None
    company = _ask("Hiring company (only if the posting doesn't state it)") or None
    tone = _ask('Tone for the CV, e.g. "conservative", "punchy", "academic"') or None
    target_length = _ask('Target length, e.g. "1 page", "2 pages"') or None
    region = _ask('Region conventions to follow, e.g. "UK", "US" (default: UK)') or None
    emphasis = _ask_emphasis()

    previous_cv: str | None = None
    feedback: list[Feedback] = []
    if _ask("Revise an earlier draft? (y/N)", "N").lower() in ("y", "yes"):
        previous_cv = _ask_document("The earlier draft", "cv.md") or None
        feedback = _ask_feedback()

    _say("\nOperator config (advanced) — press Enter to skip.")
    house_style = _ask_optional_file(
        "House style (spelling / punctuation / phrasing rules)", demo=DEMO_HOUSE_STYLE
    )
    expert_guidance = _ask_optional_file(
        "Expert guidance (replaces the built-in method)"
    )

    _say("\nWriting…\n")
    return Input(
        cv=cv,
        job_posting=job,
        background_documents=background,
        job_title=role_title,
        job_company=company,
        tone=tone,
        target_length=target_length,
        region=region,
        emphasis=emphasis,
        previous_draft=previous_cv,
        previous_feedback=feedback,
        house_style=house_style,
        expert_guidance=expert_guidance,
    )


# --- flag parsing --------------------------------------------------------


def _parse_args() -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description=__doc__,
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="ask for each field one step at a time (also the default when no flags are given)",
    )

    required = parser.add_argument_group("required inputs")
    required.add_argument(
        "--job-posting",
        type=argparse.FileType("r"),
        metavar="FILE",
        help='the role being applied for — a text/markdown file path, or "-" for stdin',
    )
    required.add_argument(
        "--cv",
        type=argparse.FileType("r"),
        metavar="FILE",
        help='the candidate\'s current CV — a text/markdown file path, or "-" for stdin',
    )

    optional = parser.add_argument_group("optional inputs")
    optional.add_argument(
        "--background",
        type=argparse.FileType("r"),
        action="append",
        metavar="FILE",
        help="extra context beyond the CV (portfolio notes, project write-up, "
        "bio, older roles); repeat for several",
    )
    optional.add_argument(
        "--tone", help='voice for the CV, e.g. "conservative", "punchy", "academic"'
    )
    optional.add_argument(
        "--target-length",
        metavar="TEXT",
        help='desired finished length, e.g. "1 page", "2 pages"',
    )
    optional.add_argument(
        "--region",
        metavar="TEXT",
        help='CV conventions to follow, e.g. "UK", "US" (default: UK, not inferred from the posting)',
    )
    optional.add_argument(
        "--emphasis",
        action="append",
        default=[],
        metavar="POINT",
        help="a quick point to lead with or foreground (no anchor); repeat, "
        "most important first",
    )
    optional.add_argument(
        "--emphasis-file",
        type=argparse.FileType("r"),
        metavar="FILE",
        help='a bullet list of emphasis points; a ">" line under a bullet '
        'anchors it to a job-posting span. File path, or "-" for stdin.',
    )
    optional.add_argument(
        "--company", help="hiring company, if the posting doesn't name it"
    )
    optional.add_argument(
        "--role-title", help="job title, if the posting doesn't name it"
    )
    optional.add_argument(
        "--previous-cv",
        type=argparse.FileType("r"),
        metavar="FILE",
        help="an earlier tailored CV to revise",
    )
    optional.add_argument(
        "--feedback",
        action="append",
        default=[],
        metavar="NOTE",
        help='general feedback on the previous CV, e.g. "make it shorter"; repeat',
    )
    optional.add_argument(
        "--feedback-on",
        action="append",
        nargs=2,
        default=[],
        metavar=("QUOTE", "COMMENT"),
        help="feedback tied to an exact span of the previous CV; repeat",
    )

    expert = parser.add_argument_group(
        "operator configuration", "supplied by whoever runs the module, not the candidate"
    )
    expert.add_argument(
        "--house-style",
        type=argparse.FileType("r"),
        metavar="FILE",
        help="cross-cutting spelling / punctuation / phrasing rules (the same "
        'file you would hand every text tool). File path, or "-" for stdin.',
    )
    expert.add_argument(
        "--expert-guidance",
        type=argparse.FileType("r"),
        metavar="FILE",
        help="a method for how to build the CV (section order, bullet style, "
        'how to handle gaps); replaces the built-in guidance. File path, or "-" for stdin.',
    )
    return parser.parse_args(), parser


def _input_from_flags(args: argparse.Namespace) -> Input:
    return Input(
        cv=args.cv.read(),
        job_posting=args.job_posting.read(),
        background_documents=[f.read() for f in args.background] if args.background else [],
        job_title=args.role_title,
        job_company=args.company,
        tone=args.tone,
        target_length=args.target_length,
        region=args.region,
        emphasis=(
            (_parse_emphasis_file(args.emphasis_file.read()) if args.emphasis_file else [])
            + [Emphasis(point=point) for point in args.emphasis]
        ),
        previous_draft=args.previous_cv.read() if args.previous_cv else None,
        previous_feedback=(
            [Feedback(comment=note) for note in args.feedback]
            + [Feedback(quote=quote, comment=comment) for quote, comment in args.feedback_on]
        ),
        house_style=args.house_style.read() if args.house_style else None,
        expert_guidance=args.expert_guidance.read() if args.expert_guidance else None,
    )


def main() -> None:
    args, parser = _parse_args()

    no_flags = args.job_posting is None and args.cv is None
    interactive = args.interactive or (no_flags and sys.stdin.isatty())

    if interactive:
        try:
            data = _prompt_for_input()
        except (KeyboardInterrupt, EOFError):
            sys.stderr.write("\naborted\n")
            raise SystemExit(1)
    else:
        if args.job_posting is None or args.cv is None:
            parser.error(
                "need --job-posting and --cv.\n"
                "  run `cli.py -i` to be prompted for each field, or\n"
                "  run `cli.py -h` for the full list and copy-paste examples."
            )
        data = _input_from_flags(args)

    output = run(data)

    if interactive:
        _say("--- tailored CV ---\n")
    sys.stdout.write(output.tailored_cv + "\n")
    if output.tailoring_note:
        _say(f"\n--- what I targeted ---\n{output.tailoring_note}")

    c = output.cost
    _say(
        f"\n--- cost ---\n"
        f"${c.usd:.4f} est. — {c.input_tokens} input, {c.output_tokens} output, "
        f"{c.cache_read_input_tokens} cache-read, {c.cache_write_input_tokens} cache-write tokens"
    )


if __name__ == "__main__":
    main()

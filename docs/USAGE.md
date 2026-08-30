# Running the CLI

`cli.py` runs this module on its own from a terminal. It builds a
`cv_writer.Input` and calls `run()` — nothing else. A consumer (an
orchestrator or the dashboard) does the same in code.

## Prerequisites

- `uv` installed (`uv --version`).
- An Anthropic API key in `.env`:

  ```
  cp .env.example .env      # then paste your key after ANTHROPIC_API_KEY=
  ```

## Try it now — the bundled demo

```
uv run python cli.py \
    --job-posting examples/job-posting.md \
    --cv examples/cv.md \
    --emphasis-file examples/emphasis.md \
    --house-style examples/house-style.md \
    --target-length "2 pages"
```

The CV prints to **stdout**; the "what I targeted" note and a one-line
cost estimate print to **stderr**, so redirecting keeps just the CV:

```
uv run python cli.py \
    --job-posting examples/job-posting.md \
    --cv examples/cv.md \
    --house-style examples/house-style.md > cv.md
```

## Interactive mode

```
uv run python cli.py -i
```

Asks for each field one at a time. At any file prompt, type `d` to load
the matching bundled demo file. Also runs automatically if you pass no
flags in a terminal.

## Your own application

```
uv run python cli.py \
    --job-posting ~/Documents/applications/acme.md \
    --cv ~/Documents/cv.md \
    --house-style examples/house-style.md \
    --emphasis-file ~/Documents/applications/acme-emphasis.md \
    --tone conservative --target-length "2 pages" --region UK \
    > cv.md
```

- Inputs are plain text or Markdown. Convert PDF/DOCX to text first.
- `--job-posting`, `--cv`, `--background`, `--previous-cv`,
  `--house-style`, `--expert-guidance` each take a file path, or `-` to
  read that field from stdin (`pbpaste | ... --job-posting -`).
- `--emphasis-file` is a bullet list; a `>` line under a bullet anchors
  that point to a job-posting span.
- `--region` is not inferred from the posting; it defaults to UK.

## Revising a draft

```
uv run python cli.py \
    --job-posting ~/Documents/applications/acme.md --cv ~/Documents/cv.md \
    --house-style examples/house-style.md \
    --previous-cv cv.md \
    --feedback "make it shorter, one page" \
    --feedback-on "a quoted line from the draft" "what to change about it" \
    > cv-v2.md
```

## Full flag list

```
uv run python cli.py -h
```

## After changing the code

```
uv run pytest
uv run lint-imports
```

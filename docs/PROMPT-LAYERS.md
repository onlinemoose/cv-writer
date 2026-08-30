# Prompt layers — scope and change protocol

The prompt text in `cv_writer/prompts/` is split into four files by **what
kind of statement** each one holds. Keeping them apart is what stops the
system prompt, the rules, and the method from bleeding into each other.

This document defines the split, and it is the protocol the assistant
runs whenever one of those files changes.

`_core.py` assembles the cached, immutable **system block** from
`system.md` + `standards.md` + `output_contract.md` (with `{{SENTINEL}}`
resolved). The **method** — `expert_guidance.md`, or a caller's
`Input.expert_guidance` that replaces it wholesale — is sent per call in
the user message and is never cached.

---

## The four layers

| File | Holds | Mood | Mutable by a caller? |
|---|---|---|---|
| `system.md` | Who the model is | *"You are… / you know… / you write for…"* | No |
| `standards.md` | What must be true of the output, + precedence | *"The result always / never…"* | No |
| `output_contract.md` | The exact reply shape | *"Return exactly…"* | No — code parses it |
| `expert_guidance.md` | How to produce a strong result this time | *"Do this, then that…"* | **Yes** — replaced wholesale |

### `system.md` — the worker, not the work

**Definition.** Role, expertise, mindset, and a plain orientation of what
the model is handed and what it returns.

**Discriminator.** Still true, word for word, if every standard were
rewritten and the whole method swapped? → it belongs here.

**Must not contain:** anything you could check the output against; a rule
(`must`, `never`, `always`); a numbered or sequenced step; anything that
only makes sense in service of one particular method.

**Example.** *"You know how a CV gets read: quickly, on the first page, by
someone checking it against a requirements list and looking for a reason
to stop. You write for that reader."*

### `standards.md` — invariants on the output

**Definition.** A standard is a property of the finished output that can
be checked true/false by inspecting the output and its inputs, without
knowing what method produced it. Breaking one makes the output *wrong*,
not merely weaker. A caller cannot loosen it. Each reads like a test
assertion. This file also holds the **precedence** map (conflicts
resolved by domain, not a single ranking).

**Discriminator.** Can you hold the finished CV next to it and say
yes/no? Is it true regardless of method? → it belongs here. If it is a
matter of degree or craft → it is method.

**Must not contain:** how to achieve the property; sequencing; anything a
caller might reasonably want to override; anything vague enough that two
readers would score it differently.

**Example.** *"Every employer-and-dates entry in the source work history
appears in the CV. The detail under a role may be cut; the entry itself
may not."*

### `output_contract.md` — the reply shape

**Definition.** The exact structure `_core.py` parses: the CV in
Markdown, the `{{SENTINEL}}` marker, the note in Markdown, nothing else,
plus the shape of the note. The marker string itself stays owned by
`_core.py`; this file carries the `{{SENTINEL}}` placeholder.

**Must not contain:** persona, method, craft, or rationale. Only the
shape.

### `expert_guidance.md` — the method

**Definition.** The recommended procedure, given the mindset and the
standards: sequence, document structure, technique, situational calls.

**Discriminator.** Could a competent expert reasonably do it another way?
Could a caller want to swap it for a specific campaign? → it belongs
here.

**Must not contain:** anything absolute or checkable — **point at a
standard, never restate it** (`"within the grounding rules, prefer the
figure the source gives"` ✅; `"never invent a figure"` ❌); any identity
claim (that is `system.md`).

**Example.** *"Default order: identity block, professional summary, key
skills, professional experience, education, then anything else. Move a
section up when this posting makes it decisive."*

---

## Precedence (lives in `standards.md`)

| Question | Decided by |
|---|---|
| Is it true / grounded? | Standards 1–6. Nothing overrides them. |
| Document structure — sections, order, entry contents | The method. The house style does not touch structure. |
| Spelling, punctuation, phrasing, date format, register | The house style if supplied, else the method's defaults. An explicit `tone` overrides both for register. |
| Length | Explicit `target_length`, else the `region` norm. |
| Region conventions | Explicit `region`, else the United Kingdom. |
| House style vs method reaching into structure | The method wins — it carries the author's domain expertise; the house style is mechanics. |

---

## Change protocol

Run this whenever a file in `cv_writer/prompts/` is added or edited —
whether the assistant made the change or a person did.

1. **Diff.** Get the exact added / changed / removed lines for each file
   (`git diff -- cv_writer/prompts/`). Work one file at a time.

2. **Mood check.** For every added or changed line, name its mood and
   confirm it matches the file it is in. Flag any line that trips a red
   flag below. Report it as **move** (name the correct file) or
   **rewrite** (give the reworded line that would fit).

   | File | A line here is wrong if it… |
   |---|---|
   | `system.md` | is a rule (`must`, `never`, `always`); is a numbered or ordered step; states a property you could check the output against; only makes sense alongside one specific method |
   | `standards.md` | tells you *how* or *in what order*; is vague or a matter of degree (two reviewers would score it differently); is something a caller could reasonably be allowed to override |
   | `output_contract.md` | describes persona, method, craft, or the reason for a rule; says anything beyond the shape of the reply |
   | `expert_guidance.md` | is absolute (`never` / `always` / `must` / `exactly`); restates a standard instead of pointing at it; makes an identity or capability claim about the model |

3. **Duplication.** Check the same instruction is not now expressed in
   two files (e.g. a grounding rule in both `standards.md` and
   `expert_guidance.md`). If it is, keep it in the higher layer and cut
   or convert the copy to a pointer.

4. **Precedence integrity.** If the change adds or alters a rule, confirm
   the precedence table in `standards.md` still resolves every conflict
   it could create. If a new conflict has no resolution, the change is
   not done — add the tie-break or reword the rule.

5. **Mechanics.** Run `uv run pytest`. `tests/test_prompt_layers.py` must
   pass (files load, the sentinel resolves and lives only in
   `output_contract.md`, the method stays out of the cached system
   block). Then `uv run lint-imports`.

6. **Verdict.** Summarise as a short list: for each finding, *keep* /
   *move to <file>* / *rewrite as "<line>"*, and whether the mechanics
   passed. Nothing is committed until every **move** and **rewrite** is
   resolved or the person has explicitly overruled it.

---

## Releasing a prompt change

Prompt text only, contract unchanged → **patch** bump. If the diff
changed `standards.md` or `output_contract.md` in a way that alters what
a caller can rely on, that is a **contract change** — update
`docs/CONTRACT.md` and bump **major**.

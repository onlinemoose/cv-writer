# Prompt layers — scope and change protocol

The prompt text in `cv_writer/prompts/` is split into five files by **what
kind of statement** each one holds. Keeping them apart is what stops the
system prompt, the rules, the style, and the method from bleeding into
each other.

This document defines the split, and it is the protocol the assistant
runs whenever one of those files changes.

`_core.py` assembles the cached, immutable **system block** from
`system.md` + `standards.md` + `output_contract.md` (with `{{SENTINEL}}`
resolved). The **style** (`style.md`, or a caller's `house_style`) and the
**method** (`expert_guidance.md`, or a caller's `expert_guidance`) are
each sent per call in the user message and are never cached; a caller
replaces either wholesale.

---

## The five layers

| File | Holds | Mood | Bundled default? | Caller replaces via |
|---|---|---|---|---|
| `system.md` | Who the model is | *"You are… / you know… / you write for…"* | — (immutable) | — |
| `standards.md` | What must be true of the output, + precedence | *"The result always / never…"* | — (immutable) | — |
| `output_contract.md` | The exact reply shape | *"Return exactly…"* | — (immutable) | — |
| `style.md` | How the prose reads | *"Write in… / prefer… / avoid…"* | yes | `Input.house_style` |
| `expert_guidance.md` | How the CV is built and how long it is | *"Do this, then that…"* | yes | `Input.expert_guidance` |

### `system.md` — the worker, not the work

**Definition.** Role, expertise, mindset, and a plain orientation of what
the model is handed and what it returns.

**Discriminator.** Still true, word for word, if every standard were
rewritten and the whole method and style swapped? → it belongs here.

**Must not contain:** anything you could check the output against; a rule
(`must`, `never`, `always`); a numbered or sequenced step; anything that
only makes sense in service of one particular method or style.

**Example.** *"You know how a CV gets read: quickly, on the first page, by
someone checking it against a requirements list and looking for a reason
to stop. You write for that reader."*

### `standards.md` — invariants on the output

**Definition.** A standard is a property of the finished output that can
be checked true/false by inspecting the output and its inputs, without
knowing what method or style produced it. Breaking one makes the output
*wrong*, not merely weaker. A caller cannot loosen it. Each reads like a
test assertion. This file also holds the **precedence** map.

**Discriminator.** Can you hold the finished CV next to it and say
yes/no? Is it true regardless of method and style? → it belongs here. If
it is a matter of degree or craft → it is method or style.

**Must not contain:** how to achieve the property; sequencing; anything a
caller might reasonably want to override; anything vague enough that two
readers would score it differently.

**Example.** *"Every employer-and-dates entry in the source work history
appears in the CV. The detail under a role may be cut; the entry itself
may not."*

### `output_contract.md` — the reply shape

**Definition.** The exact structure `_core.py` parses: the CV in
Markdown, the `{{SENTINEL}}` marker, the note in Markdown, nothing else,
plus the shape of the note. The marker string stays owned by `_core.py`;
this file carries the `{{SENTINEL}}` placeholder.

**Must not contain:** persona, method, style, craft, or rationale. Only
the shape.

### `style.md` — how the prose reads

**Definition.** Voice, register, spelling and language locale, date
format in prose, and words to avoid. **Cross-cutting** — the same rules
would apply to a cover letter, an email, or a company brief. Ships a
default; a caller replaces it wholesale with `Input.house_style`.

**Discriminator.** Would this rule apply identically to a cover letter
and a CV, and is it about *how the prose reads* rather than *what the
document contains or how long it is*? → it belongs here.

**Must not contain:** document structure or section order; how long the
CV is or how verbose (that is the method — a CV is concise whatever
register this file is written in); which evidence to select or weigh;
an identity claim about the model; a checkable invariant (that is a
standard); CV-format conventions such as page count or whether to
include a photo (that is `region`).

**Example.** *"Write in British English: organise, colour, recognise.
Prefer the active voice and name who acted. Avoid: leverage, utilise,
spearhead, passionate, driven, results-oriented."*

### `expert_guidance.md` — the method

**Definition.** How the CV is built and how long it is: section set and
order, evidence selection, achievement-bullet craft, gap handling,
length and verbosity. Ships a default; a caller replaces it wholesale
with `Input.expert_guidance`.

**Discriminator.** Could a competent expert reasonably do it another way?
Could a caller want to swap it for a specific campaign? Is it specific to
building *this artifact* (a CV) rather than prose in general? → it
belongs here.

**Must not contain:** anything absolute or checkable — **point at a
standard, never restate it** (`"within the grounding rules, prefer the
figure the source gives"` ✅; `"never invent a figure"` ❌); voice,
spelling, or word choice (that is the style); an identity claim (that is
`system.md`).

**Example.** *"Default order: identity block, professional summary, key
skills, professional experience, education, then anything else. Move a
section up when this posting makes it decisive."*

---

## Precedence (lives in `standards.md`)

Each layer owns a disjoint domain, so most conflicts do not arise.

| Question | Decided by |
|---|---|
| Is it true / grounded / correctly shaped? | The standards + the output format. Nothing overrides them. |
| Sections, order, entry contents, how long, how much detail | The method. The style has no say. |
| Voice, register, spelling, language locale, word choice | The style. The method has no say. An explicit `tone` beats the style for register. |
| CV-format conventions — page norm, photo / DOB / nationality, "CV" vs "résumé" | An explicit `region`, else the United Kingdom. Separate from the style's language locale. |
| Length target | An explicit `target_length`, else the `region` norm, applied by the method. |

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
   | `system.md` | is a rule (`must`, `never`, `always`); is a numbered or ordered step; states a property you could check the output against; only makes sense alongside one specific method or style |
   | `standards.md` | tells you *how* or *in what order*; is vague or a matter of degree (two reviewers would score it differently); is something a caller could reasonably be allowed to override |
   | `output_contract.md` | describes persona, method, style, craft, or the reason for a rule; says anything beyond the shape of the reply |
   | `style.md` | sets section order or document structure; sets length or verbosity; selects or weighs evidence; makes an identity claim; states a checkable invariant; sets a CV-format convention (page count, photo, DOB) that belongs to `region`; would not apply equally to a cover letter |
   | `expert_guidance.md` | is absolute (`never` / `always` / `must` / `exactly`); restates a standard instead of pointing at it; sets voice, spelling, or word choice (that is the style); makes an identity or capability claim about the model |

3. **Duplication.** Check the same instruction is not now expressed in
   two files (a grounding rule in both `standards.md` and
   `expert_guidance.md`; a voice rule in both `style.md` and
   `expert_guidance.md`). If it is, keep it in the layer that owns the
   domain and cut or convert the copy to a pointer.

4. **Precedence integrity.** If the change adds or alters a rule, confirm
   the precedence table in `standards.md` still resolves every conflict
   it could create, and that the new rule sits in the layer that owns
   its domain. If a new conflict has no resolution, the change is not
   done.

5. **Mechanics.** Run `uv run pytest`. `tests/test_prompt_layers.py` must
   pass (files load, the sentinel resolves and lives only in
   `output_contract.md`, the style and method stay out of the cached
   system block). Then `uv run lint-imports`.

6. **Verdict.** Summarise as a short list: for each finding, *keep* /
   *move to <file>* / *rewrite as "<line>"*, and whether the mechanics
   passed. Nothing is committed until every **move** and **rewrite** is
   resolved or the person has explicitly overruled it.

---

## Releasing a prompt change

Prompt text only, contract unchanged → **patch** bump. A change to
`standards.md` or `output_contract.md`, or a change to which layer owns a
domain, that alters what a caller can rely on → **contract change**:
update `docs/CONTRACT.md` and bump **minor** pre-1.0 (**major** after).

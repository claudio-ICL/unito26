# Delivering chapter 1: four classes, twelve hours

Teaching starts Monday 28 September 2026, two classes a week, three hours each. The first
four cover `chap.microstructure` in full. This file is the plan and the checklist for the
material that delivers it.

**The lecture notes are not changed.** Everything here is shaped around them. Where this file
and the `.tex` disagree, the `.tex` wins.

One notes section per class, and slides and a notebook in every class.

| | notes section | slides | notebooks |
| --- | --- | --- | --- |
| Class 1 | §1.1 `sec.orderDrivenMarkets` | 1h45 | `01-the-limit-order-book` 1h |
| Class 2 | §1.2 `sec.messageFiles` | 1h | `02-the-fold` 1h05 · `03-the-book-made-faster` 55m |
| Class 3 | §1.3 `sec.pointProcesses` | 1h15 | `04-simulating-self-excitation` 1h45 |
| Class 4 | §1.4 `sec.priceFormation`, §1.5 `sec.lobsterEmpirics` | 1h45 | `05-price-formation` 1h15 |

---

## The deck

One deck, `documentation/tex/slides/main.tex`, mirroring the book: one `\section` for the
chapter and one `\include` per section of the notes, under the notes' own name.

**A Welcome section now opens the deck**, under `\section{Welcome}` ahead of
`\section{Market microstructure}`: six frames, about ten minutes, in `the_course`,
`prerequisites`, `learning_python`, `examination`, `reading_list`. It mirrored
`notes/welcome/` one file per section until the caption pass of 25 September, which merged
`learning_finance` into the chapters table of `the_course` and `assignments` into the
arithmetic frame of `examination`, and deleted the two files. Before 25 September the first
slide of the course was "Two market infrastructures".

| file | class | frames | planned | written |
| --- | --- | --- | --- | --- |
| `sections/` × 5 (Welcome) | day one | 6 | 10m | ☑ 25 Sep |
| `sections/order_driven_markets.tex` | 1 | 22 | 95m | ☑ 22 Sep, revised 25 Sep |
| `sections/message_files.tex` | 2 | 16 | 58m | ☑ 25 Sep |
| `sections/point_processes.tex` | 3 | 18 | 76m | ☐ |
| `sections/price_formation.tex` | 4 | 20 | 90m | ☐ |
| `sections/lobster_empirics.tex` | 4 | 4 | 13m | ☐ |

**No assignment and no sample examination questions.** The closing exam-format frame is out
of all five files, and `lobster_empirics.tex` keeps the four frames that teach what the
generated setting lacks but not the one that sets the assignment.

`\include` rather than `\input`, so that the commented `\includeonly` line in the preamble
builds one class alone. Verified: the full deck is 121 pages and class 1 alone is 39, both
with a clean log. **The line must stay in the preamble** — `\includeonly` after
`\begin{document}` raises `Can be used only in preamble` and the errors that follow name the
wrong line. For the same reason the shared preamble files are `\input`: `\includeonly` would
otherwise exclude `notation.tex` and nothing would compile.

`sections/microstructure.tex` is the superseded deck. It is no longer included, and it is
deleted once the rewrite has been read.

### Six fixes to the class and formatting files, made and verified

The class promises in its own comment *"Same names as the notes, so that a statement can be
moved between the two"*, and did not keep it.

- **`assignment` was missing**, so `assignment.orderFlowImbalance` had nowhere to go. Added,
  with its own counter, as the notes class declares it.
- **`enumerate` was loaded where the notes class loads `enumitem`**, so every
  `\begin{enumerate}[label={\emph{\roman{*}}.}]` in the notes — in
  `assumption.idealisedBook`, `def.orderFlowProcess`, `thm.stationarity`, `thm.meyer1971`,
  `assignment.orderFlowImbalance` and four more — failed to compile on a slide. Swapped for
  `enumitem`, and a list copied verbatim from the notes now builds.
- **`lemma` needed no declaration**: beamer supplies it, as it supplies `example` and
  `corollary`. Declaring it raises `Command \lemma already defined`. The class comment named
  only two of the three and now names all three. `lemma.orderingOfOrders` therefore keeps its
  own name on a slide — on beamer's own counter, so the deck reads "Lemma 1, Definition 1".
- **The footline had zero height.** `slide_formatting.tex` built it inside
  `\begin{picture}(0,0)`, so beamer reserved no vertical space and painted the rule and the
  footer text *inside* the body. Measured: 18 lines clean, **19 and 20 silently printed over
  the footer with no `Overfull` at all**, 21 the first the log mentioned. A zero-width strut
  now gives the template the height the picture occupies — it shares the picture's baseline,
  so nothing drawn moved — and the band is gone: 18 clean, 19 reported. **The log is
  trustworthy again**, which is what matters when nobody else reads the deck.
- **The References frame printed across the footer** and the log said nothing.
  `allowframebreaks` breaks on `\textheight`; with the footline reserving space it now breaks
  clear. Verified by rendering the page.
- **the deck carried no version.** The notes date their title page with `This version:
  \compilationDate`; the deck said `Fall 2026` and nothing else, so two printouts could not be
  told apart. `\date[Fall 2026]{Fall 2026\\[1ex] This version: \compilationDate}` in
  `specs.tex` dates the title page and leaves the footline one line — the footline prints the
  *short* form, through `\insertshortdate`. `\compilationDate` is defined again in
  `unito26slides.cls`, as the two classes share no preamble.
- **`tikz` was loaded with no libraries.** `positioning`, `arrows.meta` and `calc` are all
  hard errors when used, and every schematic wants one. Added.
- **there was no way to build the lecturer's script.** `\documentclass[script]{unito26slides}`
  now sets `show notes`, so each frame is followed by a page carrying its `\note`: the slide
  and what is said over it are one source and cannot drift apart. Combine it with `handout`, or
  every `\pause` beat gets a page and the script repeats. natbib renews `\makeindex`
  unconditionally and beamer leaves it undefined once notes are typeset, so the class
  `\providecommand`s it before loading natbib — without that the script build alone fails.
- **`handout` was swallowed in silence.** `\LoadClass[10pt]{beamer}` forwarded no options, so
  `\documentclass[handout]` did nothing and each `\pause` beat stayed its own page.
  `\DeclareOption*{\PassOptionsToClass{\CurrentOption}{beamer}}` before it fixes that: the
  deck is 130 pages in presentation mode and **83 in handout**, which is the difference
  between rendering 130 images to review and 83.

### The frame contract

The first version of both microstructure decks reproduced the notes' paragraphs. Measured
against `~/Documents/thesis/viva/tex`, which is the style model, class 1 ran at 115 words a
frame and class 2 at 133, against the viva's 67 — and class 2 carried **one display across
sixteen frames**, with eight frames holding no object at all.

**The deck is projection material, not reference material.** Students do not read the slides;
they see them while the lecturer talks, and the reference material is the notes. So:

- **every frame carries one object** — a display, a statement of at most two lines, a TikZ
  picture, a `booktabs` table or an `algorithmic` block. No frame is prose alone;
- **at most three captions under it**. A caption is a *gloss* (`term: noun phrase`), a
  *fragment* of subject and predicate, or a *symbol* — a condition written as mathematics
  rather than said in words. It is never a sentence, and never a repetition of the frame
  title: what the title claims, the body does not claim again. Budget 12 words of prose a
  caption, 25 a frame, hard cap 40;
- **a statement states its head claim and stops.** Its consequence is spoken. Remark 9 reads
  `$\vwap_{t,w}$ is a statistic of the transactions.` and *cannot be recovered from the
  sequence of configurations alone* is in the `\note`. Definitions keep their mathematics
  whole: one that sheds a condition is a different definition;
- **no closing summary frame.** A slide that recites what the class just did is the spoken
  half written down; the forward signpost lives in the last frame's `\note`;
- **what is said over the object goes in `\note{}`**, not on the slide. Nothing is lost: it
  moves to where it is used;
- a statement environment keeps the notes' label only where it survives *as a statement*.
  Where the claim becomes a caption or a picture, the label goes with it, and the file header
  says which labels the file still owns.

Measured, in caption words a frame: the viva deck 67; class 1 115 before the first rewrite,
24 after it, **15** after the caption pass; class 2 133, then 21, then **16**; the Welcome
section 82 before the caption pass and **17** after. Zero frames over the cap, zero with a
caption over twelve words, zero with no object, across all forty-four.

The contract is checked, not remembered:

```bash
python3 .claude/skills/writing-in-tex/scripts/frame_density.py documentation/tex/slides/sections/<file>.tex
```

It prints every frame over the cap (`OVER`), every frame carrying a caption that reads as a
sentence (`LONG`), every frame whose statement says more than its head claim (`STMT`), and
every frame with no object (`BARE`), with the file's average. It counts `\note` separately
and never holds it against a frame, and it counts prose only: a symbol is not a word.
`STMT` is a list to justify rather than a list to forbid — three of the notes' statements
carry their hypotheses in words, and abridging them would change the claim.

Two recurring objects came out of the rewrite and belong in classes 3 and 4 too: the **chapter
roadmap**, four boxes with the current section highlighted, which opens and closes every class;
and **the schematic**, boxes and arrows in the vocabulary of the two-feed picture.

Conventions the deck inherits, and the two it does not:

- statements shared with the *notes* reuse the notes' labels, the two documents being
  compiled separately. **Within the deck a label is defined once across the five class
  files**, since they are `\include`d into one document — and a cross-file `\ref` prints
  `??` under `\includeonly`, the other files' `.aux` being absent. Every statement a later
  class needs from an earlier one is therefore **restated without a label**. Each file's
  header says which those are;
- a frame carrying `lstlisting` is `\begin{frame}[fragile]`, or the build aborts. Beamer
  then writes `main.vrb`, which is git-ignored;
- `algorithm` is a float and floats do not place inside a frame. `algo.ogata`,
  `algo.dassiosZhao` and `algo.bookFold` go on slides as bare `algorithmic`, with the caption
  in the `\frametitle` and no `\label`;
- every picture is TikZ, drawn inline. `documentation/tex/**/figures/` is git-ignored, so a
  deck depending on a generated image would not build from a fresh clone;
- **no measured number goes on a slide**, exactly as the notes require of the book. Timings,
  coefficients and goodness-of-fit numbers live in the notebooks;
- each deck closes on a frame in the examination's format — one snippet, and the question
  what it computes. Candidates are in `market-microstructure.md`.

### If a class overruns

The cut order lives in each file's header, so it is read where it is needed. In summary:

| class | cut first | then |
| --- | --- | --- |
| 1 | the elementary-stream reduction, recoverable in class 2 | the `Sto18mic` beat on the micro-price |
| 2 | the consolidated tape — Regulation NMS is background and plays no part in the assignment | the nomenclature frame, the vendor names surviving under the schematic; then hand the fold's termination argument to the notebook |
| 3 | the mean response, folding the relaxation time into the frame before it | the conditional survival function, asserted inline in the two algorithms |
| 4 | the total response, as a closing clause on the residual frame | a minute each from two frames; then hand the three weightings to the notebook |

**Class 3 has no headroom and `prop.forwardMean` may not be cut**, `prop.shortHorizonForecast`
in class 4 being built on it. Class 3 is already compressed to the judgment content: dropped
are `lemma.perronFrobenius`, the whole second-order block (`thm.lyapunov`,
`lemma.lyapunovUniqueness`, `eq.stationaryCovariance`), the scalar case, and sub- and
supercriticality. Perron–Frobenius survives as a subordinate clause in two places and gets no
statement.

### The 25 September review, and what it changed

Class 1 was declared done on 23 September on the strength of a clean build, a clean notebook
run and a green test suite. A review pass on 25 September found **eleven substantive defects
in the deck and one hollow section in the notebook**. Every gate measured whether the
artefacts compiled and ran; none measured whether they were true.

Four were false statements, now corrected: the residual described as resting *inside the old
spread* when it rests a tick *below the old best bid*; a matching trichotomy that contradicted
its own preceding line; $N_s$ said to be infinite when $q$ exceeds the *price-eligible* rather
than the *total* bid size; and "each unit at a price worse than the last", when units within a
level share a price. Two symbols were used and never defined — $\delta\bestAskPrice_t$ and the
$j \le 0$ convention — both needed by the deck's own worked example. Dropped hypotheses were
restored, nine register breaches cut, and the signpost to §1.4 added at both ends.

**Fourteen frames were retitled** to carry a claim rather than name a topic: "The cost of
taking liquidity" became *Every share pays the half-spread*, "One order, before and after"
became *The residual rests below the old best bid*. Five of twenty-three carried a claim
before; all twenty-three do now.

**Notebook `01` §7 demonstrated nothing.** `{1000: 20 + 20 + 20 + 20 + 20}` is `{1000: 100}`,
so the section on the chapter's central modelling decision compared a dictionary with itself.
It now folds two message streams — one submission of 100 against five of 20 — to the same
state, and adds the exhibit §1.1 most wants: the same book reached by execution and by
cancellation, 40 traded against 0, so that *volume is not a change in size* is shown rather
than asserted. The notebook also stopped hand-rolling what the package provides
(`SubmitResult.market_order_size`, `.walked_the_book`, `describe_message`,
`lobster.load_orderbook`, `frames.lobster_padding_row`), and now *computes* its two standing
claims instead of asserting them: the sentinel spread at level 10 prints as 19,999,999,998
file units, and the padding census reports 0 of 269,748 rows.

### Two errata, reported on 25 September and fixed the same day

Both are closed. They are recorded here because the second was in five files and only one of
them had been named.

- `notes/microstructure/sections/order_driven_markets.tex:529-530` stated the walking condition
  against the **spread**; it is the **half**-spread, and with the full spread only one direction
  survives. The same two lines read *"if an only if"*, *"larget"*, *"sprad"*. Rewritten as one
  edit, with the clause that makes the equivalence checkable from `eq.sweepCost`
  (commit `ad4053a`). **The only change ever made to the lecture notes**, and authorised as a
  typo fix.
- The residual of §8 Case B described as resting *inside the old spread* when it rests a tick
  *below the old best bid*. The phrase had been copied into four files —
  `documentation/order-driven-markets-notation.md`, `documentation/order-flow-to-order-book.md`,
  the `market-microstructure` skill's implementation notes and `unito26/lob/worked_examples.py`
  — and all four were fixed together (commit `ae86a8a`). Uses of the same phrase that are
  correct, in the micro-price discussion and in a different fixture, were left alone.

## The notebooks

`notebooks/lectures/`, numbered because students open them in teaching order and a notebook
carries no cross-references to break. Section structure follows what a class needs; the eight
notebooks in `notebooks/` are development artefacts and are ancestry, not a template.

`sec.learningPython` names four habits the course teaches alongside the stack, and each
notebook is built so that one of them is what the class practises:

| habit | notebook |
| --- | --- |
| invariants, round trips, and alternative routes that must reach the same value | `02` — our fold against the exchange's own |
| the property written as a test before the implementation | `04` — the compensator and the random time change |
| what defines an object is written with the object | `01` — the LOBSTER row round trip; `04` — a frozen parametrisation |
| the clear implementation first, then one shown to beat it | `03` — the whole notebook |

`05` practises the first at the level of a study: the contemporaneous identity is the route
that must agree, and the pre-registration is the property written down before the run.

Notebooks use LOBSTER wherever the notes use it. `data/` is git-ignored, so each states which
files it wants and fails readably when they are absent.

---

## The evenings

A class at a time, finished before the next is started. Four evenings buy roughly half of
what Sunday's plan promised, so the question is what to finish rather than what to hurry.

| | built | state at the end | done |
| --- | --- | --- | --- |
| Sun 20 | scaffolding: this file, the deck restructure, five frame skeletons, five notebook skeletons | | ☑ |
| Mon 21 | nothing — held for a review the author had no time to give | | ☒ |
| Tue 22 | class 1 deck, §1.1, 23 frames, three schematics | | ☑ |
| Wed 23 | notebook `01`, written and executed; the plotly template lifted into `visualization.py` | **class 1 teachable end to end** | ☑ |
| Thu 24 | nothing for class 2: the evening went to reviewing class 1 | | ☒ |
| Fri 25 | the class-1 review applied, both errata fixed, then class 2 in full: the deck at 16 frames and notebooks `02` and `03`, written and executed | **class 2 teachable end to end** | ☑ |

Classes 3 and 4 keep their skeletons and are built in the week of 28 September; they are
taught on 5 and 8 October. **The gate: nothing for class 2 begins until class 1 is teachable.**

### Artefacts

The "read by the lecturer" column that stood here is removed: the author has said they
cannot read anything before teaching, so a checklist gated on it could never close.

| artefact | scaffolded | written | builds / runs | inspected |
| --- | --- | --- | --- | --- |
| `slides/sections/order_driven_markets.tex` | ☑ | ☑ | ☑ | ☑ |
| `slides/sections/message_files.tex` | ☑ | ☑ | ☑ | ☑ |
| `slides/sections/point_processes.tex` | ☑ | ☐ | ☑ | ☐ |
| `slides/sections/price_formation.tex` | ☑ | ☐ | ☑ | ☐ |
| `slides/sections/lobster_empirics.tex` | ☑ | ☐ | ☑ | ☐ |
| `notebooks/lectures/01-the-limit-order-book.ipynb` | ☑ | ☑ | ☑ | ☑ |
| `notebooks/lectures/02-the-fold.ipynb` | ☑ | ☑ | ☑ | ☑ |
| `notebooks/lectures/03-the-book-made-faster.ipynb` | ☑ | ☑ | ☑ | ☑ |
| `notebooks/lectures/04-simulating-self-excitation.ipynb` | ☑ | ☐ | ☐ | ☐ |
| `notebooks/lectures/05-price-formation.ipynb` | ☑ | ☐ | ☐ | ☐ |
| `unito26slides.cls` and `slide_formatting.tex` | ☑ | ☑ | ☑ | ☑ |
| `config.TWO_TYPE_PARAMS` and its test | ☐ | ☐ | ☐ | ☐ |
| `visualization.use_template` | ☑ | ☑ | ☑ | ☑ |
| `sections/microstructure.tex` deleted | ☐ | | | |

`sections/microstructure.tex` stays until classes 3 and 4 are written: it is nineteen frames
of quarry material those two still draw on.

### How an evening runs

Read this file first, and tick it last. A deviation from the table above is reported at the
top of the reply, not buried in it — including a class that will not fit its budget, which is
the failure mode this plan is most exposed to.

---

### What class 2 does instead of the reconciliation the notes promise

§1.2 closes by saying that an implementation of the fold is compared against the exchange's
own, state by state. That comparison needs a map from a `LobsterEvent` to a `Message`, and the
package deliberately does not carry one: `market-microstructure.md` records L6 —
reconstructing the real LOBSTER book from its message file — as the aspiration the ladder
points at and as unbuilt on purpose. **Class 2 does not build it**, and therefore needs no new
code in `unito26/` at all.

What notebook `02` practises the habit on instead is the coarsening, which is built, tested and
measurable. The feed writes one row per resting order consumed and a session one row per order
that consumed them; the identity
$\sum_n e_n - e(\text{first},\text{last}) = S_{\text{end}} - \sum_i S_{j_i}$ says the order
flow contribution survives a queue split and cannot survive a level walk. On AMZN's whole day:
6,591 market orders, 1,511 of several fills, **297 that walked a level, and exactly 297 rows on
which the contribution differs**. A proof of where two routes must agree, and a measurement that
lands on it.

### Two things notebook `01` turned up

- **`to_lobster_row` and `from_lobster_row` do not take the same type.** The first returns a
  list in column order; the second wants a mapping keyed by column name. A file has names and
  a row of output has positions, and a `zip` over `lobster_book_columns` is where they meet.
  The round trip closes, but not by symmetry, and the notebook says so where it happens.
- **AMZN at depth 10 on 2012-06-21 has no padded row at all.** The padding demonstration
  therefore constructs one rather than finding one, and says as much. The format permits
  padding; whether a given file shows it is a property of the instrument and the day.

Notebook `01` also carries the first row of that file inline, so it runs whether or not the
sample data has been downloaded — the only class-1 artefact that needs `data/`.

## Verification

Run at the end of every evening.

The author cannot open the PDF, so a clean log is not the end of it. Two checks are
mechanical and one is mine:

```bash
# a frame that overflows is now reported, since the footline reserves its height
grep -c 'Overfull .vbox' documentation/tex/slides/main.log    # 0
grep -c 'Overfull .hbox' documentation/tex/slides/main.log    # 0

# render in handout mode -- one image per frame, not one per \pause beat
pdftoppm -r 110 -png documentation/tex/slides/main.pdf /tmp/frame
```

then measure how far body ink reaches down each page (a frame over about 90% is worth
looking at twice), and read the rendered frames. After the rewrite the deck's median frame
measures 63%, and the four deepest are the class 2 schematics at 83--89%.

```bash
# the notes must still build, unchanged
cd documentation/tex/notes && latexmk -C && latexmk -f -pdf -interaction=nonstopmode main.tex
grep -icE '^! |Undefined control sequence|LaTeX Warning: (Reference|Citation)|multiply defined' main.log
grep -c 'numberline {1}Market microstructure' main.toc          # 1
git diff --stat documentation/tex/notes/                        # empty

cd ../slides && latexmk -C && latexmk -f -pdf -interaction=nonstopmode main.tex
grep -icE '^! |Undefined control sequence|LaTeX Warning: (Reference|Citation)|multiply defined' main.log

# the package -- from INSIDE the env: a bare `python` is 3.9 here and every dataclass
# with slots=True fails to import, which reads as sixteen collection errors
conda activate unito26 && python -m pytest tests/
jupyter nbconvert --to notebook --execute --inplace notebooks/lectures/0*.ipynb
python3 .claude/skills/writing-in-tex/scripts/loose_paragraphs.py documentation/tex/slides

# the frame contract: 0 over the cap, 0 with no object, average well under 40
python3 .claude/skills/writing-in-tex/scripts/frame_density.py documentation/tex/slides/sections
# and the title page, read as an image: the version line on it, `Fall 2026' in the footline

# the lecturer's script builds from the same sources
sed 's/{unito26slides}/[handout,script]{unito26slides}/' documentation/tex/slides/main.tex \
  > documentation/tex/slides/script.tex
```

A `\nocite` key is checked against `documentation/tex/bibliography.bib` before it is written.
The 46 valid keys are the only ones that exist, and a wrong one fails inside bibtex rather
than at the point of use.

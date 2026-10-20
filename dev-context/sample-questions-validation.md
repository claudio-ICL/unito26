# Validating the sample questions and their worked solutions

October 2026. An account of every error found while the worked solutions of the sample questions
were written and validated: what was wrong, where it came from, and how it was fixed.

## What was done

Each of the eleven sections of `documentation/tex/questions` received a notebook of worked
solutions, `notebooks/sample-questions/NN-name-worked-solutions.ipynb`. It answers every question by
hand, cites the notes for every formula, and names the misreading behind each wrong choice. The
notebooks of sections 6 and 7 are copies of `worked_examples_for_final_lecture.ipynb`, used in class.

Every section went through the same cycle:

1. A writer drafted the notebook.
2. A mathematician re-derived every answer, read every cited statement in the notes source, and
   checked that each wrong choice is the outcome of a definite misreading.
3. An empirical developer ran every snippet, every intermediate value and every misread variant
   as code. It reran each timing several times, some of the runs under deliberate CPU load.
4. A fixer applied the findings. Every changed claim about code was confirmed by a run, and every
   changed citation was read in the source.
5. A reviewer re-examined every entry that had changed beyond its wording. Where the re-review
   found more, a second round followed.

The rule held throughout: a statement about what code prints, returns, raises or costs is true
only once a run has shown it. That covers the misread variant behind each wrong choice.

## In numbers

- **113 questions; no key was wrong.** Every key letter verified by the notebooks before stands.
- **29 questions changed in the `.tex`:** 19 in their choices, 8 in their stems, 7 in the
  explanation of the key (some in more than one).
- **The verification notebooks:** the boolean of every changed choice now evaluates the new
  text. Seven timing checks that load could break were rebuilt.
- **The class notebook, sections 6 and 7:** 12 corrections from the empirical review and 23 from
  the mathematical review and its re-review, none of them to an answer.
- **The drafts of the new notebooks:** some 110 errors of fact corrected before release, by the
  fixers' records. Most were misreadings described without being run, or citations credited with
  more than they state.
- **One fault in the package**, outside the questions; reported below and not fixed.

## Where the errors came from

The same few causes account for nearly everything.

1. **A wrong choice written from the outcomes, not from a misreading.** The README asks that "a
   distractor is the answer of a definite misreading". Eighteen choices broke that rule. Some were
   a permutation of the outputs that nothing can print. Others needed two unrelated mistakes at
   once. In two questions, 4.2 and 5.11, one mistake made two choices hold together. Every such
   choice was found by running the misread variant and seeing it print something else.
2. **A misreading described without being run.** The commonest error of the drafts and of the
   class notebook. The text names a plausible mistake, but the mistake, written as code, prints
   another choice or none.
3. **A citation credited with more than it states.** The statement is close to the claim but does
   not contain it; examples are 1.6, 5.4, 7.4, 8.6 and 10.11. Also: a remark cited where the
   paragraph after it is meant, and a proposition stated modulo 2^(n+1) cited for the integers.
4. **The common case stated as the rule.** For example: "each step starts just after an event"
   (the first starts from Z = 0); "what is left of a market order rests at its last fill" (unless
   it filled nothing); "`np.allclose` raises on arrays of different lengths" (not when one has
   length one); "the times are fixed by the column sums of A" (only when those are constant).
5. **A premise of the run left implicit.** In 6.8 the key holds only if an event falls in
   (10, 40]. In 7.7 and 7.8 a correlation near zero prints `+0.0` or `-0.0` by its sign, which no
   one can read by hand.
6. **A figure from one run quoted as typical.** For example "a growth of 12.2", "about 70", "about 5"
   and "8.3". A rerun gives another value. The figures are now quoted as ranges, measured over
   several runs.
7. **Timing checks tuned on a quiet machine.** Few repeats, consecutive blocks, the wall clock,
   and thresholds that leave a band where no choice holds. Under load a check could print "no
   choice holds" (3.7, 7.5, 5.11, 8.12) or come within a few per cent of failing (2.10, 10.12,
   11.7).
8. **Spurious precision.** In 7.3, "a mean of 250.75" adds 0.75 to a term that the fluctuation of
   N/T moves by more; the run prints 249.32. A related slip is an underflow shown as a value:
   `exp(-2000)` prints `0.0`.

## The questions document and the verification notebooks

Each fix below was confirmed by a run of the snippet, a run of the misread variant behind the new
choice, and a full execution of the verification notebook with every `verify` passing.

### Choices that no definite misreading produced

| question | the problem | the fix (the new choice, and the misreading behind it) |
| --- | --- | --- |
| 1.1 `signedStateToSides` (D) | "A raises; B prints `1001 1`": A passes only positive sizes; 864 combinations of misreadings found it only with three at once | "Both alternatives raise `ValueError`": A's `s < 0` read as `s <= 0` |
| 2.2 `precomputedMarketPartOnAWalkingSell` (D) | "B raises `TypeError`": B never meets an empty side here, and forced onto one it loops | B prints `[(1000, 100), (999, 200), (998, 50)]`, then `998 999 50`: B's test read without `d` |
| 2.5 `fillsPricedAtTheIncomingOrder` (C), (D) | the wrong price confined to the record; carried into the price test, it changes the walk | the market sell carrying 998, its last fill; and carrying `sys.maxsize`, the sentinel of a buy |
| 2.6 `priceTestWithoutTheDirection` (B) | needed two misreadings | "After (i), (ii) and (iii)": the market sell taken to pass any price test |
| 2.7 `splittingAMarketOrderLosesItsRemainder` (C) | three guards keep the empty resting part from writing; no single misreading passes them | "False, False, True": the two parts applied in reverse order |
| 3.9 `frameSweepCostZeroTimesNan` (B) | B's `1.0` impossible: its padded 0·NaN makes the row NaN | B `[1.25, nan, nan]`: `filled` disregarded |
| 4.2 `copyingFoldAgainstInPlaceFold` (D) | the misreadings of (A) and (C) made (D) hold too: a constant ratio forces equal growths | (D) adds "near the hundredfold growth of ℓ"; the bounds of (A) and (C) no longer overlap |
| 5.11 `cachedBestPriceWhenTheTouchEmpties` (A) | (B) implied (A): one misreading, a free repair of the cache, made both hold | "on S neither time grows, on E both about tenfold": `AggregateBook` credited with the cache |
| 5.12 `abstractMethodRaisesAtInstantiation` (D) | needed two errors at once | the JSON, then `TypeError` at the call of `_HawkesState`: the two forms of leaving a function to a subclass exchanged |
| 6.10 `transposedKernelChangesTheRate` (D) | "close to 3, then `ValueError`": a matrix and its transpose share every stability quantity | "close to 2, twice": λ̄ = μ̄/(1 − ρ) applied to both; the stem's sentence on `ValueError` removed |
| 7.9 `fillsSharingATimestamp` (C) | a wrong rate is not "as bad as the atom" | "0.5 on every line": `np.unique` read as sorting and keeping the repeats |
| 8.7 `clusterSizeByFounderAndItsTranspose` (E) | the rule behind it, a column sum above one taken for an infinite cluster, stops A as well as B | both loops not ending |
| 8.9 `selfAndCrossPairsRelaxAtDifferentRates` (C) | no rule gives 1.0 then 0.15 | `0.71`, then `0.15`: the relaxation time taken for the time constant of the fastest mode |
| 8.11 `statisticsThatTellSelfFromCross` (B) | "the Fano factor alone": no misreading makes only it differ | "the correlation alone": the mask `types[:-1] == 1` overlooked |
| 9.1 `restartTheStateAfterAMarketSell` (A), (D) | `decayed_counts_at` is linear in the initial state, so neither pattern can be printed | `F, F, T, T`: the event at the shifted time 0 not read; `False` on every line: events and clock left unshifted |
| 9.2 `millisecondClockKeepsTheState` (B) | its second line did not follow from its first | "True False, then False False" |
| 9.5 `forecastBetweenEventsFollowsTheFlow` (D) | `forecast_b ≥ forecast_a` on every path, so the two are never both unbiased | "`forecast_b` only": Z taken constant between events |
| 9.8 `forecastAWindowThatOpensLater` (C), (D) | the misreading of (C) yields (E); (D) compound | "`window_d` only": the horizon read as a time; "`window_b` only": the horizon read as the h-th second |

### Stems, and explanations of the key

- **11.6 `askWindowsOfTheTwoBitmaps`.**
  - "Shifted so that the lower end of the window is bit 0" had two readings for the asks of
    `TickArrayBook`, by bit and by price, and the key held under one only. It now reads "the lowest
    set bit of the window is bit 0", as the package's docstrings do.
  - The asks lay symmetrically about 103.5, so the misreading the explanation is about, the
    direction of count, still printed the key. The asks are now 101, 102, 104, 106, with five new
    choices. Origin: data chosen without running the misreadings.
- **6.8 `eventsHoldTheCrossingEvent`.** The key holds only if an event falls in (10, 40]. The stem
  now gives the pair's total baseline, 0.5, and bounds thirty quiet seconds below e^{-15}.
- **6.7 `selfAndCrossExcitingShareTheirTimes`.** "`np.allclose` raises when the lengths differ" is
  false for an array of length one. It now ends "neither being of length one".
- **7.6 `groundResidualsCannotSeeTheTypes`.** "About 1900 buys": the path has 1971, the
  expectation 2000. Now "about 2000".
- **7.7 and 7.8.** A correlation near zero prints `+0.0` or `-0.0` by seed; 53 seeds in 100
  printed `-0.0` on line 1 of 7.8. 7.8 now prints the absolute value; 7.7, where the sign of the
  other line decides, says so in the stem.
- **10.4 `blockExponentialOfOneMarketBuy`.** The stem cited eq. `forwardMeanCounts` for e^{Kh},
  which is in eq. `forwardMeanState`. It now cites both.
- **Explanations.**
  - 3.7: "the fixed cost weighs as much as the searches" holds at n = 1000 only (measured).
  - 10.10: "neither gives the same number" was asserted; the sign argument now proves it.
  - 11.1: the variant it named prints `77 352`, not the choice; it now names the one that does.
  - 11.4: it cited Proposition A.3.1, stated modulo 2^(n+1), for an identity on the integers,
    which Definition A.4.1 gives.

### Verification notebooks

- **Labels.** In 10.4, "no decay" labelled the variant that gives 1.375. Dropping the decay gives
  2.148; 1.375 is K taken for zero. In 8.12, the markdown gave the number of terms as
  log(2·10¹²) where the loop stops at log(5·10¹¹). In 2.8 the markdown said the loop "reads nothing
  but the book".
- **Timing checks.** Each was rebuilt in one or more of four ways, and tested quiet and under 6 to
  18 CPU burners:
  - more repeats, keeping the minimum;
  - the cases timed in turn over several rounds, rather than each in one block;
  - thresholds moved to the geometric midpoint of the growths the choices contrast;
  - `time.process_time` in place of the wall clock.

  | check | before | after |
  | --- | --- | --- |
  | 2.10 | failed 4 times in 14 under load | 7 interleaved rounds; held at 14 burners on 12 cores |
  | 3.7 | failed once (B ×8.6 against > 10) | 5 repeats, thresholds at 8; 3 of 3 under load |
  | 5.11 | no choice held under burners | 5 repeats, thresholds at 3 |
  | 7.5 | 0 of 3 under load | 5 interleaved rounds for all three; 6 of 6 |
  | 8.12 | first rung timed once on a cold core; failures at 4.8, 4.5, 3.1 | warm-up, 9 interleaved rounds, `process_time`; 22 of 22 up to 18 burners |
  | 10.12 | B's growth fell to 4.5 against > 4 | 7 rounds back to back, medians within rounds |
  | 11.7 | array growth 2.72 against < 2 | more reads, minimum of 9, thresholds 5 and 3 |

## The class notebook, `worked_examples_for_final_lecture.ipynb`

Sections 6 and 7 had been checked before class: their letters, numbers and citation numbers matched
the runs, and the content of every citation was read. No claim of the prose had been run as code.
Running them found the following, none of which changes an answer.

- **6.6.**
  - "After a quiet spell D is near 0 and the probability [of a defective clock] near 1" is false.
    Every wait is drawn just after an event, so D ≥ 25 at every step after the first, and the
    probability is at most e^{-1/2} ≈ 0.61. Logged over 20 000 steps: least D 25.0, largest
    probability 0.6065.
  - The first step, from Z = 0, has D = 0; the entry had left it out.
  - The misreading behind (C) is now `max` read as `min`, which prints 1.31.
- **6.1.**
  - "B's bound stays near μ̄": its time-averaged bound is 0.84.
  - (A) and (C) now name misreadings.
- **6.7:** "about 200 events": the path has 164.
- **6.8:**
  - The misreading behind (B) yields it only if the generator is put back with the clock and the
    state.
  - Only the second line needs an event in (10, 40].
- **6.5 (D):** an arithmetic slip, replaced by a misreading that prints the choice.
- **6.10:**
  - The column-sum shortcut applies to neither matrix.
  - The reading behind (A) would solve the transpose's baseline as (1.3, −1.6), not a baseline.
- **F3:** the count of a simulation from Z = 0 was credited to the definition of the relaxation
  time; it comes from eq. (1.3.33) and the ergodicity of Section 1.3.4.
- **7.2:**
  - D, a statistic, was written equal to the distance between two laws; the run prints 0.389
    against 0.385.
  - (C) and (E) now name misreadings that yield them.
- **7.3:** the spurious 250.75 (true value 249.32), the underflow cell, and a misreading for (C).
- **7.4 (E), 7.5 (A, C, E), 7.9 (B):** misreadings that did not yield their choice, replaced.
- **7.6:** "the mean residual is about 1": 0.943 on the path; and 1900 buys.
- **7.7:** "B fails the theorem": B, an antithetic stream, is not a Poisson flow; the theorem's
  hypothesis is absent.
- **7.8:**
  - "equal except in its first entry" holds only to rounding.
  - Why the joint independence fails is now said.
- **G2:** Remark 1.3.13 was credited with the overstatement of the post-jump reading. It states the
  continuity; the overstatement comes from the jump of N.
- **G4:** "a test of the margins sees no dependence"; the remark says "tests", and serial dependence
  does change the law of D.

The two copies of sections 6 and 7 are kept identical, cell for cell.

## The drafts of the new notebooks

Before release, some 110 errors of fact were corrected in the drafts of sections 1–5 and 8–11. The record,
entry by entry, closes this note.
By kind, the commonest first:

- **Misreadings that did not yield their choice when run.** For example:
  - 1.7 (C), a filter keeping all four rows, prints 5×10⁹ rather than the choice's 3.3×10⁹;
    `book.where` in place of boolean indexing prints exactly the choice;
  - 4.5 (D), the zero kept in the book but not in its copies, prints no choice;
  - 10.4 (B): β = 0 gives 2.148, while K = 0 gives the choice's 1.375;
  - 11.6 (A, B, E): with the old asks, the misreadings printed the key.
- **Citations credited with more than they state, or misplaced.** For example:
  - Remark 1.1.3 credited with a clause about the best bid;
  - Proposition 1.1.11 credited with the market-to-limit rule of Section 1.2.3;
  - "the paragraph after the definition" where the second paragraph was meant;
  - Corollary 1.4.21 deciding by θ, where it decides by θ(h);
  - eq. (1.1.8) giving a VWAP, where it gives a volume.
- **Statements beyond what the argument gives.** For example:
  - "fail to commute when one changes what the other finds", a necessary condition stated as
    sufficient;
  - "the ratio is (n+1)/2" where the argument gives proportionality;
  - an equality that holds up to A K^{-1} e^{100K};
  - limits stated without ρ < 1.
- **Facts of Python, NumPy or pandas left unmarked or misstated.** For example:
  - `0.2 / (1 - 1)` raises `ZeroDivisionError`; only NumPy's division gives `inf`;
  - NumPy pads printed arrays;
  - a generator's body runs at the first `next`.
- **Figures of one run quoted as typical.** Now ranges, from several runs.
- **Notation**: a symbol of the notes reused with another meaning (κ, the kernel, for
  an eigenvalue; B₀ for the opening book; m for a Palm mean).

## Found outside the questions

`unito26.lob.hawkes._mean_response_blocks` passes a stack of horizons to `scipy.linalg.expm` in one
call. On scipy 1.18.0 a stack that is not sorted comes back wrong, without any error: horizons
(10, 0.3) on a 2×2 generator differ from the one-at-a-time result by 0.63, and 45 of 500 random
unsorted stacks are wrong. Sorted stacks are exact. `forward_mean_counts(z, clock)` does not check
that the clock is sorted. No notebook uses an unsorted clock. Not fixed: it is a change to the
package, for a separate decision.

## For the next questions

- **Run each wrong choice.** Write the misreading as code and run it; it must print the choice
  exactly. If it needs two mistakes, or also satisfies another choice, rewrite the choice.
- **Check each new boolean against both runs.** It must be false on the real code and true on the
  misread variant.
- **Time with the load in mind.**
  - Take the minimum over several repeats, with the cases interleaved.
  - Use `process_time` where the wall clock is shared.
  - Put the threshold between the growths the choices contrast, with no band in which no choice
    holds.
  - Before committing, run the check under CPU burners.
- **Quote measured figures as ranges** over several runs, and only as illustration; the answer
  rests on the cost argument.
- **Cite a statement only for what it says**, after reading it in the source, and its number from
  the current `.aux`.

## The record, section by section

One line per error of fact: where, what was wrong, its origin, the fix, and the run that
confirms it. "The stem" is the questions document; "the draft" is the first version of the
worked notebook; "the verification notebook" is `NN-name.ipynb`.

### Section 1 · Representing the aggregate book

- 1.1 `signedStateToSides`, choice (D) of the stem, "A raises `ValueError`; B prints `1001 1`". No misreading yields it: A hands `from_levels` only positive sizes, and an empirical search over 864 combinations of misread primitives found it only with three changes at once. Origin: the stem, a distractor written as a symmetric permutation of the outcomes rather than from a misreading. Fix: (D) "Both alternatives raise `ValueError`.", boolean `a == "ValueError" and b == "ValueError"`, misreading A's `s < 0` as `s <= 0`. Confirmed: the misread variant raises `ValueError: level at 1001 must hold positive size`; `01-representing-the-book` passes all nine `verify`.
- 1.7 `paddingSentinelsInTheSpread`, cell 19, bullet (C). "takes the filter to keep every row … the mean would be near 5×10⁹" yields `4 5000000000.75`, no choice. Origin: the draft, a misreading described without being run. Fix: `book[mask]` read as `book.where(mask)`, which keeps four rows and blanks row 1 (a fact of pandas). Confirmed: that variant prints `4 3333333000.3333335`, exactly (C).
- 1.7, cell 18. The calculator cell showed `four / 4 = 5000000000.75`, a value of the rejected misreading. Fix: removed.
- 1.3 `microPriceTowardsTheThinSide`, cell 8, bullet (B). "the two weightings exchanged" needs one misreading per function. Origin: the draft. Fix: the single misreading, the sizes of the two sides exchanged. Confirmed: bids `{1000: 100}`, asks `{1002: 300}` print `1000.5 1001.5`.
- 1.6 `sizeIsNotVolume`, cell 14. Remark 1.1.3 (`remark.sizeVersusVolume`) was credited with "the best bid can move to a larger queue", which it does not state. Origin: the draft, a citation credited with more than it states. Fix: that clause stated as a fact of this stream. Confirmed: the run moves the best bid from 1000 (60) to 999 (190) on the last sell, which trades 70.
- 1.5 `recorderAliasesTheSide`, cell 13. F1 cited for `levels_map` returning the side itself; F1 says nothing of it. Origin: the draft, a citation credited with more than it states. Fix: Section B.6 (`sec.stateAndInvariants`), which states it.
- 1.4 `floatPricesSplitALevel`, cell 9. "converted from currency only at the boundary" attributed to Section 1.2.3, which says "converted to currency". Origin: the draft, a misquotation. Fix: the notes' wording, and "the conversion from currency" for `TickGrid.to_ticks`.
- F3, cell 1. "rests what is left at its own price" is false for a market order, whose sentinel is not a price of the grid. Origin: the draft, Algorithm 1.2.1 stated without the departure of the package. Fix: "what is left of it rests at the price of its last fill (Section 1.2.3)". Confirmed: a market buy of 80 against asks of 30 and 20 rests its 30 at 1003, the last fill.
- 1.9 `sizeAtOnADictAgainstAList`, cell 21. "the sentence before Table 1.4" located the cost of a dict write in the wrong sentence. Origin: the draft, a citation read loosely. Fix: cite Section 1.2.4 (`sec.fasterBook`), "of the four only `best_price` does work that grows with the book", `size_at` being this `get`. The timing figures (1.5 and 12.2, one run) are now hedged as about 1 and about 12. Confirmed: eight runs, five quiet and three under six CPU burners, give A 0.39–1.28 and B 11.1–14.1, with B/A 874–1236.
- (re-review) F3: "rests at the price of its last fill" assumed a fill; a market order matching nothing rests nowhere (run: book unchanged, `unfilled == 10`). Origin: the fix of the first round, stated from the common case. Fix: ", and nowhere if it matched nothing".
- (re-review) 1.5: F4 credited with the entries of `shared` being one dictionary; that is `append` storing its argument, a fact of Python. Origin: the first-round fix, a citation placed one step early. Fix: the fact of Python named, F4 cited for reading the change through `shared[0]`.
- (re-review) 1.9: "about 12" for the growth of B is one draw; nine runs under load gave 7.6–18.9. Origin: a measured value quoted as typical. Fix: "of the order of ten", and the figures said to vary.

### Section 2 · Updating the book

- 2.2 `precomputedMarketPartOnAWalkingSell`, choice (D) of the stem, "Alternative B raises `TypeError`". No reading yields it: on this book B stops after $q_M = 300$ of the 450 bid shares, and forced onto an empty side `size_at(-d, None)` is 0 and the loop never ends. Origin: the stem, a distractor written from a guess at what a missing `None` test does, not run. Fix: (D) "B prints `[(1000, 100), (999, 200), (998, 50)]`, then `998 999 50`", boolean to match; misreading B's test read without $d$. Confirmed: the misread B prints exactly that; the verification notebook passes.
- 2.2, cell 9, bullet (B). "B's loop taken to run on $q$" leaves `if q > q_m` resting 100 at 999 and prints `998 999 100`, not the choice. Origin: the draft, a misreading described without being run. Fix: $q_M$ taken to be $q$, which prints exactly `[(1000, 100), (999, 200), (998, 100)]`, `998 1002 120`.
- 2.5 `fillsPricedAtTheIncomingOrder`, choices (C) and (D) of the stem. A market sell carrying 999 or `sys.maxsize` also changes the walk (A prints `998 150 300 299800` and `999 50 250 249850`), so the choices needed the wrong price confined to the record. Origin: the stem, the misreading applied to one line of the code only. Fix: (C) the sell carrying 998, its last fill (the walk unchanged, variant `349550`); (D) the sell carrying `sys.maxsize` (A `999 50 250 249850`, variant `999 50 250 249750`). Confirmed by the two runs.
- 2.6 `priceTestWithoutTheDirection`, choice (B) of the stem, "After (i) and (iii)": no single change of the code yields it (five tried). Origin: the stem, a distractor needing two misreadings. Fix: "After (i), (ii) and (iii)", the market sell passing any price test. Confirmed: `[True, True, True, False]`.
- 2.6, cell 20, bullets (A) and (D). "The variant taken to fail on every sell" gives `[T, F, F, T]`, no choice; "A taken to sell the order at 1001 to the bid at 1000", as a rule, gives (E). Origin: the draft, outcomes described as misreadings. Fix: (A) the messages applied in turn to one book; (D) A's test read as `best * d > p`. Confirmed: `[T, F, F, F]` and `[T, T, F, T]`.
- 2.7 `splittingAMarketOrderLosesItsRemainder`, choice (C) of the stem, "True, False, False": three guards (`remaining > 0`, the resting price `None`, `set_size` removing a zero) keep the empty resting part from writing, and no single misreading passes all three. Origin: the stem. Fix: "False, False, True", the two parts applied in reverse order. Confirmed: `['False', 'False', 'True']`.
- 2.7, cell 23, bullet (A): an outcome, not a misreading. Fix: the resting part taken to inherit the last fill of the market part. Confirmed: `['True', 'True', 'True']`.
- 2.8, cell 26, bullet (B): "the loop taken to end once 1002 is exhausted, the 30 shares dropped" is two misreadings; the first alone rests the 30 at 1002 and prints `1002 0 0`. Origin: the draft. Fix: a walk over the sorted prices on to 1003, `best_price` returning 1002 at size 0. Confirmed: `1002 0 2` twice.
- 2.8, cell 26, bullet (C): `check_invariants` after each message raises before anything prints. Origin: the draft. Fix: at the start of each pass. Confirmed: `1002 0 2`, then `AssertionError`.
- 2.8, cell 24: "the loop reads nothing else": it also reads `direction` and `limit_price`. Fix: "nothing else the loop reads changes".
- 2.4, cell 13: "the two trade the same 250 shares at different prices": they trade at the same two prices, 1000 and 999, in different amounts. Origin: the draft. Fix: as stated.
- F1, cell 2: the spread written $P^a - P^b$; the definition is $|P^a - P^b|$. Fix: the definition, and why it equals $P^a - P^b$.
- F3, cell 2: Algorithm 1.2.1 called the decomposition; the notes make it $F$, whose submission branch the decomposition is. Fix: "The submission branch of".
- 2.10, cell 31: B's "time grows by a factor between 10 and 13" bounds the count of operations; measured growths fall below 10 (8.6–9.9). Fix: the count of operations bounded, the time about tenfold; the $O(\ell\log\ell)$ of `sorted` marked as Python's.
- 2.10, verification notebook, the timing check: failed 4 times in 14 under load, each case being timed in one consecutive block. Origin: a measurement tuned on a quiet machine. Fix: the six cases timed in turn, seven rounds, the fastest of each kept; thresholds unchanged. Confirmed: under 14 burners on 12 cores the old cell failed once in four (B ×23.1) and swung A ×91–187, the new one held four times in four (A ×96–99, B ×10.2–10.5).
- 2.11, cell 34: "the paragraph after Assumption 1.4.1" is the second paragraph after it. Fix: "the second paragraph".
- (re-review) 2.10: the O(1) of a read and a write uncited; a write is in Table 1.4, a read is a property of Python's dict. Fix: both named.
- (re-review) verification notebook, markdown before 2.8: "The loop of `submit` reads nothing but the book and `remaining`"; it also reads the direction and the limit, which do not change. Fix: "Nothing else the loop reads changes".

### Section 3 · Traded volume and VWAP

- 3.9 `frameSweepCostZeroTimesNan`, choice (B) of the stem: "B prints `[1.25, nan, 1.0]`" follows from no misreading; B's third row also adds 0·NaN at its padded levels. Origin: the stem, a distractor composed without running its misread variant. Fix: B's line `[1.25, nan, nan]`, the misreading `filled` disregarded and the row costed on the 120 shares it takes; boolean changed in `03-vwap`. Confirmed: misread variant prints A `[1.25, 1.25, 1.0]`, B `[1.25, nan, nan]`; `03-vwap` passes whole.
- 3.9, worked cell 32: the bullet claimed that misreading gave the whole of (B). Origin: the draft, misreading described for A and not run for B. Fix: bullet restated with the new choice. Confirmed by the same run.
- 3.10 `lobsterAggressorIsMinusDirection`, worked cell 35, (C): "reads `Direction` as the direction of the trade" changes no code, so no output; (A) "sign the trades alike" and (D) "agree, as (A) does" did not fix which output. Origin: the draft, misreadings of meaning not reduced to code and not run. Fix: (A) B negating `Direction` as A does; (C) `aggressor > 0` read as selecting the negative aggressors, in both; (D) A's minus sign overlooked. Confirmed: prints exactly each choice.
- 3.6 `vwapWindowAtATiedTimestamp`, worked cell 20: row 1's `1003` presented as VWAP_{t,w} of eq. (1.1.10) (F2); the definition reads the window on the times and gives 1000.75 there. Origin: the draft, the code's convention (each window ends at its own row) credited to the definition. Fix: rows 0, 2, 3 are VWAP_{t,w}, row 1 is not; (A) named as the definition's reading. Confirmed: hand computation, and the verification's variant for (A).
- 3.7 `rollingVwapByCumulativeSums`, verification notebook: the timing `verify` failed under load (B's growth 8.6 against `> 10`, no choice holding). Origin: the verification notebook, min over 3 repeats and thresholds 10/6 leaving a dead zone, tuned on a quiet machine. Fix: min over 5 repeats, 100 calls per timing of A, every threshold at 8, the geometric midpoint of the fourfold and sixteenfold the choices contrast. Confirmed:, quiet 5/5 old and new; under six burners old 1/3, new 3/3.
- 3.7, worked cell 24: "A is faster by orders of magnitude" stated as derived from a count of steps against a count of calls. Origin: the draft, a measured factor presented as an argument. Fix: both counts given (1.2×10⁶ interpreter steps, 4.8×10⁴ compiled comparisons), the factor attributed to the run. Confirmed: the run prints B over A ≈ 3100.
- (re-review) 3.9 (D): "takes A to multiply the 0 shares by the NaN price as B does": A does multiply them (`np.where` evaluates both arguments, the point of 3.8); the misreading is A summing every product unfiltered. Origin: the first-round fix, a misreading described by its effect. Fix: so worded; run gives `[1.25, nan, nan]` twice.
- (re-review) 3.6: eq. (1.1.8) credited with giving 1000.75, a VWAP; it gives the volume. Fix: the window of eq. (1.1.8), and VWAP_{2,1} = 1000.75.
- (re-review) 3.7, worked entry and key's explanation in vwap.tex: "at these sizes [the fixed cost] weighs as much as the searches": measured, only at n = 1000 (9 µs against 15 µs; 79 µs at 4000). Origin: the key, a cost comparison stated without measurement. Fix: "at n = 1000 it is of the order of the searches", in both.
- (re-review) F3: `_sweep_cost` said to walk the occupied levels; it walks what `AggregateBook.sweep_cost` hands it. Fix: so stated.

### Section 4 · The book as a fold

- 4.5 `recorderAlignedWithTheOrderbookFile`, cell 12, bullet (D). "takes the withdrawal to leave 1000 in the book at size 0" alone prints `[1000, 1000, 1000]`, `[1000, 1001, 1000]`, `[1001, 1000, None]`, not (D): the package's `copy` writes through `set_size` and drops the zero. Origin: the draft, a misreading described without being run. Fix: the zero kept "in the book and in its copies". Confirmed: a variant whose withdrawal keeps the zero and whose `copy` carries every key prints exactly (D), `[1000, 1000, 1000]`, `[1000, 1001, 1000]`, `[1001, 1000, 1000]`.
- 4.4 `messagesThatCommuteInTheFold`, cell 9, bullet (D). "the misreadings of (B) and of (C) together" named two unrelated errors. Origin: the draft, a compound distractor described without its single cause. Fix: one misreading, an order that meets the opposite side filling at its best price alone and the rest cancelled. Confirmed: that variant prints False for pairs i and iii and True for ii, exactly (D). The `.tex` is unchanged.
- 4.4, cell 7. "two messages fail to commute when one changes what the other finds at its prices" is false as stated: in pair i the sell finds 50 at 1001 only if the buy came first, and the pair commutes. Origin: the draft, a necessary condition stated as sufficient. Fix: "can fail to commute only when …; pair i shows that this is not enough". Confirmed by the run of the snippet (pair i `True`).
- 4.3 `recursiveFoldOverAStream`, cell 6, bullet (B). "frames … to stay on the stack for every message" read literally applies to the loop of `fold_b` too, which would then raise at both lengths, no choice. Origin: the draft, a misreading worded without its scope. Fix: the frames counted "at each level of the recursion". Confirmed: a recursion holding one or four extra frames a level raises at n = 500 and at n = 5000, the snippet prints `5000` then raises.
- 4.2 `copyingFoldAgainstInPlaceFold`, cell 3, bullet (D). "a slowdown of about 10 for `fold_a` and about 70 for `fold_b`" was one run; fifteen runs of the reviewer gave 6.0–9.6 and 35.6–77.8, eight of mine 7.2–11.3 and 58–67. Origin: the draft, figures of one run quoted as typical. Fix: "of the order of ten for `fold_a` and several times larger for `fold_b`".
- 4.2, bullet (C). "takes `transition` to do the work of each message twice" restated the choice. Origin: the draft. Fix: the copy taken to cost about one message whatever ℓ; it makes 2ℓ calls of `set_size`.
- 4.7 `spreadsRefoldedFromEmpty`, cell 14. "the ratio of the two times is about (n+1)/2" claimed equality where the argument gives proportionality (`run` and `spreads_b` do different work per message). Origin: the draft, an argument stated beyond what it proves. Fix: "grows as (n+1)/2, the ratio of the numbers of messages applied". Confirmed: runs print 97–133, 253–272, 458–546.
- F1, cell 1. `apply` returning `None` when `record` is `False` was credited to Section 1.2.3, which does not state it. Origin: the draft, a citation credited with more than it states. Fix: cited to `unito26.lob.orderbook.AggregateBook.apply`. Confirmed: `apply(..., record=False)` returns `None`.
- F2, cell 1. The withdrawal rule (at most the size resting; `strict=True` raises) carried no citation, though Section 1.2.3 states it. Fix: cited to the paragraph on `withdraw`. Confirmed: a strict book raises `ValueError`.
- 4.5, cell 10. $\mathcal B_0$ denoted the opening book, against F1, eq. (1.2.1) and 4.7, 4.9, where $\mathcal B_0 = \varnothing$. Origin: the draft, a symbol reused with another meaning. Fix: "the opening book", and $\mathcal B_1, \mathcal B_2, \mathcal B_3$ for the configurations after the messages.
- (second round) 4.2, choices (C) and (D) of the stem: the misreading of (C), the copy costing one more application of the message, makes the ratio about two at every ℓ and therefore the two growths equal, so (D) held with it; and the misreading of (A), the copy costing nothing, made (D) hold with (A). Origin: the stem, (D) stating a relation between growths that every constant ratio satisfies; and (A)'s bound of 2 overlapping (C)'s "about two". Fix: (D) now reads "…by about the same factor …, near the hundredfold growth of ℓ, …", its boolean `growth_in_place > 30 and growth_copying > 30 and 0.5 < growth_copying / growth_in_place < 2`; (A)'s bound 1.5, (C)'s band 1.5–2.5. Confirmed: four variants (the real code, the copy as an alias, the message applied twice, a scan whose every step is a method call), five runs quiet and three under six CPU burners: each yields its own choice alone every time (real B; alias A, ratios ≤ 1.15; twice C, 1.94–2.07; scan D, ratios ≥ 3.5, growths ≥ 48); the real growth of `fold_a` is 8.0–11.4, far below 30.
- (second round) 4.2 (D), worked bullet: "takes the scan of a side to dominate both folds" would also make the two times equal, (A). Fix: a step of the scan counted as a call of `set_size`, which is the scan variant above.
- (second round) 4.2: "above 30 at ℓ = 1000": one run under load printed 21.9. Fix: "above 20".
- (second round) 4.5: the books after the messages written B_1, B_2, B_3, against F1's B_0 = ∅ (under F1, B_1 = F(∅, m_1) has bids {1001: 50}). Fix: the symbols dropped, the books named by the message after which they are read.
- (second round) F2: `ValueError` and its condition credited to the paragraph on `withdraw`, which says only "raises instead". Fix: the condition stated, the exception cited to `AggregateBook.withdraw` (run: 30 at a level of 20 raises `ValueError: cannot withdraw 30 at price 1000: only 20 resting`); "every write goes through set_size" cited to Section 1.2.3, where it is stated.
- (re-review) 4.2: "a ratio of about 5 at ℓ = 10": eleven runs print 5.4–6.1. Fix: "between 5 and 6". "A withdrawal … writes one" and "2ℓ calls at every message": 43 of 532 withdrawals find an empty price and write nothing, and the book holds 2ℓ−3 to 2ℓ prices (instrumented run: 957 writes on 1000 messages; 19145 calls of the copies at ℓ = 10). Fix: "at most one", "about 2ℓ".

### Section 5 · Classes and inheritance

- 5.11 `cachedBestPriceWhenTheTouchEmpties`, choices (A) and (B) of the stem. (B) implied (A): the one misreading "the repair of the cache on E costs nothing" made both hold, so no definite misreading yielded (A) alone. Origin: the stem, two distractors written from one misreading, one a weaker form of the other. Fix: (A) "On S neither time per message changes noticeably with ℓ, and on E both grow about tenfold", from AggregateBook credited with the cache; its boolean on the four growths. Confirmed: four variants timed, the real code giving (D), a free repair (B), a rescan at every write (C), AggregateBook replaced by a cached book (A), each alone.
- 5.11, verification notebook, the timing. One `timeit(number=3)` per configuration: under six CPU burners no choice held in any of three runs; under ambient load the full notebook gave growths on E of 5.2 and 6.0 against the threshold 5. Origin: a single measurement, and thresholds tuned on a quiet machine with a dead zone between 2 and 5. Fix: the least of five repeats; the growth thresholds at 3, between the 1 and the 10 the choices contrast. Confirmed: three runs under burners and three at ambient load, all giving (D); the notebook run gives 8.8, 1.0, 8.6, 8.5.
- 5.12 `abstractMethodRaisesAtInstantiation`, choice (D) of the stem. "NotImplementedError at the call of to_json" needed two errors at once: the abstract declarations read as raising bodies, and `self.to_frame` in `to_records` read as the base function (`to_json` reaches only the override). Origin: the stem, a distractor no single misreading yields; the draft's bullet named the first error alone, and a run of it prints the JSON, which is (B). Fix: (D) "The first prints the table as JSON; the second raises TypeError at the call of _HawkesState, and prints nothing", the two forms of leaving a function to a subclass exchanged. Confirmed: real code gives (A) alone; the exchanged variant gives the new (D) alone.
- 5.1 `writesToABookAndAMessage`, cell 2, (D). "takes `spread` for a method" yields "(5) only" when run, since (2) then binds an attribute. Origin: the draft, a misreading described without being run. Fix: the property seen to refuse assignment and `book.spread()` taken to call its function. Confirmed: that variant gives (2) AttributeError, (3) prints 2, (5) unchanged: (2) and (5) only.
- 5.6 `rescansCountedThroughTheCache`, cell 13, (E). "one rescan per message" names no misreading. Origin: the draft. Fix: every change of the cached price counted, the two writes of `from_levels` that fill the empty cache among them. Confirmed: 2 changes in `from_levels`, 5 in all.
- 5.8 `copyOfABookWithAVenue`, cell 15, (B) and (C). "the same misreading, in B alone" is not a misreading, and "carry the attributes" gives (C) for a reader who reads `_empty_like` right. Origin: the draft. Fix: (B) the book duplicated without calling its class; (C) the call read right and the venue carried onto the clone. Confirmed: deep copy prints `XETRA 99` twice; venue carried gives A `TypeError`, B `XETRA 99`.
- 5.9 `buildingABookOfAGivenClass`, cell 18, (B). "the function of AggregateBook receiving cls" gives `['CachedBestBook', 'TypeError']` on line 2, not (B). Origin: the draft. Fix: `AggregateBook.for_prices` read as `cls.for_prices`, so that `build_b` is `build_c`. Confirmed: line 2 then prints `['CachedBestBook', 'TickArrayBook']`.
- 5.11, cell 22, (C). "the repair costs more than the scan it replaces; on S there is no repair" leaves CachedBestBook faster on S, so (C) fails under it. Origin: the draft. Fix: every write taken to repair the cache by a scan. Confirmed: that variant gives (C) alone, ratios 0.50 and 0.50.
- 5.11, cell 22, the timing figures. "growths of about 7" against runs of 5.2 to 9.7. Origin: one run quoted. Fix: "5 to 10".
- F1, cell 1. "raises nothing … unless … slots" omits the property and the frozen data class, against 5.1 (2) and (5). Origin: the draft, a rule stated without its exceptions. Fix: both exceptions named, with F2 and F3. The citation "the paragraph after the definition" is the second paragraph. Confirmed in `objects_references.tex`.
- F2, cell 1. Table B.2 credited with "computed at every reading", which the paragraph after it states. Origin: the draft, a citation credited with more than it states. Fix: the paragraph cited.
- F6, cell 1. "only while every write goes through `set_size`" claims the converse of Proposition B.6.2, a sufficient condition. "occupied and better than the cache" omits the empty cache, the case that sets it in `from_levels`. Origin: the draft. Fix: "while … by hypothesis iii", Listing B.10 for a write past it; "the cache is None or worse", as `_best_after` reads.
- 5.4, cell 9. "hypothesis iii fails for both subclasses": it fails on all three books (Section B.6: the bypass "leaves the first two invariants true, on a plain book and on a cached one, and breaks the third"). Origin: the draft. Fix: "on all three books", the plain book keeping no index.
- 5.12, cell 23. Remark B.8.1 credited with both forms; it states the second, Section B.8 the first. Origin: the draft. Fix: both cited.
- 5.10, cell 19. The read `size_at` before the write, which returns 0 outside the band, was missing, so the line that raises was unstated; the calculator's −1 was unquoted. Origin: the draft. Fix: stated, citing `unito26.lob.orderbook.TickArrayBook.size_at` (the notes do not state it). Confirmed: `size_at` gives 0 at 34 and 166 on both banded books, `set_size` raises `ValueError` at 34 on both and at 166 on `TickArrayBook`.
- Facts of Python unmarked (5.1 (3), 5.8, 5.9, 5.12): calling an integer, a parameter left without a value, the body of a generator. Fix: marked, and the call of a class stated once as F8 with Definition B.2.1 and Table B.1.
- (re-review) 5.10: the first-round fix said the notes do not state that a read outside the band returns zero, and cited the package; Section 1.2.4, the paragraph after Table 1.4, states it. Origin: a search of the notes that missed it. Fix: Section 1.2.4 cited; "writes it" (the 0 read) made "writes 0 + 10".
- (re-review) F6: hypothesis iii of Proposition B.6.2 credited alone with the invariant of the cache; the proposition needs i and ii too. Fix: all three named.
- (re-review) 5.12, verification notebook: the boolean of the new (D) did not test "at the call of `_HawkesState`". Fix: `created == "TypeError"` added; all 12 `verify` pass.

### Section 6 · Simulating a Hawkes process

- (empirical review) 6.6 `clippedExcitationClockAddsEvents`, cell 19. "after a quiet spell D is near 0 and the
- (empirical review) 6.6, same cell. "27.6/50 ≈ 0.553": 27.6/50 = 0.552; −log 10⁻¹² = 27.63. Fix: 27.63/50.
- (empirical review) 6.7, cell 22. "Over about 200 events": the seed-3 paths have 164. Fix: "Over 100 s, some 200
- (empirical review) 6.8 (B), cell 23. The misreading "as though the clock and the state had not moved" gives
- (empirical review) 06 copy only: `pi` imported and unused.
- 6.10 (D), the stem. "A number close to 3, then `ValueError`": no definite misreading yields it, since Γ and Γᵀ share their spectral radius and every stability quantity. Origin: the stem, a distractor kept from an earlier draft whose ValueError the package never raises here. Fix: (D) "A number close to 2, twice", the shortcut λ̄ = μ̄/(1−ρ) applied to both; the stem's sentence on `ValueError` dropped; the key explains why the shortcut holds for the transpose only. Confirmed: the snippet prints 2.98, 2.01 (only B holds); the variant μ̄/(1−ρ) prints 2.0, 2.0 (only the new D holds).
- 6.8, the stem. The key "False 1" needs an event in (10, 40], which the stem did not give the means to assume. Origin: the stem, a premise of the run left implicit. Fix: the stem states the total baseline 0.5 and the bound e^{-15}; the entry says both lines need such an event. Confirmed: seed 11 has 28 events there; the bound is e^{-30·0.5} by eq. (1.3.40).
- 6.7, the stem. "np.allclose raises ValueError when x and y differ in length" is false when one has length one (broadcasting). Origin: the stem, a library fact stated without its exception. Fix: "neither being of length one". Confirmed by runs.
- 6.6, cell 19. "Each step starts just after an event … D ≥ 25" ignored the first step, from Z = 0, where D = 0 and τ₂ = +∞ in both classes. Origin: the draft, as corrected in the first round. Fix: "every step after the first", and the first step stated. Confirmed: the logged run, D = 0 at the first step only.
- 6.6 (C), cell 21. "the clip only shortens waits" named no misreading. Fix: `max` read as `min`. Confirmed: that variant prints 1.31 against 1.98 and 4.61.
- 6.5 (D), cell 18. An arithmetic slip, not a misreading. Fix: the threshold taken as the uniform 0.75 without `cumulative[-1]`. Confirmed: the variant prints `0 [1.75, 0.5]`, `0 [1.25, 0.5]`.
- 6.1, cell 5. "B's bound stays near μ̄": its time-averaged bound is 0.84 against μ̄ = 0.5. Fix: "far below λ_g(T_n+)" (mean 5.32 at the acceptances). (A) and (C) now name misreadings (the first step of Algorithm 1.3.1 for B's update; a lower bound read as a higher acceptance, the candidates' rate forgotten). Confirmed by a logged run of B on seed 8.
- 6.7 (D), cell 22: now a misreading (the self-exciting pair taken for the one with more events).
- 6.10, cell 29. F3's shortcut said not to apply "to the first matrix"; it applies to neither (Γᵀ's column sums are 1.5 and 0.3); "some 25 standard errors" is "more than 25"; Remark 1.3.7 credited with the fixed-μ sentence it does not contain. Fixes as stated. Confirmed: column sums and Γᵀμ = 0.6μ by a run.
- F3, cell 2. The count of a simulation from Z = 0 credited to Definition 1.3.36, which gives only the time constant. Fix: the mean deficit from eq. (1.3.33) at z = 0 and the ergodicity sentence of Section 1.3.4; Corollary 1.3.25 completed by eq. (1.3.22).
- 6.4, 6.9, 6.3: package and numeric facts without a source (from_state's clock, μ̄ = 1.8, e^{-18}), now cited; 6.3 argues "faster at every n" at n = 1000.
- (re-review) 6.8: "Both lines need an event in (10, 40]": only the second does; without one, `Dropping` drops an event past 40 s that the single run lacks too, and prints `True 0` (run: stretch to 11.20 s, both print `True 0`). Fix: so stated.
- (re-review) 6.10 (A): "holds when μ is solved from a target λ*": for this kernel the solved baseline of the transpose is (I − Γᵀ)λ* = (1.3, −1.6), not a baseline (run). Origin: Remark 1.3.7 generalised without its condition that the solved μ be non-negative (which the remark itself leaves unstated). Fix: the misreading named, and the negative baseline given.

### Section 7 · Necessary conditions and goodness of fit

- (empirical review) 7.2, reference 4 (and 3): D, the sample statistic, written equal to the distance between the
- (empirical review) 7.3: "a mean of about 250 + 0.75 = 250.75" and "0.25075": spurious precision; the mean is
- (empirical review) 7.4 (E): "takes the overstatement to accumulate" yields (D)'s output when run; (E) needs also
- (empirical review) 7.5 (C): the misreading explained only C's growth; the choice also has B doubling. Fix: "exchanges
- (empirical review) 7.6: "the mean residual is about 1": 0.943 on the path (N₁/N₀ = 0.915). Fix: "near 1, and the
- (empirical review) 7.8: "equals … except in its first entry": equal only to rounding (8 entries differ by
- (empirical review) G2 and 7.4: Remark 1.3.13 (`remark.readPreJump`) credited with the overstatement of the
- 7.9 `fillsSharingATimestamp`, choice (C) of the document, "0.5, 0.5, and a number close to 0". No definite misreading yields it (a wrong rate is not "as bad as the atom"). Origin: the stem, a distractor built from the outcomes rather than from a misreading. Fix: (C) "0.5 on every line.", boolean `reads(0.5, 0.5, 0.5)`; misreading `np.unique` read as sorting and keeping the repeats. Confirmed: `np.sort` in its place prints 0.5, 0.5, 0.5 and only the new (C) holds; the real run prints 0.5, 0.252, 0.018, only (A).
- 7.8 `tradesReportedOnBothSides`, the snippet. Line 1 prints `0.0` or `-0.0` by the sign of a correlation near 0, which cannot be read by hand; every choice writes `0.0`. Origin: the stem, the sign of a rounded zero overlooked (seed 14 happens to give `+`). Fix: `round(abs(np.corrcoef(...)[0, 1]), 1)` in the .tex and the verification notebook; choices and booleans unchanged. Confirmed: 53 of 100 seeds print `-0.0` before, none after; seed 14 prints the key unchanged.
- 7.7 `antitheticWaitsPassTheMargin`, the stem. The same signed zero on line A, where `abs` is not possible (B's sign decides the choice). Fix: the stem says that a correlation rounding to zero prints `+0.0` or `-0.0`, and that A's is positive on this seed (r = +0.0109).
- 7.5 `compensatorByRecursionSumOrQuadrature`, the verification notebook. The timing failed once under load (B ×2.81 against "more than threefold"), B timed twice and C once, in consecutive blocks. Origin: a timing tuned on a quiet machine with too few repeats. Fix: the three implementations timed in five interleaved rounds over the ladder, the least time of each kept; thresholds unchanged. Confirmed: old method 5/5 pass quiet (B 3.58-3.88) but 0/3 under six burners plus the other agents' load (B 3.24-6.11, C 2.52-3.92); interleaved with 3 rounds for C, 2/3 under load (C 2.91 once); with 5 rounds for all, 6/6 at load averages 6-9 (B 3.54-3.64, C 1.98-2.00); the notebook runs whole in 96 s, every verify passing.
- G2: "hence the post-jump reading … overstates" drew the overstatement from the continuity of Remark 1.3.13; it comes from the jump of N with Z left-continuous. Origin: the first-round fix, a logical link added with the citation. Fix: two sentences, the remark cited for the continuity alone.
- G4: "a comparison of each margin sees neither … independence"; Remark 1.3.46 says "tests", and serial dependence does change the law of D (7.7, 7.10). Fix: "tests".
- 7.7: "4000 residuals of a Poisson flow … (B)" and "B … fails the theorem": B is not a Poisson flow, its second wait being a function of the first; the theorem does not fail, its hypothesis is absent. Origin: the draft for class. Fix: the waits and their residuals under 2t; "B passes … and is not a Poisson flow".
- 7.2 (C) and (E): the misreadings named did not yield them (the first also passes reference 3; the second gives no reason to reject reference 0). Origin: the draft, misreadings described without being run. Fix: `stats.expon()` taken to fit the sample's scale, `[0, 2, 4]`; every comparison read against Exp(1), `[2]`. Confirmed by runs.
- 7.3 (C): "rescales μ and A and leaves β per second" described line 4 rather than a miscomputation. Fix: Γ taken unchanged in line 4. Confirmed by hand: 0.25 + 0.75 = 1.
- 7.4 (E): two misreadings together; one suffices, `np.diff` read as a cumulative sum. Confirmed: prints `[] []`, then `[0, 1, 2] [0.7, 1.4, 2.1]`.
- 7.5 (A), (E): corrections without misreadings. Fix: `quad_vec` taken to cost a compiled loop; B's vectorised sum taken for a constant and A's update for the sum of eq. (1.3.11). 7.5 B: "a doubling multiplies the time by more than 3" holds past bn > 2a only; the threshold now stated.
- 7.6 (A): "depends on the rows of A, not only on its column sums": the rows also sum to 3. Fix: the entries of row 0, which the kernels exchange.
- 7.7 (A): "misses the antithetic pairing" named no reading. Fix: `ravel` read in column order. Confirmed: prints `True +0.0` on both lines.
- 7.8 line 3: why the joint independence fails was not said. Fix: on the joint history a buy announces the sell 1 ms later, the sells' compensator jumps, hypothesis ii fails.
- 7.9 (B): two misses; one suffices, the executions taken for a Poisson flow of rate 2. Confirmed: 0.011 on every line.
- G1: d Λ = λ dt uncited. Fix: the paragraph after eq. (1.3.5).
- 7.2, 7.6: "the run prints" for numbers the verification notebook prints, not the snippet. Fix: "the verification notebook prints".

### Section 8 · Telling specifications apart

- 8.7 (E), the stem. "A prints numbers near 4.4 and 2.5; the loop of B does not end": the misreading behind it, a column sum above one taken for an infinite cluster, would stop A too (a buy has 1.2 direct offspring under Γ). Origin: the stem, a distractor built from one alternative's misreading without applying it to the other. Fix: (E) both loops not ending, its boolean `not ended`, the explanation naming both column sums. Confirmed: every cluster dies out (A 18/19 generations, B 7/24); verification passes.
- 8.11 (B), the stem. "The Fano factor alone" follows from no definite misreading (the Fano factor is a statistic of the times, and no reading makes it alone differ). Origin: the stem. Fix: (B) "The correlation alone.", from the mask `types[:-1] == 1` overlooked; boolean `differ([2])`. Confirmed by a patched verification run: only (B) holds under the misreading; the reviewer's alternative (types drawn with λ*/λ̄) was run and yields (A).
- 8.12, the verification notebook. The timing check came within 20% of its bound (first growth 5.2-6.0 quiet; failures reported at 4.84, 4.5, 3.1): the first rung was timed once, on a cold core. Origin: a measurement of five calls taken once, in ladder order. Fix: warm-up, nine interleaved rounds, minimum per rung. Confirmed: first growth 10.3-10.5 in eight runs, quiet and under six CPU burners. Its markdown gave the number of terms as log(2e12)/(1-ρ); the loop stops at 0.5ρ^k ≤ 1e-12, log(5e11). Fixed.
- 8.12, cell 37 of the draft. "a growth of 5.8 and then 9.9: at 256 terms the fixed cost of the call still weighs": the 5.8 was a disturbed measurement, the empty call costing 0.3% of the 256-term one. Origin: the draft, a measured figure explained without a run. Fix: growth about 10 at each rung, as the number of terms. Confirmed: 10.3 and 10.1 in the verification run.
- 8.2 (D), cell 9. "the floating-point division 0.2/(1 - 1), which gives inf": in Python it raises ZeroDivisionError; only NumPy's division gives [inf inf]. Origin: the draft, a behaviour stated without a run. Fix: NumPy's division of μ. Confirmed by a run.
- 8.11 (A), cell 36. "they [μ, λ*, ρ] fix the law of the times": false in general; the times are fixed by μ̄, β and 1ᵀA. Origin: the draft. Fix: stated so.
- 8.11 (B) of the draft. "the Fano factor taken to see the kernel beyond its column sums" did not yield "the Fano factor alone" (it would not make the correlation and the share agree). Origin: the stem (see above) and the draft.
- 8.10 (D), cell 33. "the Fano factor taken to depend on the total rate alone" yields two equal values, not values near 1. Origin: the draft. Fix: the counts taken for Poisson counts of the total rate.
- 8.7 (E) of the draft. "the column sum 1.6 of Γᵀ taken for its spectral radius" applied consistently stops A. Origin: the stem (see above).
- 8.4, cell 13. "This is the example of Remark 1.3.20": the remark's example is Γ = diag(2, 0), μ = (0, 1). Origin: the draft, a citation credited with more than it states. Fix: "As in the example of".
- 8.6, cell 19. The coincidence of ρ and the endogenous fraction credited to Corollary 1.3.25; it is in the paragraph after it. Origin: the draft. Fix: cite the paragraph and F4.
- F1, F3, F4, F5 (cell 2). Proposition 1.3.8 cited without its hypothesis ρ < 1; ergodicity used (shares along one path) without citation; Proposition 1.3.23 states the cluster of an immigrant, the draft said "an event"; F5 did not name the hypotheses its argument uses. Origin: the draft. Fix: each stated with its citation (Proposition 1.3.8, the paragraph before eq. (1.3.37), Proposition 1.3.23 and its proof, Theorem 1.3.29), read in the source.
- 8.9, 8.4, 8.8: printed NumPy arrays quoted with one space (`[1. 1.4]`) where NumPy prints `[1.  1.4]`. Origin: the draft copied the choices. Fix: quoted as printed, with a sentence in cell 0. Confirmed by printing each array.
- 8.9 (C), the `.tex`: "`[1. 1.4] 1.0`, then `[1. 6.6] 0.15`" had no rule behind it: the misreading named (the relaxation time read off the mode the swap moves) gives 0.71 on the first line, not 1.0. Origin: the stem, a distractor that changed one line only. Fix: (C) "`[1. 1.4] 0.71`, then `[1. 6.6] 0.15`", the relaxation time taken for the time constant of the fastest mode; boolean `printed == ["[1. 1.4] 0.71", "[1. 6.6] 0.15"]` (spaces normalised by `lines`). Run: the misread variant prints `[1.  1.4] 0.71`, `[1.  6.6] 0.15` and holds (C) alone; the snippet holds (B) alone.
- 8.12, the verification notebook: the timing on the wall clock failed when the cores were oversubscribed (18 burners on 12 cores: 1 failure in 6, growth 31.8 > 20, and 19.4 in another run). Origin: `timeit`'s default timer counts the time other processes take. Fix: `timer=time.process_time` for both timings, said in the markdown. Run: quiet, 6, 12 and 18 burners, 22 runs in all, every one holding (A) alone, growth 10.0–10.6.
- 8.11 (A), the worked notebook: "the times are fixed by μ̄, β and 1ᵀA" is false when the column sums are not constant (μ = (0.25, 0.25), β = 4: A = ((1, 0), (0, 3)) and ((0, 0), (1, 3)) share 1ᵀA = (1, 3) and have λ̄ = 1.333 and 1.5). Fix: "with constant column sums of A … and their common value, 3 in both pairs".
- F4: Proposition 1.3.23 and Corollary 1.3.25 assume ρ < 1; F4 did not say so. Fix: "At ρ < 1".
- 8.7: "its clusters are finite" and "every cluster dies out" uncited. Fix: the paragraph after Proposition 1.3.8 (`prop.clusterRepresentation`), which states extinction with finite expected size precisely when ρ < 1.
- 8.6: the coincidence of ρ and the endogenous fraction credited to F4 and the paragraph after Corollary 1.3.25, which gives ρ = 1 − 1/C̄; it follows from the identity of the entry when every column sum is ρ. Fix: so stated, with the first sufficient condition after the corollary.
- 8.12: "the quotient gives 256, 2681 and 26925": the quotients are 255.7, 2680.3, 26924.4; those are their ceilings, the number of products A makes. Fix: so stated, and the ceilings shown by the calculator.
- 8.10: √(2/n), the relative standard error of a sample variance, is a Gaussian fact from outside the notes; now said. Y written λ_g 1_(0,T], as in 7.1.

### Section 9 · The Markov state

- 9.1 `restartTheStateAfterAMarketSell`, choices (A) `F, F, T, F` and (D) `T, T, T, T` of the stem. No misreading yields either: `decayed_counts_at` is linear in the initial state, so line 4 is line 1 shifted by the sell and line 3 is line 2 shifted by it. Origin: the stem, distractors written as patterns of the outputs rather than from misreadings. Fix: (A) `F, F, T, T` (the event at the shifted time 0 taken for one already in Z(0+)), (D) `False` on every line (events and clock left unshifted); booleans changed. Confirmed: both variants run, F,F,T,T and F,F,F,F; the snippet prints T,F,T,F; the verification notebook passes.
- 9.1 (B), cell 6. "lines 1, 3 and 4 count it twice": line 4 counts the sell three times (first reading (0.25, 2.5) against (0.25, 1.5)). Origin: the draft, a count not run. Fix: "lines 1 and 3 twice and line 4 three times". Confirmed by the variant with `<=` throughout.
- 9.2 `millisecondClockKeepsTheState`, choice (B) of the stem, "True False, then False True". The misreading behind its first line (the state divided by c) carried into the second gives `False False`. Origin: the stem, the second line of a distractor not derived from its first. Fix: (B) "True False, then False False"; boolean changed. Confirmed: the forecast from z/1000 is (0.225, 0.245) against (0.233, 0.923).
- 9.3 (C), cell 12. "as if the sell … left more descendants" gives a sign, not the value −0.19. Origin: the draft, a misreading by analogy. Fix: `more` read as the count from `z2` less that from `z1`. Confirmed: the reversed snippet prints `0.00 0.00`, then `0.00 -0.19`.
- 9.4, cell 13. "Both `estimate_b` and `estimate_c` tend to λ*": they tend to λ* + A e^{30K}Φ(1)(z₀ − m), within e^{-48} of it. "The time … never read": `_advance` and `events` read it; it enters no draw. "(AΦ(1))₀₀ > 0, so both components exceed": the sells need (AΦ(1))₁₁ > 0 too. Origin: the draft, statements made in the limit or for one component. Fix: each stated exactly.
- 9.4 (E), cell 15. "takes the four to estimate one quantity" restated the choice. Fix: the homogeneity in time of F2 taken for stationarity.
- 9.5 `forecastBetweenEventsFollowsTheFlow`, choice (D) of the stem, "forecast_a and forecast_b". No definite misreading makes both unbiased: forecast_b ≥ forecast_a on every path. Origin: the stem. Fix: (D) "forecast_b only" (Z taken constant between events); boolean changed. Confirmed on 3000 paths: forecast_b differs from a, c, d by means (0.092, 2.235), (0.065, 1.310), (0.121, 2.941), standard errors at most 0.025.
- 9.5, cell 16. The overstatement of `forecast_c` on the buys was argued by "every event excites the sells", while the run prints a buy error of −0.02, within noise. Origin: the draft, a heuristic where the key's claim needs an argument. Fix: forecast_c is the forecast from the mean state m_{T_n,t}(Z(T_n+)), which exceeds Z(t+) by e^{-βu}(e^{Au} − I)Z(T_n+) + Φ(u)μ > 0. Confirmed: forecast_c − forecast_a has mean (0.0265, 0.925) and is non-negative on all 3000 paths.
- 9.8 `forecastAWindowThatOpensLater`, choices (C) and (D) of the stem. The misreading of (C), a difference of forward means depending on the horizons through their difference, makes all four right, (E); (D) was (C) with (A). Origin: the stem. Fix: (C) "window_d only" (the second argument of the forward means read as a time), (D) "window_b only" (a window forecast only from the state at its opening); booleans changed. Confirmed: window_d read with horizons (s+2) − s and (s+1) − s equals the target (0.5037, 2.1102).
- 9.9, cell 26. "a growth … of 8.3 for B": one run; six runs give 6.5 to 8.3. Origin: a measured value quoted as fixed. Fix: "about 7, varying from run to run", against the factor 16 of the exponentials, now quoted with 500 and 8000 per event.
- F3, cell 2. The limit of 1ᵀAΦ(h)e_{e'} as h → ∞ was stated outside the hypothesis ρ < 1 that eq. (1.3.35) needs. Fix: "If ρ < 1, …".
- (re-review) 9.1 (D): "every reading is decayed over two units too many": only the part from `z` is (run: line 1 reads (0.0625, 0.5) against (0.25, 0.5)). Fix: so stated.
- (re-review) 9.8 (D): the first-round misreading was a judgement no run reproduces; one that does: `forward_mean_counts(z, h)` read as the count of the h-th second, (s+h−1, s+h], under which `window_b` alone gives the target (0.5037, 2.1102). Fix: the bullet names it; the choice stands.

### Section 10 · The matrix exponential and the expected order flow

- 10.4 `blockExponentialOfOneMarketBuy`, worked cell 14 (B), and verification notebook cell 11: the misreading behind `1.375` was called "the decay left out" ("no decay" in the verification print). Leaving out the decay is β = 0, K = A = 2, and gives 2.148; 1.375 is K taken for zero, e^{Ku} = 1. Origin: draft and verification notebook, a misreading named without being run as code. Fix: "K taken for zero" in the entry and in the print label; the boolean is unchanged. Confirmed: generator entry (0, 0) set to 0 prints `[0.0, 1.0, 0.5]` / 1.375; set to 2 prints 2.148.
- 10.4, worked cell 14 (A): "the second row of Gh taken for that of e^{Gh}" read as `blocks = Gh` prints `[0.0, 0.0, 0.5]` then 1.25, not (A). Origin: draft, misreading named loosely. Fix: the identity dropped from e^{Gh}, the zero block's exponential taken for zero; the count reads off-diagonal entries only. Confirmed: `expm(G h) - I` prints `[0.0, 0.0, 0.5]` / 0.974.
- 10.4 stem (`matrix_exponential.tex`) and worked cell 12: e^{Kh}, Φ(h) and ∫Φ were called "the matrices of eq. (1.3.31, eq.forwardMeanCounts)"; e^{Kh} is in eq. (1.3.30, eq.forwardMeanState). Origin: stem, copied by the draft. Fix: both equations cited, in the stem and the entry. Confirmed: the two equations read in `stability.tex`; one-topic build, 0 undefined references.
- 10.4, worked cell 12: "E' = K E" for a block row; a row times G puts K on the right, E' = E K (as the key writes). Origin: draft; harmless at d = 1. Fix: E' = E K.
- 10.9 `signedCountDriftOnTheOneWayPair`, worked cell 28: "A Φ(100) = (I − Γ)^{-1} − I" stated as an equality; it holds up to A K^{-1} e^{100K}. Origin: draft. Fix: "up to A K^{-1} e^{100K}, negligible". Confirmed: max |A Φ(100) − ((I − Γ)^{-1} − I)| = 8.9e-16.
- 10.2 `seriesOnKAgainstSeriesOnTheExcitation`, worked cell 8 (C): "takes the size of the numbers for the loss of digits" read literally fails the series of Kh (terms of 1.1e27) and gives (D). Origin: draft, misreading not run. Fix: judges by the size of the sum, 2.3e-5 for Kh against 5e12 for Ah. Confirmed: largest term entry 1.13e27, float sum 4.0e11 against `expm` 2.27e-5, A-series sum 5.34e12.
- 10.11 `regimeSignAfterABurstOfBuys`, worked cell 34: "the sign is that of θ, Corollary 1.4.21" credited the corollary with more than it states; it decides by θ(h) of eq. (1.4.18). Origin: draft, citation credited with more than it states. Fix: the sign of θ(h) = θ(1 − e^{−(4−θ)h})/(4 − θ), which has the sign of θ at every h. Confirmed: θ(0.5) = 0.935 and −0.379 on the two pairs; the corollary read in `forecasting_the_mid.tex`.
- 10.12 `meanResponseOnAClockByEigenvalues`, worked cell 37: "ratios of about 40 at both sizes, and growths of about 10 and 11" quoted one run as general; over six runs the ratio is 39–44 at 10^4 and 33–39 at 10^5, the growths 9.3–11.2 (A) and 10.8–13.6 (B). Origin: draft, one run quoted. Fix: "ratios between 30 and 45, and growths of 9 to 11 for A and of 11 to 14 for B". Confirmed: the empirical reviewer's six runs; the verification notebook passes with thresholds ratio > 5, 4 < growth < 25.
- 10.12, verification notebook, timing cell. Each case was the minimum of 3 consecutive timings; under a shared load B's growth from n = 1e4 to 1e5 fell to 4.5 against the bound `4 < growth_b`, where no choice holds. Origin: the verification notebook, a measurement whose two sizes were timed at different moments, with B's time at n = 1e4 (about 1.3 ms) taken once a repeat. Fix: seven rounds of the four timings back to back, B repeated 200_000 // n times a timing so that its two timings last as long, and the medians of the ratios within a round; thresholds unchanged. Confirmed: old method, 9 runs at load 3-12, B growth 4.9-14.2; new, 15 harness runs (3 under six burners) B growth 6.0-11.9 and 5 executions of the notebook (2 under burners) 11.1-11.9, every run (B) alone. B's growth is bimodal (about 11, or 6-7 in some processes), at any load.
- 10.12, worked entry. "ratios between 30 and 45, growths of 9 to 11 for A and of 11 to 14 for B" held on a quiet machine only. Origin: one reviewer's quiet runs quoted as ranges. Fix: "ratios of some 30 to 55, and growths of about 10 for A and of 6 to 12 for B".
- 10.10, cell 31. The four values were quoted to three decimals from exact exponentials while the prose gives three-digit ones (which give -1.154, -1.154, 0.727, 0.670). Origin: the draft, values copied from the calculator. Fix: "about -1.15, -1.15, 0.73 and 0.67".
- 10.2 (C), cell 8. "5e12 for that of Ah" shown by no calculator cell. Fix: `0.5 * exp(30)` added to cell 7 (5.34e12).
- 10.11, cell 34. "of the sign of theta at every h": theta(0) = 0. Fix: "every h > 0".
- Verification notebook, markdown cell 10: "the decay ignored inside the integrals" for the misreading that gives 1.375, which is K taken for zero (dropping the decay gives 2.148). Fix: "K taken for zero".
- 10.4 (A) and (C): code indices written as matrix entries, "(0, 1)", "(0, 2)" of G, beside mathematics counted from 1. Fix: `blocks[0, 1]`, `blocks[0, 2]`, `generator[0, 2]`.

### Section 11 · Integers in binary

- 11.6 stem (`binary_tricks.tex`): "shifted down so that the lower end of the window is bit 0" had two readings for the asks of `TickArrayBook`, by bit and by price, and the key held under the bit reading only. Origin: the stem, worded on the price side where the package docstrings speak of bits. Fix: "so that the lowest set bit of the window is bit 0". Run: the snippet prints the key; the price reading prints `0b1011 0b1011`, choice (B).
- 11.6 data (`binary_tricks.tex`, verification cell 17): the asks 101, 102, 105, 106 lie symmetrically about 103.5, so misreading the direction of count, the point of the key's explanation, still printed the key. Origin: the stem's data, chosen without running the misreadings. Fix: asks 101, 102, 104, 106; new choices, booleans and explanation (bits 6, 7, 9, 11 and 5, 4, 2, 0; the cut at bit 2; 104 at bit 0). Run: `11-binary-tricks` executed, (D) alone holds; the count alone or the cut alone misread gives `0b10101`, no choice.
- 11.6 worked, cell 22, (A), (B), (E): the misreadings named (a book counting the other way; "the two books exchanged") printed the key on the old asks. Origin: the draft, misreadings described without being run. Fix: (A) and (B) both books taken to hold their asks as one of them does, count and cut together; (E) each book as the other. Run: `0b1101 0b1101`, `0b1011 0b1011`, `0b1101 0b1011` exactly.
- 11.1 worked, cell 5, (A), and the key's explanation: "the asks counted up from the floor, as the bids are" names a variant that prints `77 352 206 208` (touch the highest set bit) or never ends (`set_size` alone changed). Origin: the key's explanation, taken over by the draft without a run. Fix: the asks held as `BitmapBook` holds them, touch the lowest set bit, the matching unchanged. Run: subclass `AsksUp` prints `77 256 206 208`.
- 11.5 worked, cells 17 and 19: "`span_bits` shifts the window down to `0b110011`" holds only for a reported depth of four or more; at three the window is `0b11001`. Origin: the draft, depth left unstated. Fix: "with a reported depth of four or more". Run: `span_bits(BUY, 3)` is `0b11001`, at 4 and 5 `0b110011`; the three functions on it give `1 1 2`.
- F2, cell 2: the case $b = 0$ was cited to "the paragraph after the proposition"; it follows Listing A.4. Origin: the draft, citation placed without reading the source order. Fix: "the paragraph after Listing A.4 (`listing.lowestSetBit`)". Source: `binary_degree.tex`, line 76.
- F4, cell 2: Proposition 1.1.11 was credited with the remainder of a market order resting at its last fill and with the withdrawal; it states the decomposition of a limit order only. Origin: the draft, a citation credited with more than it states. Fix: the market-to-limit rule and the withdrawal cited to Section 1.2.3 (`sec.foldImplementation`), and "a market order that has traded". Source: `message_files.tex`, lines 302-316.
- 11.4 worked, cell 13: Proposition A.3.1 was cited for $\neg 8 = -9$ clearing bit 3 alone on the integers; it is stated modulo $2^{n+1}$. Origin: the draft, following the key's citation. Fix: cited to F3 (Section A.4). Source: `binary_complement.tex` states A.3.1 modulo $2^{n+1}$; `binary_embedding.tex`, line 55, states $\neg x = -x - 1$ on $\mathbb Z$.
- 11.7 worked, cell 23: "34 [digits] at $W = 10^3$, where the fixed cost of the call dominates": a one-digit read takes about 108 ns and a read at $W = 10^3$ about 195-233 ns, so the fixed cost is about half. Origin: the draft, not measured. Fix: "comparable to the work on the digits". Run: the empirical review's timings.
- 11.7 verification, cell 19: "about the same" was `< 2` and "about in proportion" `> 5`, with dead zones to the `> 5` and `< 2` of the other choices; under load the array growth reached 1.51, 2.00 and 2.72, and the bitmap's last growth 4.4 once. Origin: the verification notebook, thresholds tuned on a quiet machine. Fix: 20000 reads of `array` and 2000 of `bitmap` per measurement, the minimum of 9; constant `< 5` over the thousandfold range, the bound the other choices already use, and the last growth `> 3`, near the geometric midpoint 3.2 of 1 and 10. Run: 8 runs, 3 under six CPU burners, (A) alone holds in every one.
- (re-review) 11.5: Section A.8 credited with the trailing zeros flooding; it states the gaps; the docstring of `measure_largest_binary_gap` states the trailing zeros (run: one pass on 816 gives 0b1110111000). Fix: both cited for what each says.
- (re-review) 11.4, key's explanation in binary_tricks.tex: Proposition A.3.1 (`prop.twosComplement`), stated modulo 2^(n+1), cited for ¬8 = −9 clearing bit 3 on the integers. Origin: the key, a citation of the nearest statement. Fix: Definition A.4.1, already cited in the same explanation, gives it.
- (re-review) 11.7: a sentence left without its verb by the first-round fix. Fix: restored.

### The package

- `unito26.lob.hawkes._mean_response_blocks`: a stack of horizons passed to `scipy.linalg.expm` in one call comes back wrong when unsorted (scipy 1.18.0). Found by the empirical review of section 9; reproduced; not fixed.

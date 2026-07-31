# Revision Audit — `paper/acl_latex.tex`

Editorial pass performed 2026-07-31 on branch `agent/master-tables`.
Baseline commit: `cea656f`. All changes are reviewable via
`git diff cea656f -- paper/acl_latex.tex`.

## Scope note (important)

The editorial brief supplied was a **generic template written for a different
paper** — its paper-specific sections (§8 "Paper-Specific Editorial Direction"
and §9 "Suggested Narrative Shape") describe a *consensus / early-exit
terminality* paper (intermediate-answer agreement, consensus rules, probe
overhead). This manuscript is about **PRM reasoning-step removability**. The
template itself says to apply §8–§9 *only if they match the repository*; they do
not. I therefore applied the **general** principles (§1–§7, §10–§16) and ignored
the consensus-specific direction.

This is also a **mature manuscript** that has already been through four rounds of
number-verified mock review, with a 141-check consistency script
(`scripts/check_paper_consistency.py`) and a hard ACL 8-page content limit. It
did **not** need a ground-up restructure (its section order already follows the
argument). The correct editorial move here was selective compression, not
demolition, with the checker and page count as guardrails.

## Original diagnosis

**Central story (already present, but buried under repetition):** A PRM's local
correctness score identifies *where* deletion helps (low-rated, semantically
harmful "negative anchors") but not *whether* deletion is safe; turned into
rollback policies, correctness-based certificates are split-unstable and
checkpoint-dependent, so safe rollback needs a cheap counterfactual probe, not a
correctness threshold.

**Main structural weakness — length.** The 11 commits of 2026-07-29 added new
robustness analyses (position, anchor-by-position, random-label), a semantic-label
ablation, and Figure 5 directly into the main body. This pushed the content
(Intro → Conclusion) **~2 pages past the 8-page ACL limit**: at baseline the
Conclusion ran onto page 10 and Limitations began on page 10. This is a
submission-blocking violation and was the single most important thing to fix.

**AI-generated-paper patterns detected (per the brief's rubric):**

- *§5.12 Numeric density.* The Abstract was one ~350-word block with ~15 numbers;
  the Introduction "three findings" paragraph was a ~400-word block restating
  every headline statistic.
- *§5.6 Repetition.* The three findings appeared in near-identical form in the
  Abstract, the Intro findings paragraph, the Intro contributions list, and again
  as a numeric second paragraph in the Conclusion (a compressed second abstract).
  The "Label convention" note appeared verbatim in both the Introduction and §4.
- *§5.10 Reviewer preemption.* Round-by-round review scar tissue: most claims were
  immediately followed by a disclaimer ("not evidence that reasoning compression
  is impossible", "these are exploratory diagnostics; the safety conclusions rest
  on…", "neither is a deployment estimate", etc.).
- *§5.1 / §5.11 Result-list structure.* §4 (Data & Protocol) contained a run of
  robustness `\paragraph` blocks (human pilot, position, anchor-by-position,
  random-label) wedged between the cohort description and the interventions —
  robustness reported inside the method section, before any result.
- *§5.13 Redundant main-text tables.* Four robustness tables (human pilot,
  position, random-label, label ablation) sat in the main body; one (label
  ablation) also produced a 29 pt overfull box.

**Contribution hierarchy:** already correct in substance but not in emphasis —
replications (phi-4, long-CoT, thinking-toggle, ProcessBench) and the deployed-PRM
signal sweep were written with the same rhetorical weight as the three core
findings.

**Claims vs evidence:** claims were generally well-scoped (the "Alone" in the
title and "a priori"/"cannot be trusted … a priori" in the abstract keep the
negative result finite). No unsupported universal/impossibility claims were found.
The main issue was density and repetition, not overreach.

## Revised plan

**One-sentence thesis.** A PRM's local correctness score identifies where
reasoning-step deletion helps but not whether it is safe; safe rollback therefore
requires counterfactual validation, not a correctness threshold.

**One-paragraph story.** Reusing PRM correctness scores to trigger a rollback
assumes local correctness predicts what happens when a step is removed. Testing
that assumption with a counterfactual protocol (control / deletion / own-control
placebo / meaning-preserving paraphrase) on 600 rating-balanced PRM800K steps, we
find deletion gains concentrate almost entirely in low-rated *harmful* steps that
act as negative anchors for no-thinking generation; an apparent generic "restart"
benefit is a placebo artifact that vanishes under own controls, and extended
thinking removes the effect entirely. Turned into deployment-weighted rollback
policies, correctness-based certificates are unstable across splits and
checkpoint-dependent, so a correctness score cannot certify rollback safety a
priori — but a single probe-and-rollback generation recovers most of an oracle's
safety.

**Ranked contribution hierarchy.**
1. *Primary:* correctness ≠ counterfactual removability/safety — the construct gap
   and its consequence, unstable and checkpoint-dependent certification.
2. *Supporting:* the negative-anchor mechanism (own-control placebo + paraphrase
   triangulation), and the probe-and-rollback remedy.
3. *Robustness / external validity (not parallel contributions):* position,
   anchor-by-position, random-label, and length controls; cross-generator,
   long-CoT, and thinking-toggle replications; ProcessBench transfer; the
   deployed-PRM/uncertainty signal sweep.

**Narrative structure.** Section order was left unchanged (it already follows the
argument: constructs → protocol → full-cohort results → mechanism → external
validation → signals → policies → discussion). The revision changed *prose economy
and placement of robustness material*, not the section skeleton.

**Narrative climax.** §9 (From Scores to Policies): the nested train/calibrate/test
certification failure — one trained PRM certifies in every split yet meets its
budget on only 9 of 20 test splits while a sibling PRM transfers on most — followed
by the probe-and-rollback repair.

## Content decisions

| Component | Decision |
|---|---|
| Abstract | **Shortened** — dropped ~6 secondary numbers (23k continuations, 1,513/1,514, −6.3 pp, +21.8→−3.0); kept the two headline effects and the 9/20 instability. |
| Intro "three findings" paragraph | **Shortened** — ~400→~180 words; numbers moved to the results tables; findings re-labelled descriptively rather than "First/Second/Third". |
| Intro "Label convention" paragraph | **Removed** — duplicated §4. |
| §4 "Human-only label robustness" | **Shortened + merged** into "Human-only label pilot"; de-duplicated the 27.3% bound already stated in "Step cohort". |
| §4 "Position robustness", "Anchor-by-position", "Random-label" | **Merged** into one "not a position/length/label-frequency artifact" paragraph with appendix pointers. |
| Table (human pilot) | **Moved to appendix.** |
| Table (position) | **Moved to appendix.** |
| Table (random-label) | **Moved to appendix.** |
| §5 "Semantic-label ablation" | **Shortened**; its table **moved to appendix** (also fixed a 29 pt overfull box). |
| §5 "Length-adjusted robustness" | **Merged** into the §4 robustness paragraph (its coefficients already live in `tab:lengthreg`, appendix). |
| §5 "Long-CoT" + "Thinking-mode" | **Merged** into one "Extended thinking neutralizes anchors" paragraph (one finding, shown two ways). |
| §5 "Cross-generator", "Trajectory state", "Step-level stability" | **Retained** (shortened cross-generator). |
| §5 main interpretation paragraph | **Shortened** — off-diagonal small-n cell values dropped (they are in the tables). |
| Figure 1 (protocol) | **Retained** as central. |
| Figure 5 (rating × effect scatter) | **Retained** as the visual of the core dissociation; **added the missing in-text reference** (was uncited at baseline). |
| §9 "balanced vs natural prevalence" | **Shortened** — removed a caveat already in Limitations; detail counts kept in `tab:frame`. |
| §9 "What certifies" | **Shortened** — removed a reviewer-preemption clause. |
| §9 "Honest nested selection" | **Shortened** — ~40% cut; three failure modes and all key numbers retained; D/E re-explanation (already in the table caption) removed. |
| §9 "Rollback probe" | **Shortened** — dropped the do-nothing calibration sanity numbers; headline result kept. |
| Discussion & Conclusion | **Merged** two paragraphs into one; removed the numeric second-abstract; **added explicit scope** (mid-size open models, math, no-thinking regime). |
| Tables/figures in appendix, Related Work, Constructs, Limitations, Ethics | **Retained unchanged.** |

No experimental value was changed. Every relocated table kept its `\label`; every
`\ref` still resolves.

## Verification issues (for author attention)

1. **Template mismatch (resolved by judgment).** The brief's §8/§9 target a
   different paper; I applied only the general principles. Confirm you are happy
   with a *selective-compression* pass rather than a section-level restructure.
2. **Figure 5 was uncited at baseline** — I added `Figure~\ref{fig:ratingeffect}`
   in the main-results paragraph. Confirm the placement.
3. **Human-pilot "82% adjudication accuracy" remains unrestored.** The paper
   honestly states the adjudicator "resolved all 46 disagreements" without a
   number; the adjudicator's decisions are still only handwritten (not
   transcribed to `m3_adjudication_final.csv`). Not changed here.
4. **Dropped CIs on two n.s. replications.** The R1-Distill DiD CI `[−7.8,+6.3]`
   and the thinking-toggle anchor CI `[−8.0,+2.3]` were removed from the merged
   §5 paragraph (the "n.s." verdict is retained). They live in the workstream
   reports but not in an appendix table; add one if a reviewer wants the interval.
5. **Title assertiveness.** "Correctness Scores Alone Are Unreliable Safety
   Certificates" is a finite empirical result stated as a general title; the
   abstract and body scope it correctly ("a priori", "for the evaluated
   settings"). Left as the author set it.

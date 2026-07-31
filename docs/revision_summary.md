# Revision Summary — `paper/acl_latex.tex`

Selective editorial pass, 2026-07-31, branch `agent/master-tables`, on top of
baseline commit `cea656f`.

## Files changed

- `paper/acl_latex.tex` — all edits (89 insertions, 106 deletions).
- `paper/acl_latex.pdf` — recompiled artifact.
- `revision_audit.md`, `revision_summary.md` — new deliverables.

No data files, scripts, or numbers were touched.

## Primary outcome: ACL page limit restored

The 2026-07-29 additions had pushed the content (Introduction → Conclusion)
**~2 pages over** the 8-page ACL limit (Conclusion ran onto page 10). After this
pass the **Conclusion ends on page 8 and Limitations begins on page 9**, with
Limitations/Ethics/References/Appendix following. Total document length: 16 → 15
pages.

## Major structural edits

- **Relocated the §4 robustness cluster to the appendix.** Four robustness tables
  (human pilot, position, random-label, semantic-label ablation) moved from the
  main body to `\appendix`/`app:robust`, each behind a compact in-text pointer.
  This removed robustness material from the *method* section (where it read as a
  result-list) and reclaimed most of the over-length.
- **Consolidated the §5 result-list.** The separate "Long-CoT replication" and
  "Thinking-mode contrast" paragraphs were merged into one
  "Extended thinking neutralizes anchors" paragraph; the position/anchor-by-
  position/random-label/length paragraphs were merged into a single
  "not a position/length/label-frequency artifact" paragraph.
- **De-duplicated the top and tail.** Removed the Intro "Label convention"
  paragraph (verbatim duplicate of §4) and merged the two-paragraph
  Discussion/Conclusion into one, deleting its numeric "second abstract".

## Claims narrowed / rewritten

- Abstract and the Intro "three findings" paragraph rewritten for lower numeric
  density (headline effects and the 9/20 certification-instability result kept;
  secondary statistics moved to the results tables).
- Reviewer-preemption disclaimers thinned (each load-bearing caveat kept once, in
  its most appropriate location — mostly Limitations).
- The Conclusion now states explicit empirical **scope** (mid-size open generators,
  mathematical reasoning, no-thinking regime) instead of restating all findings.
- No claim was strengthened; the negative result stays finite ("a priori",
  "cannot be trusted … a priori").

## Contribution hierarchy

Reweighted (via space and phrasing, not new claims): one primary contribution
(correctness ≠ counterfactual removability/safety), two supporting (negative-anchor
mechanism; probe-and-rollback remedy), everything else framed as robustness /
replication / external validity.

## Figures and tables

- Figure 1 (protocol) and Figure 5 (rating × deletion-effect scatter) retained in
  the main body; **Figure 5's missing in-text citation was added** (it was uncited
  at baseline).
- Tables moved to the appendix: `tab:humanpilot`, `tab:position`,
  `tab:randomlabel`, `tab:labelablation`. All keep their labels and remain
  referenced.
- Fixed the 29 pt overfull box in the label-ablation table (shortened one
  first-column row).

## Material moved to the appendix

Human-only pilot table, position-robustness table, random-label negative-control
table, semantic-label-ablation table (all previously in the main body).

## Remaining concerns

- Human-pilot "82% adjudication accuracy" is still unrestored (records not
  digitized); the paper states the adjudicator resolved all 46 disagreements
  without a number.
- Two n.s. replication CIs were dropped from main-text prose (verdict "n.s."
  retained); add an appendix row if a reviewer requests the intervals.
- One pre-existing trivial overfull box remains (1.08 pt, generation-budget
  table `tab:generationbudget`) — cosmetically negligible.

## Compilation

- **Command:** `pdflatex acl_latex.tex → bibtex acl_latex → pdflatex ×2`
  (run from `paper/`). Equivalent: `latexmk -pdf acl_latex.tex`.
- **Result:** succeeds; no fatal errors; no undefined references or citations; no
  orphaned (unreferenced) floats.
- **Final page count:** 15 (content ends page 8; Limitations page 9).
- **Overfull boxes:** 1 (pre-existing, 1.08 pt).
- **Consistency checker:** `python3 scripts/check_paper_consistency.py` — all 141
  checks pass.

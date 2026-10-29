# Journal format notes (TACL)

Target: *Transactions of the Association for Computational Linguistics* (MIT Press). Chosen by a research
pass over the journal's guidelines, template and four published papers; the notes below record what was
found and where, so the draft can be re-checked against the live sources.

## Sources read

- Author guidelines: https://transacl.org/index.php/tacl/about/submissions
- Formatting instructions: https://transacl.org/tacl-submission-templates/tacl2021v1-submission-formatting-instructions.pdf
- Template files (Dec. 2021): `tacl2021v1.sty`, `tacl2021v1-template.tex`, `acl_natbib.bst` under
  https://transacl.org/tacl-submission-templates/ (Overleaf copy linked from the guidelines page)
- Published papers read in full: Guo et al. 2022 (aclanthology.org/2022.tacl-1.11),
  Meister et al. 2023 (2023.tacl-1.7, definitions and proofs), Jiang et al. 2024 (2024.tacl-1.7, theorems
  with appendix proofs), Glockner et al. 2024 (2024.tacl-1.1, has a Limitations section)

## Format facts applied

| Item | TACL | In this draft |
|---|---|---|
| Page and columns | A4, 2.5 cm margins, two columns of 7.7 cm, 0.6 cm gutter | same |
| Fonts | Times, body 11 pt, title about 14.3 pt bold, section titles 12 pt bold, captions 10 pt | same |
| Headings | `1 Introduction`, `2.1 Name`, both bold | same |
| Abstract | "Abstract" 12 pt bold, text 10 pt, narrower than the page | same |
| Captions | below tables and figures, "Table 1:" / "Figure 1:" | same |
| Tables | horizontal rules only | same |
| Equations | right-aligned numbers `(1)` | same |
| Theorems | bold run-in label with number and name, italic statement, italic "Proof." and an end mark | same; numbering is global |
| Unnumbered headings | Limitations, then Acknowledgments, then References | same |
| Appendices | after References, `A Title`, `A.1 Name` | same |
| Citations | natbib author-year: (Guo et al., 2022) and Guo et al. (2022) | same |
| References | alphabetical, full given names, no "et al.", DOI where available | same |
| Page 1 footer | production data added by MIT Press (volume, action editor, batches, licence) | shown as a demo |
| Length | 7 to 10 A4 pages including appendices, references excluded, no supplementary material | 9 pages including references |

## Submission-mode differences (not applied: this is a demo)

- Double blind: anonymous author block ("Anonymous TACL submission"), no self-identifying links, own work cited in the third person
  (the earlier study is cited as "Anonymous, 2026").
- Header "Confidential TACL submission. DO NOT DISTRIBUTE." on every page and a line-number ruler.
- The template defines no theorem environments; the `.tex` adds `amsmath`, `amssymb` and `amsthm`.

## References: verification status

Each entry was checked against a primary source (ACL Anthology, Crossref, NeurIPS proceedings, arXiv,
publisher front matter). Corrections made from that check:

- Angelopoulos and Bates: cited as the journal version (*Foundations and Trends in Machine Learning*, 2023),
  not the arXiv preprint; TACL prefers the peer-reviewed version.
- Page ranges and volumes added for the NeurIPS papers (Schlichtkrull et al., Wang et al., Zheng et al.) and for
  both EMNLP papers; DOIs added throughout.
- Manakul et al.: the Anthology lists the third author as "Mark Gales".

Open items:

- Ji et al.: the article number 248 rests on a DBLP listing; the ACM page could not be opened. The published
  record has ten authors, the arXiv version thirteen; the published list is used.
- Mahalanobis (1936): the repository and encyclopedia sources spell the title "generalized"; the printed original
  could not be opened to confirm the spelling.
- Min et al.: the Anthology shows "Pang Koh", arXiv shows "Pang Wei Koh"; the arXiv spelling is used.
- Efron: given name "Bradley" is from general knowledge; the sources list "B. Efron".
- Cover and Thomas: second edition, 2006 (Wiley-Interscience). The theorem number for Gibbs' inequality
  (Chapter 2, Section 2.6) was not confirmed, so the draft cites the book without a theorem number.
- Check the live guidelines page for a template newer than December 2021 before submitting.

## Not verified here

- The `.tex` has not been compiled: no TeX engine is installed on this machine. The PDF was produced from the
  Word file.
- Computational Linguistics was considered as an alternative; its guidelines page could not be retrieved, so its
  page limit is unconfirmed. TACL is the default; switch only if the proofs cannot fit within 10 pages.

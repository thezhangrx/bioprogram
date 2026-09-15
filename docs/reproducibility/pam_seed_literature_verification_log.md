# Verified reference list — PAM-proximal / seed-region importance and single-nucleotide guide sensitivity

Every reference below was verified against **Crossref** (title + venue + year + DOI) and, where available, **PubMed**
(PMID). Verification was done programmatically via `api.crossref.org/works/{DOI}` and NCBI E-utilities; the raw
per-reference output is in `crispr_doi_results.json`, `crispr_doi2_results.json`, `crispr_title_results.json`.

**Key negative finding:** no verified publication reports an experimentally measured effect of the nucleotide
identity at **guide position 18** specifically (or of a C→A/C→G/C→T substitution at that position). The
position-18 C→A counterfactual must therefore be presented as a novel candidate hypothesis, not as literature-backed.

---

## A. EXPERIMENTAL EVIDENCE (original research: experimental / structural)

Ordered by usefulness for the paper's claims.

1. **`Fu2014NatBiotech`** — Fu Y, et al. "Improving CRISPR-Cas nuclease specificity using truncated guide RNAs."
   *Nature Biotechnology*, 2014, 32(3):279–284. DOI: 10.1038/nbt.2808 · PMID: 24463574
   *Supports:* guides truncated to the PAM-proximal ~17–18 nt retain on-target activity while reducing off-target
   effects — direct experimental evidence that the PAM-proximal part of the guide carries the activity-determining
   information and that its exact sequence is critical. **Evidence type:** original research (experimental).

2. **`Zheng2017SciRep`** — Zheng T, et al. "Profiling single-guide RNA specificity reveals a mismatch sensitive core
   sequence." *Scientific Reports*, 2017, 7:40638. DOI: 10.1038/srep40638 · PMID: 28098181
   *Supports:* systematic single-mismatch profiling identifies a PAM-proximal "mismatch-sensitive core" — background
   plausibility that single-nucleotide identity in this window changes activity. **Evidence type:** original research
   (experimental).

3. **`Boyle2017PNAS`** — Boyle EA, et al. "High-throughput biochemical profiling reveals sequence determinants of
   dCas9 off-target binding and unbinding." *PNAS*, 2017, 114(21):5461–5466. DOI: 10.1073/pnas.1700557114 ·
   PMID: 28495970
   *Supports:* quantitative, position-resolved biochemical measurement of how single mismatches across the guide
   alter Cas9 binding/unbinding kinetics; PAM-proximal positions are the most disruptive. **Evidence type:** original
   research (experimental/biochemical).

4. **`Hsu2013NatBiotech`** — Hsu PD, et al. "DNA targeting specificity of RNA-guided Cas9 nucleases."
   *Nature Biotechnology*, 2013, 31(9):827–832. DOI: 10.1038/nbt.2647 · PMID: 23873081
   *Supports:* mismatch tolerance is position-dependent, with PAM-proximal (seed) mismatches far less tolerated than
   PAM-distal ones. **Evidence type:** original research (experimental).

5. **`Doench2014NatBiotech`** — Doench JG, et al. "Rational design of highly active sgRNAs for CRISPR-Cas9-mediated
   gene inactivation." *Nature Biotechnology*, 2014, 32(12):1262–1267. DOI: 10.1038/nbt.3026 · PMID: 25184501
   *Supports:* position-specific nucleotide-composition rules for guide efficacy, including preferences at
   PAM-proximal positions — background plausibility that base identity near the PAM modulates activity.
   **Evidence type:** original research (experimental + sequence model).

6. **`MorenoMateos2015NatMethods`** — Moreno-Mateos MA, et al. "CRISPRscan: designing highly efficient sgRNAs for
   CRISPR-Cas9 targeting in vivo." *Nature Methods*, 2015, 12(10):982–988. DOI: 10.1038/nmeth.3543 · PMID: 26322839
   *Supports:* position-specific nucleotide composition in the PAM-proximal (3′) end of the spacer is a determinant of
   in vivo activity. **Evidence type:** original research (experimental + sequence model).

7. **`Xu2015GenomeRes`** — Xu H, et al. "Sequence determinants of improved CRISPR sgRNA design."
   *Genome Research*, 2015, 25(8):1147–1157. DOI: 10.1101/gr.191452.115 · PMID: 26063738
   *Supports:* large-scale identification of position-specific nucleotide determinants of sgRNA activity.
   **Evidence type:** original research (experimental + sequence model).
   *(Note: venue is Genome Research, not Genome Biology.)*

8. **`Jiang2013NatBiotech`** — Jiang W, et al. "RNA-guided editing of bacterial genomes using CRISPR-Cas systems."
   *Nature Biotechnology*, 2013, 31(3):233–239. DOI: 10.1038/nbt.2508 · PMID: 23360965
   *Supports:* position-dependent effect of guide mutations, with PAM-proximal (seed) mutations strongly impairing or
   abolishing targeting. **Evidence type:** original research (experimental).

9. **`Semenova2011PNAS`** — Semenova E, et al. "Interference by clustered regularly interspaced short palindromic
   repeat (CRISPR) RNA is governed by a seed sequence." *PNAS*, 2011, 108(25):10098–10103.
   DOI: 10.1073/pnas.1104144108 · PMID: 21646539
   *Supports:* the original "seed sequence" concept — PAM-proximal guide nucleotides dominate target recognition.
   **Evidence type:** original research (experimental).

10. **`Jost2020NatBiotech`** — Jost M, et al. "Titrating gene expression using libraries of systematically attenuated
    CRISPR guide RNAs." *Nature Biotechnology*, 2020, 38(3):355–364. DOI: 10.1038/s41587-019-0387-5 ·
    PMID: 31932729
    *Supports:* experimentally measured, graded activity changes produced by defined single/multiple nucleotide
    changes in the guide — templates the kind of wet-lab validation the position-18 hypothesis needs.
    **Evidence type:** original research (experimental).

11. **`Kim2020NatBME`** — Kim HK, et al. "High-throughput analysis of the activities of xCas9, SpCas9-NG and SpCas9
    at matched and mismatched target sequences in human cells." *Nature Biomedical Engineering*, 2020, 4(1):111–124.
    DOI: 10.1038/s41551-019-0505-1 · PMID: 31937939
    *Supports:* matched-vs-mismatched target series quantifying how individual nucleotide substitutions change
    activity in cells. **Evidence type:** original research (experimental).

12. **`Nishimasu2014Cell`** — Nishimasu H, et al. "Crystal structure of Cas9 in complex with guide RNA and target
    DNA." *Cell*, 2014, 156(5):935–949. DOI: 10.1016/j.cell.2014.02.001 · PMID: 24529477
    *Supports:* base-specific guide–target and protein–nucleotide contacts along the heteroduplex, giving a physical
    basis for why particular positions/bases matter. **Evidence type:** original research (structural).

13. **`Anders2014Nature`** — Anders C, et al. "Structural basis of PAM-dependent target DNA recognition by the Cas9
    endonuclease." *Nature*, 2014, 513(7519):569–573. DOI: 10.1038/nature13579 · PMID: 25079318
    *Supports:* structural basis of PAM readout and of the PAM-proximal nucleation of the guide–target duplex.
    **Evidence type:** original research (structural).

14. **`Jiang2016Science`** — Jiang F, et al. "Structures of a CRISPR-Cas9 R-loop complex primed for DNA cleavage."
    *Science*, 2016, 351(6275):867–871. DOI: 10.1126/science.aad8282 · PMID: 26841432
    *Supports:* R-loop structure showing the ordered, PAM-proximal-to-distal build-up of the guide–target duplex
    before cleavage. **Evidence type:** original research (structural).

15. **`Szczelkun2014PNAS`** — Szczelkun MD, et al. "Direct observation of R-loop formation by single RNA-guided Cas9
    and Cascade effector complexes." *PNAS*, 2014, 111(27):9798–9803. DOI: 10.1073/pnas.1402597111 ·
    PMID: 24912165
    *Supports:* PAM-proximal nucleation and directional R-loop propagation — mechanistic basis for positional
    asymmetry in mismatch sensitivity. **Evidence type:** original research (experimental/biophysical).

---

## B. COMPUTATIONAL / MODEL-BASED PAPERS

16. **`Konstantakos2022NAR`** — Konstantakos V, et al. "CRISPR–Cas9 gRNA efficiency prediction: an overview of
    predictive tools and the role of deep learning." *Nucleic Acids Research*, 2022, 50(7):3616–3637.
    DOI: 10.1093/nar/gkac192 · PMID: 35349718
    *Supports:* authoritative survey of on-target/efficiency prediction models and, critically, of how (and how
    weakly) their predictions are experimentally validated. **Evidence type:** review.
    *(Note: correct DOI is gkac192.)*

17. **`Wang2019NatCommun`** — Wang D, et al. "Optimized CRISPR guide RNA design for two high-fidelity Cas9 variants
    by deep learning." *Nature Communications*, 2019, 10:4284. DOI: 10.1038/s41467-019-12281-8 · PMID: 31537810
    (DeepHF)
    *Supports:* deep-learning model with explicit position-dependent nucleotide-composition analysis of high- vs
    low-activity guides — precedent for interpreting learned positional preferences. **Evidence type:** methods
    (computational, with experimental training data).

18. **`Xiang2021NatCommun`** — Xiang X, et al. "Enhancing CRISPR-Cas9 gRNA efficiency prediction by data integration
    and deep learning." *Nature Communications*, 2021, 12:3238. DOI: 10.1038/s41467-021-23576-0 · PMID: 34050182
    (CRISPRon)
    *Supports:* state-of-the-art efficiency prediction with data integration, plus experimental validation of
    predictions — a model for how to frame and test the position-18 counterfactual. **Evidence type:** methods
    (computational + experimental validation).
    *(Note: venue is Nature Communications, not Nature Biotechnology.)*

19. **`Arbab2020Cell`** — Arbab M, et al. "Determinants of base editing outcomes from target library analysis and
    machine learning." *Cell*, 2020, 182(2):463–480.e30. DOI: 10.1016/j.cell.2020.05.037 · PMID: 32533916
    *Supports:* machine learning on a large experimentally measured target library to attribute editing outcomes to
    guide/target sequence — the standard of evidence for pairing model-derived sequence effects with wet-lab data.
    **Evidence type:** original research (experimental + computational).

20. **`Thean2022NatCommun`** — Thean DGL, et al. "Machine learning-coupled combinatorial mutagenesis enables
    resource-efficient engineering of CRISPR-Cas9 genome editor activities." *Nature Communications*, 2022, 13:2219.
    DOI: 10.1038/s41467-022-29874-5 · PMID: 35468907
    *Supports:* explicit workflow in which model-guided predictions of mutational effects are experimentally
    validated — direct precedent for the "candidate hypothesis requiring wet-lab validation" framing.
    **Evidence type:** methods (computational + experimental validation).
    *(Note: first author is Thean, not Bhattacharya.)*

---

## C. ADDITIONAL VERIFIED REFERENCES (lower priority, all DOI/PMID-checked)

| Key | Reference (first author, venue, year) | DOI | PMID |
|---|---|---|---|
| `Jinek2012Science` | Jinek M, et al. *Science* 2012, 337:816–821 | 10.1126/science.1225829 | 22745249 |
| `Cong2013Science` | Cong L, et al. *Science* 2013, 339:819–823 | 10.1126/science.1231143 | 23287718 |
| `Mali2013Science` | Mali P, et al. *Science* 2013, 339:823–826 | 10.1126/science.1232033 | 23287722 |
| `Jinek2014Science` | Jinek M, et al. *Science* 2014, 343:1247997 | 10.1126/science.1247997 | 24505130 |
| `Sternberg2014Nature` | Sternberg SH, et al. *Nature* 2014, 507:62–67 | 10.1038/nature13011 | 24476820 |
| `Sternberg2015Nature` | Sternberg SH, et al. *Nature* 2015, 527:110–113 | 10.1038/nature15544 | 26524520 |
| `Chen2017Nature` | Chen JS, et al. *Nature* 2017, 550:407–410 | 10.1038/nature24268 | 28931002 |
| `Lim2016NatCommun` | Lim Y, et al. *Nature Communications* 2016, 7:13350 | 10.1038/ncomms13350 | 27804953 |
| `Gong2018CellRep` | Gong S, et al. *Cell Reports* 2018, 22:359–371 | 10.1016/j.celrep.2017.12.041 | 29320733 |
| `Ivanov2020PNAS` | Ivanov IE, et al. *PNAS* 2020, 117:5853–5860 | 10.1073/pnas.1913445117 | 32123105 |
| `Anderson2015JBiotech` | Anderson EM, et al. *J Biotechnol* 2015, 211:56–65 | 10.1016/j.jbiotec.2015.06.427 | 26189696 |
| `Fu2013NatBiotech` | Fu Y, et al. *Nature Biotechnology* 2013, 31:822–826 | 10.1038/nbt.2623 | 23792628 |
| `Slaymaker2016Science` | Slaymaker IM, et al. *Science* 2016, 351:84–88 | 10.1126/science.aad5227 | 26628643 |
| `Kleinstiver2016Nature` | Kleinstiver BP, et al. *Nature* 2016, 529:490–495 | 10.1038/nature16526 | 26735016 |
| `Kleinstiver2015Nature` | Kleinstiver BP, et al. *Nature* 2015, 523:481–485 | 10.1038/nature14592 | 26098369 |
| `Nishimasu2018Science` | Nishimasu H, et al. *Science* 2018, 361:1259–1262 | 10.1126/science.aas9129 | 30166441 |
| `Chari2015NatMethods` | Chari R, et al. *Nature Methods* 2015, 12:823–826 | 10.1038/nmeth.3473 | 26167643 |
| `Wang2014Science` | Wang T, et al. *Science* 2014, 343:80–84 | 10.1126/science.1246981 | 24336569 |
| `Wong2015GenomeBiol` | Wong N, et al. *Genome Biology* 2015, 16:218 | 10.1186/s13059-015-0784-0 | 26521937 |
| `Liu2016SciRep` | Liu X, et al. *Scientific Reports* 2016, 6:19675 | 10.1038/srep19675 | 26813419 |
| `Graf2019CellRep` | Graf R, et al. *Cell Reports* 2019, 26:1098–1103.e3 | 10.1016/j.celrep.2019.01.024 | 30699341 |
| `Dang2015GenomeBiol` | Dang Y, et al. *Genome Biology* 2015, 16:280 | 10.1186/s13059-015-0846-3 | 26671237 |
| `Wu2014NatBiotech` | Wu X, et al. *Nature Biotechnology* 2014, 32:670–676 | 10.1038/nbt.2889 | 24752079 |
| `Kuscu2014NatBiotech` | Kuscu C, et al. *Nature Biotechnology* 2014, 32:677–683 | 10.1038/nbt.2916 | 24837660 |
| `Tsai2015NatBiotech` | Tsai SQ, et al. *Nature Biotechnology* 2015, 33:187–197 | 10.1038/nbt.3117 | 25513782 |
| `Kim2015NatMethods` | Kim D, et al. *Nature Methods* 2015, 12:237–243 | 10.1038/nmeth.3284 | 25664545 |
| `Cameron2017NatMethods` | Cameron P, et al. *Nature Methods* 2017, 14:600–606 | 10.1038/nmeth.4284 | 28459459 |
| `Qi2013Cell` | Qi LS, et al. *Cell* 2013, 152:1173–1183 | 10.1016/j.cell.2013.02.022 | 23452860 |
| `Bikard2013NAR` | Bikard D, et al. *Nucleic Acids Research* 2013, 41:7429–7437 | 10.1093/nar/gkt520 | 23761437 |
| `Ran2013NatProtoc` | Ran FA, et al. *Nature Protocols* 2013, 8:2281–2308 | 10.1038/nprot.2013.143 | 24157548 |
| `Jore2011NSMB` | Jore MM, et al. *Nat Struct Mol Biol* 2011, 18:529–536 | 10.1038/nsmb.2019 | 21460843 |
| `Wiedenheft2011Nature` | Wiedenheft B, et al. *Nature* 2011, 477:486–489 | 10.1038/nature10402 | 21938068 |
| `Doench2016NatBiotech` | Doench JG, et al. *Nature Biotechnology* 2016, 34:184–191 | 10.1038/nbt.3437 | 26780180 |
| `Doench2018NatRevGenet` | Doench JG. *Nature Reviews Genetics* 2018, 19:67–80 | 10.1038/nrg.2017.97 | 29199283 |
| `Jiang2017AnnuRevBiophys` | Jiang F & Doudna JA. *Annu Rev Biophys* 2017, 46:505–529 | 10.1146/annurev-biophys-062215-010822 | 28375731 |
| `Haeussler2016GenomeBiol` | Haeussler M, et al. *Genome Biology* 2016, 17:148 | 10.1186/s13059-016-1012-2 | 27380939 |
| `Kim2019SciAdv` | Kim HK, et al. *Science Advances* 2019, 5:eaax9249 | 10.1126/sciadv.aax9249 | 31723604 |
| `Kim2018NatBiotech` | Kim HK, et al. *Nature Biotechnology* 2018, 36:239–241 | 10.1038/nbt.4061 | 29431740 |
| `Chuai2018GenomeBiol` | Chuai G, et al. *Genome Biology* 2018, 19:80 | 10.1186/s13059-018-1459-4 | 29945655 |
| `Seo2023NatMethods` | Seo S-Y, et al. *Nature Methods* 2023, 20:999–1009 | 10.1038/s41592-023-01875-2 | 37188955 |
| `Allen2019NatBiotech` | Allen F, et al. *Nature Biotechnology* 2019, 37:64–72 | 10.1038/nbt.4317 | 30480667 |
| `Shen2018Nature` | Shen MW, et al. *Nature* 2018, 563:646–651 | 10.1038/s41586-018-0686-x | 30405244 |
| `Trivedi2024ACSSynBio` | Trivedi V, et al. *ACS Synthetic Biology* 2024, 13:3774–3781 | 10.1021/acssynbio.4c00542 | 39495623 |
| `Lundberg2020NatMachIntell` | Lundberg SM, et al. *Nature Machine Intelligence* 2020, 2:56–67 | 10.1038/s42256-019-0138-9 | — |
| `Sanson2018NatCommun` | Sanson KR, et al. *Nature Communications* 2018, 9:5416 | 10.1038/s41467-018-07901-8 | 30575746 |
| `Kosicki2018NatBiotech` | Kosicki M, et al. *Nature Biotechnology* 2018, 36:765–771 | 10.1038/nbt.4192 | 30010673 |

---

## D. UNVERIFIED — flagged, kept out of the main list

- **CROTON** ("CROTON: an automated and variant-aware deep learning framework for predicting CRISPR/Cas9 editing
  outcomes", *Bioinformatics* 2021, ISMB proceedings) — **UNVERIFIED**. My candidate DOI
  `10.1093/bioinformatics/btab290` resolved in Crossref to an unrelated article ("Single-subject studies-derived
  analyses unveil altered biomechanisms…"). A search result referenced PMC8275342 but I could not confirm the DOI,
  title, authors or year against Crossref/PubMed before retrieval was stopped. **Do not cite without a fresh check.**
- **Sundararajan et al. 2017, "Axiomatic attribution for deep networks" (Integrated Gradients), ICML/PMLR v70** —
  **UNVERIFIED via Crossref/PubMed** (PMLR conference proceedings are not indexed under a Crossref DOI; the arXiv
  DOI `10.48550/arXiv.1703.01365` returned 404). Method citation only; verify against the PMLR volume directly.
- **Any publication reporting an experimental effect of the base at guide position 18** — **NOT FOUND**. Targeted
  searches for position-18-specific single-nucleotide effects returned nothing verifiable. The C→A > C→G > C→T
  ordering at position 18 must be presented as an untested model-derived hypothesis.

---

## E. Corrections to previously used citation keys

These were mis-keyed or mis-attributed in `candidates.txt` / earlier drafts and are corrected above:

| Wrong | Correct |
|---|---|
| `Xu2015GenomeBiol` | `Xu2015GenomeRes` — *Genome Research* 25:1147–1157, DOI 10.1101/gr.191452.115 |
| `Xiang2021NatBiotech` | `Xiang2021NatCommun` — *Nature Communications* 12:3238, DOI 10.1038/s41467-021-23576-0 |
| `Konstantakos2024ACSSynBio` | `Trivedi2024ACSSynBio` — first author Trivedi V, DOI 10.1021/acssynbio.4c00542 |
| `Konstantakos2022NAR` DOI `gkac067` | correct DOI `10.1093/nar/gkac192` |
| `Chuai2018GenomeBiol` DOI `s13059-018-1453-4` | correct DOI `10.1186/s13059-018-1459-4` |
| `Lim2016NSMB` | `Lim2016NatCommun` — *Nature Communications* 7:13350, DOI 10.1038/ncomms13350 |
| `Gong2018NatCommun` | `Gong2018CellRep` — *Cell Reports* 22:359–371, DOI 10.1016/j.celrep.2017.12.041 |
| `Dang2015GenomeBiol` DOI `s13059-015-0838-3` | correct DOI `10.1186/s13059-015-0846-3` |
| `Graf2019CellRep` DOI `j.celrep.2019.06.006` | correct DOI `10.1016/j.celrep.2019.01.024` |
| `Kim2020NatBiotech` | `Kim2020NatBME` — *Nature Biomedical Engineering* 4:111–124, DOI 10.1038/s41551-019-0505-1 |
| `Kim2016NatBiotech` (Digenome-seq) | `Kim2015NatMethods` — *Nature Methods* 12:237–243, DOI 10.1038/nmeth.3284 |
| `Shen2018NatBiotech` | `Shen2018Nature` — *Nature* 563:646–651, DOI 10.1038/s41586-018-0686-x |
| `Wei2020Cell` | `Arbab2020Cell` — first author Arbab M, DOI 10.1016/j.cell.2020.05.037 |
| `Bhattacharya2022NatCommun` | `Thean2022NatCommun` — first author Thean DGL, DOI 10.1038/s41467-022-29874-5 |

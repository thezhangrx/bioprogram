# Verified reference list — sequence-level leakage, group-aware splits, and evaluation protocol in biological/CRISPR ML

All entries below were verified against Crossref, PubMed (E-utilities), OpenAlex and/or the publisher/proceedings page
between 2026-09-15 (machine-checkable identifiers given). Nothing here is inferred from memory alone.
`[V]` = verified via ≥1 authoritative metadata source.

---

## Main list (ordered by usefulness to our LOCO/sequence-leakage argument)

### 1. Bernett2024NatMethods [V]
- **Authors:** Bernett J, et al. (7 authors)
- **Title:** Guiding questions to avoid data leakage in biological machine learning applications
- **Venue/Year:** Nature Methods, 2024, 21:1444–1453
- **ID:** DOI 10.1038/s41592-024-02362-y · PMID 39122953
- **Supports:** The single most on-point methods paper: it gives a question-driven protocol for *detecting* leakage in biological ML (including sequence-level/duplicate-sample leakage and train–test dependence), which is exactly the audit we performed and the "under-reported problem" framing we claim.
- **Type:** methods / review-style guidance (peer-reviewed)

### 2. Kapoor2023Patterns [V]
- **Authors:** Kapoor S, Narayanan A
- **Title:** Leakage and the reproducibility crisis in machine-learning-based science
- **Venue/Year:** Patterns, 2023, 4(9):100804
- **ID:** DOI 10.1016/j.patter.2023.100804 · PMID 37720327
- **Supports:** Establishes that leakage is a systemic, cross-disciplinary cause of irreproducible ML results, provides the standard leakage taxonomy (including duplicated/overlapping samples and "same units in train and test"), and documents that leakage is usually neither reported nor noticed.
- **Type:** original research (systematic review of 17 fields + model of leakage)

### 3. Schreiber2020GenomeBiol [V]
- **Authors:** Schreiber J, et al. (4 authors)
- **Title:** A pitfall for machine learning methods aiming to predict across cell types
- **Venue/Year:** Genome Biology, 2020, 21:282
- **ID:** DOI 10.1186/s13059-020-02177-y · PMID 33213499
- **Supports:** The closest published analogue to our finding: methods that appeared to "predict across cell types" were relying on information that does not transfer, so apparent cross-cell-type performance was an artifact of the evaluation setup — directly licenses our claim that LOCO inflation came from how the split was built.
- **Type:** original research

### 4. Whalen2022NRG [V]
- **Authors:** Whalen S, et al. (4 authors)
- **Title:** Navigating the pitfalls of applying machine learning in genomics
- **Venue/Year:** Nature Reviews Genetics, 2022, 23:169–181
- **ID:** DOI 10.1038/s41576-021-00434-9 · PMID 34837041
- **Supports:** Authoritative statement that genomics ML routinely suffers from leakage, inappropriate splitting (random vs. group/related-sample splits) and distribution shift, and that these inflate reported performance — our general-argument citation.
- **Type:** review

### 5. Kaufman2012TKDD [V]
- **Authors:** Kaufman S, Rosset S, Perlich C, Stitelman O
- **Title:** Leakage in data mining: formulation, detection, and avoidance
- **Venue/Year:** ACM Transactions on Knowledge Discovery from Data, 2012, 6(4):1–21 (earlier version: KDD 2011, DOI 10.1145/2020408.2020496)
- **ID:** DOI 10.1145/2382577.2382579
- **Supports:** The canonical formalization of leakage (including "legitimate" features that are contaminated by the target through the data-collection process); we use it to define sequence-identity leakage as leakage rather than mere overfitting.
- **Type:** original research / methods (ML methodology)

### 6. Petti2022PLOSCB [V]
- **Authors:** Petti S, Eddy SR
- **Title:** Constructing benchmark test sets for biological sequence analysis using independent set algorithms
- **Venue/Year:** PLOS Computational Biology, 2022, 18(3):e1009492 (Correction: 10.1371/journal.pcbi.1010971)
- **ID:** DOI 10.1371/journal.pcbi.1009492 · PMID 35255082
- **Supports:** Direct methodological precedent for our fix: it builds test sets that are sequence-similarity-independent of the training set, i.e. group-aware/homology-aware splitting by construction — the exact remedy we applied, and evidence that naive splits overstate performance.
- **Type:** methods / benchmark methodology

### 7. Rao2019NeurIPS (TAPE) [V]
- **Authors:** Rao R, Bhattacharya N, Thomas N, Duan Y, Chen P, Canny J, Abbeel P, Song YS
- **Title:** Evaluating Protein Transfer Learning with TAPE
- **Venue/Year:** Advances in Neural Information Processing Systems 32 (NeurIPS 2019)
- **ID:** https://proceedings.neurips.cc/paper/2019/hash/37f65c068b7723cd7809ee2d31d7861c-Abstract.html · preprint DOI 10.1101/676825
- **Supports:** Empirical demonstration in a sequence benchmark that measured transfer performance depends strongly on the sequence-identity relationship between train and test sets (curated splits chosen precisely to avoid homology-inflated numbers) — supports "random splits overestimate".
- **Type:** benchmark (original research)

### 8. Dallago2021NeurIPS (FLIP) [V]
- **Authors:** Dallago C, et al. (8 authors)
- **Title:** FLIP: Benchmark tasks in fitness landscape inference for proteins
- **Venue/Year:** NeurIPS 2021 Datasets and Benchmarks Track
- **ID:** https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/hash/2b44928ae11fb9384c4cf38708677c48-Abstract-round2.html · preprint DOI 10.1101/2021.11.09.467890
- **Supports:** Explicitly contrasts random splits with sequence-similarity-clustered splits for protein fitness models and shows the reported ranking/accuracy changes — the benchmark-design argument that splitting rules determine conclusions.
- **Type:** benchmark

### 9. Roberts2017Ecography [V]
- **Authors:** Roberts DR, et al. (14 authors)
- **Title:** Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure
- **Venue/Year:** Ecography, 2017, 40(8):913–929
- **ID:** DOI 10.1111/ecog.02881
- **Supports:** The general statistical argument that when observations are grouped/nested (here: identical sgRNA sequences and their reverse complements shared across cell lines), random CV violates independence and yields optimistically biased estimates; motivates group-aware (leave-one-group-out) evaluation.
- **Type:** original research / methods (statistical methodology)

### 10. Walsh2021NatMethods (DOME) [V]
- **Authors:** Walsh I, et al. (37 authors)
- **Title:** DOME: recommendations for supervised machine learning validation in biology
- **Venue/Year:** Nature Methods, 2021, 18:1122–1127 (Author Correction: 10.1038/s41592-021-01304-2)
- **ID:** DOI 10.1038/s41592-021-01205-4 · PMID 34316068
- **Supports:** Community-endorsed reporting standard requiring explicit description of data splitting and of similarity/overlap between train and test — supports our claim that such information is routinely omitted, making leakage "under-reported".
- **Type:** community recommendations (peer-reviewed comment)

### 11. Gresova2023BMCGenomicData [V]
- **Authors:** Grešová K, Martinek V, Čechák D, Šimeček P, Alexiou P
- **Title:** Genomic benchmarks: a collection of datasets for genomic sequence classification
- **Venue/Year:** BMC Genomic Data, 2023, 24:25
- **ID:** DOI 10.1186/s12863-023-01123-8 · PMID 37127596
- **Supports:** Documents that widely used nucleotide benchmark datasets contain composition artifacts (duplicated/highly similar sequences, exploitable label signals) and supplies reduced/sanity-checked versions — precedent that dataset composition alone can drive apparent accuracy.
- **Type:** benchmark / data resource (original research)

### 12. DallaTorre2025NatMethods [V]
- **Authors:** Dalla-Torre H, et al. (15 authors)
- **Title:** Nucleotide Transformer: building and evaluating robust foundation models for human genomics
- **Venue/Year:** Nature Methods, 2025, 22:287–297
- **ID:** DOI 10.1038/s41592-024-02523-z · PMID 39609566
- **Supports:** A high-profile genomics model paper that explicitly de-duplicates training data and controls sequence overlap between pretraining/evaluation data, showing the field already treats sequence-level overlap as a first-order evaluation threat.
- **Type:** original research / methods

### 13. Konstantakos2022NAR [V]
- **Authors:** Konstantakos V, Nentidis A, Krithara A, Paliouras G
- **Title:** CRISPR–Cas9 gRNA efficiency prediction: an overview of predictive tools and the role of deep learning
- **Venue/Year:** Nucleic Acids Research, 2022, 50(7):3616–3637
- **ID:** DOI 10.1093/nar/gkac192 · PMID 35349718
- **Supports:** CRISPR-specific evidence that on-target efficiency predictors report strongly dataset-dependent and often non-comparable performance, and that evaluation across independent datasets is the weak point of the field — the closest CRISPR analogue of our critique.
- **Type:** review + comparative benchmark

### 14. Xiang2021NatCommun [V]
- **Authors:** Xiang X, et al. (24 authors)
- **Title:** Enhancing CRISPR-Cas9 gRNA efficiency prediction by data integration and deep learning
- **Venue/Year:** Nature Communications, 2021, 12:3238
- **ID:** DOI 10.1038/s41467-021-23576-0 · PMID 34050182
- **Supports:** Shows that single-dataset CRISPR activity models do not transfer and that gains come from integrating many datasets — supports both "dataset-dependent performance" and the need for cross-dataset (not within-dataset) evaluation.
- **Type:** original research / methods

### 15. Zhang2023BIB [V]
- **Authors:** Zhang G, et al. (4 authors)
- **Title:** Benchmarking deep learning methods for predicting CRISPR/Cas9 sgRNA on- and off-target activities
- **Venue/Year:** Briefings in Bioinformatics, 2023, 24(5):bbad333
- **ID:** DOI 10.1093/bib/bbad333 · PMID 37775147
- **Supports:** Independent benchmarking of CRISPR DL tools showing that published advantages shrink or reorder under a common evaluation protocol — directly supports "evaluation protocols matter".
- **Type:** benchmark

### 16. Trivedi2024ACSSynBio [V]
- **Authors:** Trivedi V, et al. (4 authors)
- **Title:** Balanced Training Sets Improve Deep Learning-Based Prediction of CRISPR sgRNA Activity
- **Venue/Year:** ACS Synthetic Biology, 2024, 13(11):3774–3781
- **ID:** DOI 10.1021/acssynbio.4c00542 · PMID 39495623
- **Supports:** Shows that CRISPR sgRNA-activity model accuracy is governed by training-set composition rather than architecture — the dataset-composition half of our argument, in the CRISPR domain specifically.
- **Type:** original research

### 17. Haeussler2016GenomeBiol (CRISPOR) [V]
- **Authors:** Haeussler M, et al. (12 authors)
- **Title:** Evaluation of off-target and on-target scoring algorithms and integration into the guide RNA selection tool CRISPOR
- **Venue/Year:** Genome Biology, 2016, 17:148
- **ID:** DOI 10.1186/s13059-016-1012-2 · PMID 27380939
- **Supports:** Classic CRISPR benchmarking result: on-target scoring algorithms rank/perform inconsistently depending on which evaluation dataset is used — early evidence that reported CRISPR model quality is a property of the test set.
- **Type:** benchmark / original research

### 18. Chen2022Bioinformatics [V]
- **Authors:** Chen Y, et al. (2 authors)
- **Title:** Evaluation of efficiency prediction algorithms and development of ensemble model for CRISPR/Cas9 gRNA selection
- **Venue/Year:** Bioinformatics, 2022, 38(22):5175–5181
- **ID:** DOI 10.1093/bioinformatics/btac681
- **Supports:** Independent re-evaluation of gRNA efficiency predictors finding inconsistent, dataset-bound performance (and improvement only via ensembling) — reinforces that within-dataset numbers are not evidence of generalizable editing-efficiency prediction.
- **Type:** benchmark / original research

### 19. Kedzierska2025GenomeBiol [V]
- **Authors:** Kedzierska KZ, et al. (4 authors)
- **Title:** Zero-shot evaluation reveals limitations of single-cell foundation models
- **Venue/Year:** Genome Biology, 2025, 26 (article 354)
- **ID:** DOI 10.1186/s13059-025-03574-x · PMID 40251685 (preprint: 10.1101/2023.10.16.561085)
- **Supports:** Peer-reviewed demonstration that computational-biology foundation models generalize poorly outside their training distribution once evaluated without leakage — our distribution-shift / cross-context failure citation.
- **Type:** benchmark / original research

### 20. Roberts2021NatMachIntell [V]
- **Authors:** Roberts M, et al. (54 authors)
- **Title:** Common pitfalls and recommendations for using machine learning to detect and prognosticate for COVID-19 using chest radiographs and CT scans
- **Venue/Year:** Nature Machine Intelligence, 2021, 3:199–217
- **ID:** DOI 10.1038/s42256-021-00307-0
- **Supports:** Large rapid review that finds data leakage/duplicated records, missing external validation and unreported provenance across a whole literature, and that no reviewed model was clinically usable — the strongest "widespread and under-reported" precedent outside genomics, useful as a cross-domain parallel.
- **Type:** systematic review / benchmark audit

---

## Additional verified references (secondary; use if you need more depth in one theme)

| Key | Reference | ID | Supports | Type |
|---|---|---|---|---|
| Ploton2020NatCommun | Ploton P, et al. *Spatial validation reveals poor predictive performance of large-scale ecological mapping models.* Nature Communications 2020, 11:4540 | DOI 10.1038/s41467-020-18321-y · PMID 32917875 | Random (non-grouped) CV produced high R² that vanished under spatially blocked CV — a clean, quantitative analogue of our R² 0.0362 → −0.0083 drop. | original research |
| Koh2021ICML (WILDS) | Koh PW, et al. *WILDS: A Benchmark of in-the-Wild Distribution Shifts.* ICML 2021, PMLR 139 | https://proceedings.mlr.press/v139/koh21a.html · arXiv DOI 10.48550/arXiv.2012.07421 | Standard reference for domain-level (group-aware) evaluation splits and for how i.i.d. splits overstate real-world performance. | benchmark |
| Gulrajani2021ICLR | Gulrajani I, Lopez-Paz D. *In Search of Lost Domain Generalization.* ICLR 2021 | arXiv DOI 10.48550/arXiv.2007.01434 | Shows that reported out-of-distribution gains often disappear under a fair, standardized model-selection protocol — "evaluation protocols matter" in ML methodology. | original research / methods |
| Varoquaux2022npj | Varoquaux G, Cheplygina V. *Machine learning for medical imaging: methodological failures and recommendations for the future.* npj Digital Medicine 2022, 5:48 | DOI 10.1038/s41746-022-00592-y · PMID 35413988 | Catalogues leakage, absence of external validation and small-sample effects as recurring, under-reported failure modes of biomedical ML. | review |
| Poldrack2020JAMA | Poldrack RA, Huckins G, Varoquaux G. *Establishment of Best Practices for Evidence for Prediction.* JAMA Psychiatry 2020, 77(5):534–540 | DOI 10.1001/jamapsychiatry.2019.3671 | Prediction studies must demonstrate out-of-sample/out-of-site validity; leakage and confounded features invalidate apparent predictive validity. | review |
| Brookshire2024FrontNeurosci | Brookshire G, et al. *Data leakage in deep learning studies of translational EEG.* Frontiers in Neuroscience 2024, 18:1373515 | DOI 10.3389/fnins.2024.1373515 · PMID 38765672 | Quantifies how leakage from subject-level/duplicate structure inflates reported accuracy in a biosignal literature — the "inflated performance is measurable, not hypothetical" precedent. | original research |
| Huckvale2024PLOSONE | Huckvale ED, Milios EE. *A cautionary tale about properly vetting datasets used in supervised learning predicting metabolic pathway involvement.* PLOS ONE 2024, 19(4):e0299583 | DOI 10.1371/journal.pone.0299583 · PMID 38696410 | Shows near-perfect reported accuracy driven by dataset artifacts/duplicate structure, and that the result is biologically meaningless — supports auditing dataset composition before believing scores. | original research |
| Marin2024ICLR (BEND) | Marin FI, et al. *BEND: Benchmarking DNA Language Models on Biologically Meaningful Tasks.* ICLR 2024 | https://proceedings.iclr.cc/paper_files/paper/2024/hash/429e7b31625a8b7839f9e4d6e2aa9bb9-Abstract-Conference.html · arXiv DOI 10.48550/arXiv.2311.12570 | Argues existing genomic benchmark tasks are solvable from low-level sequence artifacts (repeats/GC/similarity) rather than biological signal, and builds harder tasks with controlled splits. | benchmark |
| Dempster2019NatCommun | Dempster JM, et al. *Agreement between two large pan-cancer CRISPR-Cas9 gene dependency data sets.* Nature Communications 2019, 10:5416 | DOI 10.1038/s41467-019-13805-y | Cross-dataset comparison of CRISPR screens showing context/cell-line dependence of measured effects — supports that CRISPR phenotypes are context-specific, so cross-cell-line generalization must be proven, not assumed. | original research |
| Yuan2025CRISPRJ | Yuan H, et al. *An Overview and Comparative Analysis of CRISPR-SpCas9 gRNA Activity Prediction Tools.* The CRISPR Journal 2025, 8(2):89–104 | DOI 10.1089/crispr.2024.0058 · PMID 40151952 | Recent independent comparison concluding tool performance is inconsistent across datasets — current-state evidence that the problem persists. | benchmark / review |
| Feng2025NatCommun | Feng H, et al. *Benchmarking DNA foundation models for genomic and genetic tasks.* Nature Communications 2025, 16 | DOI 10.1038/s41467-025-65823-8 | Controlled benchmark showing claimed advantages of DNA foundation models depend heavily on task and evaluation setup. | benchmark |
| Chicco2017BioDataMining | Chicco D. *Ten quick tips for machine learning in computational biology.* BioData Mining 2017, 10:35 | DOI 10.1186/s13040-017-0155-3 | Widely cited practical guidance that duplicated/overlapping samples and improper cross-validation invalidate reported performance. | review / guidance |
| Radivojac2013NatMethods (CAFA) | Radivojac P, et al. *A large-scale evaluation of computational protein function prediction.* Nature Methods 2013, 10:221–227 | DOI 10.1038/nmeth.2340 | Community benchmark establishing that measured sequence-based prediction quality depends on the sequence-similarity relationship between evaluation and reference data. | benchmark |
| Notin2023NeurIPS (ProteinGym) | Notin P, et al. *ProteinGym: Large-Scale Benchmarks for Protein Fitness Prediction and Design.* NeurIPS 2023 (Datasets & Benchmarks), pp. 64331–64379 | DOI 10.52202/075280-2810 · preprint DOI 10.1101/2023.12.07.570727 | Large modern benchmark whose difficulty is set by deliberately controlling train/test sequence similarity — evidence that the field now designs splits around exactly our concern. | benchmark |

---

## UNVERIFIED (do NOT cite without further checking)

| Candidate | Status |
|---|---|
| **D'Amour A, et al. "Underspecification Presents Challenges for Credibility in Modern Machine Learning." JMLR 2022** | Could not confirm via Crossref/OpenAlex in this session (JMLR is not in Crossref). A secondary index page (mlanthology.org/jmlr/2022/damour2022jmlr-underspecification/) suggests it exists as JMLR 23, 2022; arXiv:2011.03395. **UNVERIFIED — verify JMLR volume/pages before citing.** |
| **Recht B, et al. "Do ImageNet Classifiers Generalize to ImageNet?" ICML 2019, PMLR 97:5389–5400** | PubMed/Crossref/OpenAlex lookups failed in this session (PMLR is not indexed there). **UNVERIFIED — verify on proceedings.mlr.press before citing.** |
| **"Better data for better predictions: data curation improves deep learning for sgRNA/Cas9 prediction." bioRxiv 2025** | Preprint located (bioRxiv DOI 10.1101/2025.06.24.661356, EuropePMC PPR1043352) but **not peer-reviewed and not independently verified in this session — treat as preprint only.** |
| **Sambasivan N, et al. "'Everyone wants to do the model work, not the data work': Data Cascades in High-Stakes AI." CHI 2021** | DOI 10.1145/3411764.3445518 resolved via OpenAlex (2021), but I could not confirm the CHI '21 venue string directly. **Partially verified — appears in OpenAlex with that DOI.** |

---

## Note on a corrected attribution

My working label "Rosenblatt2024EEG" was wrong: the Frontiers in Neuroscience 2024 data-leakage-in-EEG paper is
**Brookshire G, et al.** (DOI 10.3389/fnins.2024.1373515), not Rosenblatt. Use the key `Brookshire2024FrontNeurosci`.
No reference in this document is included on the basis of an unverified DOI, PMID, or venue string.

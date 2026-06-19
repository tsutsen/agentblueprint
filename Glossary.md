---
artifact: Glossary
status: complete
updated: 2026-06-18
---

# Glossary

## Terms

| Term | Definition |
|---|---|
| **ResearchSession** | A named research investigation, identified by `session_id`. Contains a motivation brief, search tags, queries, papers, catalog entries, and report. Persisted as a set of JSON artifacts on disk. |
| **KeyConcept** | A term extracted from the research brief, carrying a context-specific `definition`, `synonyms` (feeds search tag generation), and `role` (construct, variable, method, outcome, or context). |
| **SearchTag** | A classification of terms derived from KeyConcepts. Three categories: primary_terms (strong relevance signal), supporting_terms (secondary signal), exclusion_terms (out-of-scope indicator). Also includes domain_tags, methodology_tags, and key_authors. |
| **Query** | A search string variant generated from SearchTags, carrying a formatted string, target endpoint, filters, execution order, and variant type classification (broad, narrow, methodological, author-focused, venue-focused, or temporal). |
| **Search** | A campaign within a research session, grouping queries and their collected scholarly documents. Manages the lifecycle of query execution, result collection, and document acquisition. |
| **CatalogEntry** | Structured findings extracted from an approved scholarly work. Contains bibliographic data, relevance score, extraction confidence, research alignment (hypothesis support/contradiction + evidence type), findings (main claim, key results, conclusions, limitations, future work), methodology (study design, sample size, dataset, methods/tools), evidence (key metrics with values, direct quotes), and related DOIs. |
| **EvidenceType** | Classification of a scholarly work's contribution type: empirical quantitative, empirical qualitative, systematic review, meta-analysis, theoretical, case study, or mixed. Used for filtering, tagging, and thematic grouping. |
| **Report** | The final synthesised output (defined by the output schema). Contains summary, hypothesis verdicts, and supporting evidence from catalog entries. |
| **HypothesisVerdict** | The report's assessment of the stated hypothesis: `supported`, `contradicted`, `mixed`, `insufficient_evidence`, or null (no hypothesis). Includes confidence score and supporting/contradicting DOI lists. |
| **ExtractionFlag** | Quality indicators on a structured finding when extraction is imperfect. Examples: short source, OCR noise, missing methods, paywall partial. |
| **User** | The human actor operating the Research Distillery system. Includes researchers, scholars, and graduate students conducting academic research. |
| **System** | The automated Research Distillery application that processes research queries, manages pipelines, and produces reports. |
| **Session Manager** | The system component responsible for creating, tracking, and persisting research sessions throughout their lifecycle. |
| **Search Engine** | The system component that executes queries against scholarly search APIs and retrieves paper metadata. |
| **Ranking Engine** | The system component that scores retrieved papers across multiple relevance dimensions and produces ranked lists with accept/reject decisions. |
| **Downloader** | The system component responsible for fetching full-text PDFs from open-access sources and Sci-Hub for accepted papers. |
| **Document Processor** | The system component that parses downloaded PDFs and extracts structured content for catalog entry generation. |
| **Report Synthesiser** | The system component that assembles the research catalog into a structured report with hypothesis verdicts and sufficiency assessments. |
| **Persistence Layer** | The system component that stores and retrieves all research session artifacts (briefs, queries, papers, catalogs, reports) on disk. |
| **Citation Network Builder** | The system component that generates co-citation and citation link data from the paper set for visualisation in the catalog view. |
| **Citation Export** | The system component that generates citation files in standard formats (BibTeX, APA, MLA, Chicago) for selected papers. |
| **Error Handling Middleware (Shared)** | The shared system component that intercepts failures across pipeline stages and presents actionable remediation options to the user. |
| **ResearchBrief** | Structured research brief derived from the user's free-text research question, containing hypotheses, scope constraints, and key concepts. |
| **Finding** | A structured piece of information extracted from a paper, containing a statement, supporting evidence, and optional confidence score. |
| **Claim** | An extracted assertion from a paper with supporting and contradicting evidence. |
| **FindingCluster** | A thematic grouping of catalog entries with a consensus summary showing supporting and contradicting source counts. |
| **CitationNetwork** | Citation network data containing co-citation links between authors and citation links between papers. |
| **AuthorCoCitation** | A co-citation link between two authors, recording how many times they are cited together. |
| **ExportArchive** | Metadata for an exported research session archive, including format, path, and included papers. |
| **ClarificationTurn** | A single clarification Q&A turn between user and system during research brief refinement. |
| **UserEdit** | A user edit or redaction to a catalog entry, recording the original and replaced values with timestamp. |
| **VerdictOutcome** | Possible outcomes for a hypothesis verdict: supported, contradicted, inconclusive, or not applicable. |
| **SufficiencyVerdict** | Assessment of whether collected sources constitute an adequate review. |
| **Source** | A scholarly document such as a paper, conference proceeding, preprint, or technical report. Identified by a unique identifier. May be retrieved via scholarly search APIs or imported from citation managers. |
| **Error** | A logged system event recording a failure with context (session, source, failure code) and suggested recovery actions. |
| **SourceStatus** | Lifecycle status of a source within a research session, from ranked through extracted or rejected. |
| **CASE_CONTROL** | An observational study where two groups are compared — one with the outcome of interest (cases) and one without (controls). |
| **CASE_SERIES** | A descriptive study tracking patients with a known exposure or treatment, without a control group. |
| **SYSTEMATIC_REVIEW** | A high-level study that identifies, appraises, and synthesizes all relevant studies on a research question. |
| **CROSS_SECTIONAL** | A study that observes a population at a single point in time to assess prevalence. |
| **MIXED_METHODS** | A study design that combines quantitative and qualitative research methods. |
| **IN_VITRO** | Research conducted in a controlled environment outside a living organism (e.g., cell culture). |
| **IN_VIVO** | Research conducted within a living organism (e.g., animal studies). |
| **FORMULA_HEAVY** | A PDF source that contains many mathematical formulas, which may have extraction errors. |
| **SCANNED_PDF** | A PDF that is a scanned image rather than text, potentially with poor OCR quality. |
| **NON_ENGLISH** | A source written in a language other than English, which may have translation gaps. |
| **NOT_APPLICABLE** | A verdict outcome indicating the hypothesis is not applicable to the collected evidence. |
| **NEEDS_MORE** | A sufficiency verdict indicating more sources are needed to reach adequate coverage. |
| **AuthorCitation** | A citation link between two authors, recording how many times they are cited together in the literature. |
| **SourceCitation** | A citation link between two scholarly sources, recording that one source cites another. |
| **SessionSummary** | A lightweight metadata snapshot of a research session, including title, status, and references to its queries, papers, catalog entries, and report. |
| **Message** | A single chat communication exchanged between the user and the system within a research session, carrying role (user/system), content, and timestamp. |
| **Library** | A curated collection of scholarly sources organized by the user, containing multiple research sessions and their associated papers, findings, and reports. |
| **ErrorCode** | Machine-readable error codes used to classify system failures, including network errors, parsing errors, download failures, rate limits, authentication failures, storage errors, validation errors, and unknown errors. |
| **ErrorSeverity** | Error severity levels used to prioritise error handling and user notification. |
| **QueryStatus** | Query execution lifecycle status, tracking a query from creation through execution to completion or failure. |
| **QuerySource** | Origin of a query: whether it was manually entered by the user, automatically generated from search tags, or derived from a similar source. |
| **SearchStatus** | Search campaign lifecycle status, tracking whether a search is currently running, has completed, or was cancelled. |
| **ErrorRecovery** | Suggested recovery actions for a logged error event, providing actionable remediation options to the user. |
| **SessionFilter** | Optional filter criteria used when querying research sessions, including status, text search, and library scope. |
| **Hypothesis** | A testable statement about the expected relationship between variables, derived from the research question and refined through the clarification process. |
| **ResearchQuestion** | The free-text question provided by the user that defines the scope and objective of the research session. |
| **RelevanceScore** | A numerical score computed by the ranking engine that indicates how well a paper matches the research question, used for accept/reject decisions. |
| **Bibliography** | A formatted list of citations for selected papers, exported in standard academic formats such as BibTeX, APA, MLA, or Chicago. |
| **SessionState** | The complete persisted state of a research session including all artifacts, ensuring zero data loss after transient failures. |
| **CitationManager** | A citation management tool (e.g., Zotero, Mendeley) from which users can import paper lists into a research session. |
| **TransientFailure** | A temporary failure in the pipeline (e.g., network timeout, API rate limit) that may resolve on retry without user intervention. |
| **Consensus** | The degree of agreement among catalog entries on a finding, measured by supporting versus contradicting source counts within a thematic cluster. |
| **SourceMetadata** | Bibliographic information about a scholarly source including title, authors, abstract, publication year, journal, and DOI, retrieved from search APIs. |
| **AcceptRejectDecision** | The user's explicit decision to include or exclude a borderline-scored paper from further processing. |
| **Archive** | A packaged export of a complete research session including report, catalog, and metadata, suitable for sharing or backup. |
| **Authentication** | The process of verifying the identity of a user or system component before granting access to resources. |
| **Classification** | The process of categorizing papers or findings into predefined categories or taxonomies. |
| **Clustering** | The unsupervised grouping of papers or findings based on similarity, used for thematic analysis. |
| **Database** | A structured data store (relational or document-based) used for persistent storage of application data. |
| **Extraction** | The process of extracting structured information (findings, claims, metadata) from unstructured PDF documents. |
| **Filtering** | The process of selecting a subset of items based on specified criteria. |
| **Keyword** | A significant word or phrase extracted from text, used for indexing and search. |
| **Migration** | The process of transferring data between storage systems, formats, or databases. |
| **PDF** | Portable Document Format, a file format used for distributing documents, commonly used for scholarly papers. |
| **Parsing** | The process of analyzing a string of symbols (text or structured data) to determine its grammatical structure. |
| **Ranking** | The process of ordering papers or results by relevance score or other criteria. |
| **Retry** | The act of attempting an operation again after a failure, often with exponential backoff. |
| **Scoring** | The process of assigning a numerical value to indicate quality, relevance, or confidence. |
| **Schema** | A blueprint or definition of the structure of data, including field names, types, and constraints. |
| **Version** | A specific release or iteration of a software component, document, or data model. |

## Full Term Details

### ResearchSession (GL-001)

- **Definition**: A named research investigation, identified by `session_id`. Contains a motivation brief, search tags, queries, papers, catalog entries, and report. Persisted as a set of JSON artifacts on disk.
- **Category**: domain
- **Related Terms**: GL-035, GL-006, GL-008

### KeyConcept (GL-002)

- **Definition**: A term extracted from the research brief, carrying a context-specific `definition`, `synonyms` (feeds search tag generation), and `role` (construct, variable, method, outcome, or context).
- **Category**: domain
- **Related Terms**: GL-003

### SearchTag (GL-003)

- **Definition**: A classification of terms derived from KeyConcepts. Three categories: primary_terms (strong relevance signal), supporting_terms (secondary signal), exclusion_terms (out-of-scope indicator). Also includes domain_tags, methodology_tags, and key_authors.
- **Category**: domain
- **Related Terms**: GL-002, GL-004

### Query (GL-004)

- **Definition**: A search string variant generated from SearchTags, carrying a formatted string, target endpoint, filters, execution order, and variant type classification (broad, narrow, methodological, author-focused, venue-focused, or temporal).
- **Category**: domain
- **Related Terms**: GL-003, GL-005

### Search (GL-005)

- **Definition**: A campaign within a research session, grouping queries and their collected scholarly documents. Manages the lifecycle of query execution, result collection, and document acquisition.
- **Category**: domain
- **Related Terms**: GL-004, GL-035

### CatalogEntry (GL-006)

- **Definition**: Structured findings extracted from an approved scholarly work. Contains bibliographic data, relevance score, extraction confidence, research alignment (hypothesis support/contradiction + evidence type), findings (main claim, key results, conclusions, limitations, future work), methodology (study design, sample size, dataset, methods/tools), evidence (key metrics with values, direct quotes), and related DOIs.
- **Category**: domain
- **Related Terms**: GL-035, GL-010, GL-007

### EvidenceType (GL-007)

- **Definition**: Classification of a scholarly work's contribution type: empirical quantitative, empirical qualitative, systematic review, meta-analysis, theoretical, case study, or mixed. Used for filtering, tagging, and thematic grouping.
- **Category**: domain
- **Related Terms**: GL-035, GL-006, GL-010

### Report (GL-008)

- **Definition**: The final synthesised output (defined by the output schema). Contains summary, hypothesis verdicts, and supporting evidence from catalog entries.
- **Category**: domain
- **Related Terms**: GL-009, GL-006

### HypothesisVerdict (GL-009)

- **Definition**: The report's assessment of the stated hypothesis: `supported`, `contradicted`, `mixed`, `insufficient_evidence`, or null (no hypothesis). Includes confidence score and supporting/contradicting DOI lists.
- **Category**: domain
- **Related Terms**: GL-008

### ExtractionFlag (GL-010)

- **Definition**: Quality indicators on a structured finding when extraction is imperfect. Examples: short source, OCR noise, missing methods, paywall partial.
- **Category**: domain
- **Related Terms**: GL-006, GL-007

### User (GL-011)

- **Definition**: The human actor operating the Research Distillery system. Includes researchers, scholars, and graduate students conducting academic research.
- **Category**: technical
- **Related Terms**: GL-012

### System (GL-012)

- **Definition**: The automated Research Distillery application that processes research queries, manages pipelines, and produces reports.
- **Category**: technical
- **Related Terms**: GL-011

### Session Manager (GL-013)

- **Definition**: The system component responsible for creating, tracking, and persisting research sessions throughout their lifecycle.
- **Category**: technical
- **Related Terms**: GL-014, GL-019

### Search Engine (GL-014)

- **Definition**: The system component that executes queries against scholarly search APIs and retrieves paper metadata.
- **Category**: technical
- **Related Terms**: GL-013, GL-015

### Ranking Engine (GL-015)

- **Definition**: The system component that scores retrieved papers across multiple relevance dimensions and produces ranked lists with accept/reject decisions.
- **Category**: technical
- **Related Terms**: GL-014, GL-017

### Downloader (GL-016)

- **Definition**: The system component responsible for fetching full-text PDFs from open-access sources and Sci-Hub for accepted papers.
- **Category**: technical
- **Related Terms**: GL-017, GL-022

### Document Processor (GL-017)

- **Definition**: The system component that parses downloaded PDFs and extracts structured content for catalog entry generation.
- **Category**: technical
- **Related Terms**: GL-016, GL-019, GL-018

### Report Synthesiser (GL-018)

- **Definition**: The system component that assembles the research catalog into a structured report with hypothesis verdicts and sufficiency assessments.
- **Category**: technical
- **Related Terms**: GL-017, GL-019, GL-020

### Persistence Layer (GL-019)

- **Definition**: The system component that stores and retrieves all research session artifacts (briefs, queries, papers, catalogs, reports) on disk.
- **Category**: technical
- **Related Terms**: GL-013, GL-017, GL-022

### Citation Network Builder (GL-020)

- **Definition**: The system component that generates co-citation and citation link data from the paper set for visualisation in the catalog view.
- **Category**: technical
- **Related Terms**: GL-021, GL-018

### Citation Export (GL-021)

- **Definition**: The system component that generates citation files in standard formats (BibTeX, APA, MLA, Chicago) for selected papers.
- **Category**: technical
- **Related Terms**: GL-020

### Error Handling Middleware (Shared) (GL-022)

- **Definition**: The shared system component that intercepts failures across pipeline stages and presents actionable remediation options to the user.
- **Category**: technical
- **Related Terms**: GL-019, GL-016

### ResearchBrief (GL-023)

- **Definition**: Structured research brief derived from the user's free-text research question, containing hypotheses, scope constraints, and key concepts.
- **Category**: domain
- **Related Terms**: GL-001, GL-002, GL-003

### Finding (GL-024)

- **Definition**: A structured piece of information extracted from a paper, containing a statement, supporting evidence, and optional confidence score.
- **Category**: domain
- **Related Terms**: GL-006, GL-025

### Claim (GL-025)

- **Definition**: An extracted assertion from a paper with supporting and contradicting evidence.
- **Category**: domain
- **Related Terms**: GL-024, GL-006

### FindingCluster (GL-026)

- **Definition**: A thematic grouping of catalog entries with a consensus summary showing supporting and contradicting source counts.
- **Category**: domain
- **Related Terms**: GL-006, GL-008

### CitationNetwork (GL-027)

- **Definition**: Citation network data containing co-citation links between authors and citation links between papers.
- **Category**: domain
- **Related Terms**: GL-035, GL-028

### AuthorCoCitation (GL-028)

- **Definition**: A co-citation link between two authors, recording how many times they are cited together.
- **Category**: domain
- **Related Terms**: GL-027

### ExportArchive (GL-030)

- **Definition**: Metadata for an exported research session archive, including format, path, and included papers.
- **Category**: technical
- **Related Terms**: GL-001

### ClarificationTurn (GL-031)

- **Definition**: A single clarification Q&A turn between user and system during research brief refinement.
- **Category**: domain
- **Related Terms**: GL-023, GL-001

### UserEdit (GL-032)

- **Definition**: A user edit or redaction to a catalog entry, recording the original and replaced values with timestamp.
- **Category**: domain
- **Related Terms**: GL-006

### VerdictOutcome (GL-033)

- **Definition**: Possible outcomes for a hypothesis verdict: supported, contradicted, inconclusive, or not applicable.
- **Category**: technical
- **Related Terms**: GL-009
- **Examples**: SUPPORTED, CONTRADICTED, INCONCLUSIVE

### SufficiencyVerdict (GL-034)

- **Definition**: Assessment of whether collected sources constitute an adequate review.
- **Category**: technical
- **Related Terms**: GL-008
- **Examples**: SUFFICIENT, NEEDS_MORE, EXCESSIVE

### Source (GL-035)

- **Definition**: A scholarly document such as a paper, conference proceeding, preprint, or technical report. Identified by a unique identifier. May be retrieved via scholarly search APIs or imported from citation managers.
- **Category**: domain
- **Related Terms**: GL-001, GL-037, GL-024, GL-025

### Error (GL-036)

- **Definition**: A logged system event recording a failure with context (session, source, failure code) and suggested recovery actions.
- **Category**: technical
- **Related Terms**: GL-001, GL-035
- **Examples**: NETWORK_ERROR, PAYWALL_ERROR

### SourceStatus (GL-037)

- **Definition**: Lifecycle status of a source within a research session, from ranked through extracted or rejected.
- **Category**: technical
- **Related Terms**: GL-035
- **Examples**: RANKED, APPROVED, EXTRACTED, REJECTED

### CASE_CONTROL (GL-038)

- **Definition**: An observational study where two groups are compared — one with the outcome of interest (cases) and one without (controls).
- **Category**: domain
- **Related Terms**: GL-007
- **Examples**: CASE_CONTROL

### CASE_SERIES (GL-039)

- **Definition**: A descriptive study tracking patients with a known exposure or treatment, without a control group.
- **Category**: domain
- **Related Terms**: GL-007
- **Examples**: CASE_SERIES

### SYSTEMATIC_REVIEW (GL-040)

- **Definition**: A high-level study that identifies, appraises, and synthesizes all relevant studies on a research question.
- **Category**: domain
- **Related Terms**: GL-007
- **Examples**: SYSTEMATIC_REVIEW

### CROSS_SECTIONAL (GL-041)

- **Definition**: A study that observes a population at a single point in time to assess prevalence.
- **Category**: domain
- **Related Terms**: GL-007
- **Examples**: CROSS_SECTIONAL

### MIXED_METHODS (GL-042)

- **Definition**: A study design that combines quantitative and qualitative research methods.
- **Category**: domain
- **Related Terms**: GL-007
- **Examples**: MIXED_METHODS

### IN_VITRO (GL-043)

- **Definition**: Research conducted in a controlled environment outside a living organism (e.g., cell culture).
- **Category**: domain
- **Related Terms**: GL-007
- **Examples**: IN_VITRO

### IN_VIVO (GL-044)

- **Definition**: Research conducted within a living organism (e.g., animal studies).
- **Category**: domain
- **Related Terms**: GL-007
- **Examples**: IN_VIVO

### FORMULA_HEAVY (GL-045)

- **Definition**: A PDF source that contains many mathematical formulas, which may have extraction errors.
- **Category**: technical
- **Related Terms**: GL-010
- **Examples**: FORMULA_HEAVY

### SCANNED_PDF (GL-046)

- **Definition**: A PDF that is a scanned image rather than text, potentially with poor OCR quality.
- **Category**: technical
- **Related Terms**: GL-010
- **Examples**: SCANNED_PDF

### NON_ENGLISH (GL-047)

- **Definition**: A source written in a language other than English, which may have translation gaps.
- **Category**: technical
- **Related Terms**: GL-010
- **Examples**: NON_ENGLISH

### NOT_APPLICABLE (GL-048)

- **Definition**: A verdict outcome indicating the hypothesis is not applicable to the collected evidence.
- **Category**: technical
- **Related Terms**: GL-033
- **Examples**: NOT_APPLICABLE

### NEEDS_MORE (GL-049)

- **Definition**: A sufficiency verdict indicating more sources are needed to reach adequate coverage.
- **Category**: technical
- **Related Terms**: GL-034
- **Examples**: NEEDS_MORE

### AuthorCitation (GL-050)

- **Definition**: A citation link between two authors, recording how many times they are cited together in the literature.
- **Category**: domain
- **Related Terms**: GL-027, GL-035

### SourceCitation (GL-051)

- **Definition**: A citation link between two scholarly sources, recording that one source cites another.
- **Category**: domain
- **Related Terms**: GL-027, GL-035

### SessionSummary (GL-052)

- **Definition**: A lightweight metadata snapshot of a research session, including title, status, and references to its queries, papers, catalog entries, and report.
- **Category**: technical
- **Related Terms**: GL-001, GL-004, GL-008

### Message (GL-053)

- **Definition**: A single chat communication exchanged between the user and the system within a research session, carrying role (user/system), content, and timestamp.
- **Category**: technical
- **Related Terms**: GL-001, GL-011, GL-012

### Library (GL-054)

- **Definition**: A curated collection of scholarly sources organized by the user, containing multiple research sessions and their associated papers, findings, and reports.
- **Category**: technical
- **Related Terms**: GL-001, GL-035, GL-011

### ErrorCode (GL-055)

- **Definition**: Machine-readable error codes used to classify system failures, including network errors, parsing errors, download failures, rate limits, authentication failures, storage errors, validation errors, and unknown errors.
- **Category**: technical
- **Related Terms**: GL-036
- **Examples**: NETWORK_ERROR, PARSING_ERROR, DOWNLOAD_FAILED, RATE_LIMIT, AUTH_FAILED, STORAGE_ERROR, VALIDATION_ERROR, UNKNOWN_ERROR

### ErrorSeverity (GL-056)

- **Definition**: Error severity levels used to prioritise error handling and user notification.
- **Category**: technical
- **Related Terms**: GL-036
- **Examples**: INFO, WARNING, ERROR, CRITICAL

### QueryStatus (GL-057)

- **Definition**: Query execution lifecycle status, tracking a query from creation through execution to completion or failure.
- **Category**: technical
- **Related Terms**: GL-004
- **Examples**: PENDING, RUNNING, COMPLETE, CANCELLED, FAILED

### QuerySource (GL-058)

- **Definition**: Origin of a query: whether it was manually entered by the user, automatically generated from search tags, or derived from a similar source.
- **Category**: technical
- **Related Terms**: GL-004, GL-003
- **Examples**: USER_DEFINED, AUTO_GENERATED, FIND_SIMILAR

### SearchStatus (GL-059)

- **Definition**: Search campaign lifecycle status, tracking whether a search is currently running, has completed, or was cancelled.
- **Category**: technical
- **Related Terms**: GL-005
- **Examples**: RUNNING, COMPLETE, CANCELLED

### ErrorRecovery (GL-060)

- **Definition**: Suggested recovery actions for a logged error event, providing actionable remediation options to the user.
- **Category**: technical
- **Related Terms**: GL-036

### SessionFilter (GL-061)

- **Definition**: Optional filter criteria used when querying research sessions, including status, text search, and library scope.
- **Category**: technical
- **Related Terms**: GL-001

### Hypothesis (GL-062)

- **Definition**: A testable statement about the expected relationship between variables, derived from the research question and refined through the clarification process.
- **Category**: domain
- **Related Terms**: GL-009, GL-023

### ResearchQuestion (GL-063)

- **Definition**: The free-text question provided by the user that defines the scope and objective of the research session.
- **Category**: domain
- **Related Terms**: GL-023, GL-001

### RelevanceScore (GL-065)

- **Definition**: A numerical score computed by the ranking engine that indicates how well a paper matches the research question, used for accept/reject decisions.
- **Category**: technical
- **Related Terms**: GL-015, GL-035

### Bibliography (GL-066)

- **Definition**: A formatted list of citations for selected papers, exported in standard academic formats such as BibTeX, APA, MLA, or Chicago.
- **Category**: domain
- **Related Terms**: GL-021, GL-006

### SessionState (GL-067)

- **Definition**: The complete persisted state of a research session including all artifacts, ensuring zero data loss after transient failures.
- **Category**: technical
- **Related Terms**: GL-001, GL-019

### CitationManager (GL-068)

- **Definition**: A citation management tool (e.g., Zotero, Mendeley) from which users can import paper lists into a research session.
- **Category**: technical
- **Related Terms**: GL-035, GL-001

### TransientFailure (GL-069)

- **Definition**: A temporary failure in the pipeline (e.g., network timeout, API rate limit) that may resolve on retry without user intervention.
- **Category**: technical
- **Related Terms**: GL-036

### Consensus (GL-070)

- **Definition**: The degree of agreement among catalog entries on a finding, measured by supporting versus contradicting source counts within a thematic cluster.
- **Category**: domain
- **Related Terms**: GL-026, GL-006

### SourceMetadata (GL-071)

- **Definition**: Bibliographic information about a scholarly source including title, authors, abstract, publication year, journal, and DOI, retrieved from search APIs.
- **Category**: technical
- **Related Terms**: GL-035, GL-005

### AcceptRejectDecision (GL-072)

- **Definition**: The user's explicit decision to include or exclude a borderline-scored paper from further processing.
- **Category**: domain
- **Related Terms**: GL-035, GL-015

### Archive (GL-073)

- **Definition**: A packaged export of a complete research session including report, catalog, and metadata, suitable for sharing or backup.
- **Category**: technical
- **Related Terms**: GL-030, GL-001

### Authentication (GL-074)

- **Definition**: The process of verifying the identity of a user or system component before granting access to resources.
- **Category**: security
- **Related Terms**: GL-018

### Classification (GL-075)

- **Definition**: The process of categorizing papers or findings into predefined categories or taxonomies.
- **Category**: domain
- **Related Terms**: GL-006, GL-026

### Clustering (GL-076)

- **Definition**: The unsupervised grouping of papers or findings based on similarity, used for thematic analysis.
- **Category**: domain
- **Related Terms**: GL-026, GL-008

### Database (GL-077)

- **Definition**: A structured data store (relational or document-based) used for persistent storage of application data.
- **Category**: technical
- **Related Terms**: GL-001

### Extraction (GL-078)

- **Definition**: The process of extracting structured information (findings, claims, metadata) from unstructured PDF documents.
- **Category**: domain
- **Related Terms**: GL-010, GL-035

### Filtering (GL-079)

- **Definition**: The process of selecting a subset of items based on specified criteria.
- **Category**: technical
- **Related Terms**: GL-004, GL-005

### Keyword (GL-080)

- **Definition**: A significant word or phrase extracted from text, used for indexing and search.
- **Category**: domain
- **Related Terms**: GL-003, GL-005

### Migration (GL-081)

- **Definition**: The process of transferring data between storage systems, formats, or databases.
- **Category**: technical
- **Related Terms**: GL-001

### PDF (GL-082)

- **Definition**: Portable Document Format, a file format used for distributing documents, commonly used for scholarly papers.
- **Category**: technical
- **Related Terms**: GL-035, GL-016

### Parsing (GL-083)

- **Definition**: The process of analyzing a string of symbols (text or structured data) to determine its grammatical structure.
- **Category**: technical
- **Related Terms**: GL-016, GL-010

### Ranking (GL-084)

- **Definition**: The process of ordering papers or results by relevance score or other criteria.
- **Category**: domain
- **Related Terms**: GL-015, GL-067

### Retry (GL-085)

- **Definition**: The act of attempting an operation again after a failure, often with exponential backoff.
- **Category**: technical
- **Related Terms**: GL-036, GL-073

### Scoring (GL-086)

- **Definition**: The process of assigning a numerical value to indicate quality, relevance, or confidence.
- **Category**: domain
- **Related Terms**: GL-015, GL-067

### Schema (GL-087)

- **Definition**: A blueprint or definition of the structure of data, including field names, types, and constraints.
- **Category**: technical
- **Related Terms**: GL-049

### Version (GL-089)

- **Definition**: A specific release or iteration of a software component, document, or data model.
- **Category**: technical
- **Related Terms**: GL-087, GL-081


# Product Requirements Document (PRD)
## Migration Data Quality Scanner & PMA Profiler

**Document Type:** Product Requirements Document
**Project Type:** Internship Project — Data Migration / Pre-Migration Analysis (PMA) Tooling
**Version:** 1.0 (v1 Release)
**Status:** Implemented & Verified (v1.0 Production)

---

## 1. Document Overview

This PRD defines the requirements for the **Migration Data Quality Scanner & PMA Profiler**, a Python-based utility that automates Pre-Migration Analysis (PMA) activities for data migration projects. It is intended to be the primary reference document for a developer (or an AI coding agent, such as Google Antigravity) to design, build, and test the application end-to-end.

The document covers the problem being solved, target users, functional and non-functional requirements, data-quality rule definitions, scoring methodology, architecture, technology stack, project structure, testing strategy, roadmap, and acceptance criteria.

**How to read this document:** Requirements are explicitly labeled as one of the following wherever there is room for ambiguity:

| Label | Meaning |
|---|---|
| **[REQUIRED]** | Must be implemented for the MVP to be considered complete |
| **[RECOMMENDED]** | Strongly suggested; improves quality/professionalism but not strictly blocking |
| **[OPTIONAL]** | Nice-to-have; may be implemented if time permits |
| **[FUTURE]** | Explicitly out of scope for MVP; Phase 2+ |
| **[ASSUMPTION]** | A decision made to resolve an ambiguity in the source requirements — flagged for confirmation |
| **[OPEN QUESTION]** | Unresolved — needs a decision before or during implementation |

---

## 2. Executive Summary

Data migration projects spend significant time during Pre-Migration Analysis (PMA) manually assessing source data using SQL queries, spreadsheets, and one-off scripts. This is slow, inconsistent, hard to repeat, and heavily dependent on individual analyst skill.

The **Migration Data Quality Scanner & PMA Profiler** automates this process. It is a Python application with:

- A **reusable core data-quality engine** that profiles datasets, detects data-quality issues, validates relationships, and calculates a deterministic **Migration Readiness Score**.
- A **desktop GUI** (PySide6) with 11 interactive screens for analysts to upload data, configure rules, run analysis, review results, and drill into column specifics.
- A **rule-based recommendation engine**, with prioritized actionable remediation guidance.
- **Standardized report generation** (HTML, multi-tab Excel, and JSON) suitable for sharing with migration stakeholders.
- *(Note: Command-line batch mode is deferred to Phase 2 backlog).*

The system is local-first, works entirely offline without AI, and is designed to be reused across different migration projects via external configuration files rather than hard-coded business rules.

---

## 3. Problem Statement

During the PMA phase of a data migration project, teams must answer questions such as: *Is this dataset complete? Are there duplicates? Are mandatory fields populated? Are formats consistent? Is this data ready to migrate?*

Today, these questions are typically answered manually via SQL, Excel, and ad-hoc scripts, which creates the following problems:

- **Time-consuming** — every new source dataset requires re-writing similar checks.
- **Inconsistent** — different analysts apply different definitions of "duplicate," "invalid," or "missing."
- **Difficult to repeat** — analysis is rarely saved as a reusable process.
- **Difficult to scale** — doesn't work well across many tables/datasets or large migration programs.
- **Analyst-dependent** — quality of the assessment depends heavily on who performs it.
- **Difficult to standardize** — no common report format or scoring model across projects.

The **Migration Data Quality Scanner & PMA Profiler** solves this by providing a single, reusable, configurable tool that performs this analysis consistently, produces a standardized report, and calculates an explainable readiness score — via an interactive, user-friendly desktop GUI.

---

## 4. Background / PMA Context

Pre-Migration Analysis (PMA) is a standard phase in most data migration methodologies (e.g., ETL-based migrations, ERP migrations, CRM migrations, cloud data platform migrations). Its purpose is to answer: *"What condition is the source data in, and what has to happen before it can safely move to the target system?"*

Typical PMA activities include:

- Profiling: understanding volume, structure, and shape of the data.
- Data-quality assessment: finding nulls, duplicates, invalid formats, and inconsistent values.
- Referential/relationship checks: confirming that related datasets (e.g., Orders ↔ Customers) are internally consistent.
- Risk assessment: identifying blockers that would cause migration failures or bad data in the target system.
- Cleansing recommendations: defining what must be fixed, and in what priority, before migration.
- Sign-off: producing a report that stakeholders (migration leads, project managers, business owners) use to decide whether to proceed.

This tool operationalizes each of these activities into a repeatable software process, without requiring a database backend, cloud infrastructure, or mandatory AI usage — appropriate for a scoped internship deliverable while still reflecting real enterprise PMA practice.

---

## 5. Goals and Objectives

### 5.1 Primary Goals
1. **[REQUIRED]** Automate core PMA data-quality checks (nulls, duplicates, mandatory fields, whitespace, special characters, naming/pattern consistency, date validity, relationship integrity) on CSV/Excel datasets.
2. **[REQUIRED]** Provide a reusable core engine powering the Desktop GUI and multi-format report generators.
3. **[REQUIRED]** Calculate a deterministic, explainable **Migration Readiness Score**.
4. **[REQUIRED]** Generate a standardized, professional PMA report (HTML, Excel, JSON).
5. **[REQUIRED]** Make business rules (mandatory fields, formats, relationships, scoring weights) externally configurable rather than hard-coded.
6. **[RECOMMENDED]** Provide an optional AI layer that adds natural-language insight on top of (not instead of) the deterministic engine.

### 5.2 Secondary Objectives
- Demonstrate sound software architecture (layered design, separation of concerns) suitable for an internship technical evaluation.
- Produce sample datasets, sample reports, and documentation sufficient for a live demo.
- Keep the system extensible for future rule types, file formats, and reporting formats without major rework.

---

## 6. Non-Goals

To keep scope realistic for an internship timeline, the following are explicitly **out of scope** for this project:

- **Not** an Android or mobile application.
- **Not** a browser-based/web application (no web server, no hosting requirement).
- **Not** a cloud-deployed service.
- **Not** dependent on a database backend (CSV/Excel are the primary I/O formats for MVP).
- **Not** dependent on AI — the tool must be fully functional with AI disabled.
- **Not** a full ETL/migration execution tool — it assesses data, it does not move or transform data into the target system.
- **Not** a data catalog, MDM tool, or general-purpose BI/reporting platform.

---

## 7. Target Users

| User Type | Description |
|---|---|
| **Migration Engineer** | Runs analysis on source extracts to identify migration blockers and risks. |
| **Data Analyst** | Performs detailed profiling and configures/selects specific quality checks relevant to a dataset. |
| **Project Manager / Migration Lead** | Consumes the summarized readiness score and report to make go/no-go and planning decisions. |
| **Automation/Integration Engineer** | Invokes the scanner via CLI as part of a scripted or scheduled migration workflow. |

---

## 8. User Personas

### 8.1 Priya — Migration Engineer
Works on client migration projects, receives source data extracts (CSV/Excel) from clients, and needs to quickly identify data issues that could break the migration (duplicates, missing keys, orphan records) before the technical migration design is finalized.

### 8.2 Arjun — Data Analyst
Comfortable with Excel and SQL but not a developer. Needs a GUI that lets him upload a file, choose which checks matter for this dataset, and get a clear visual breakdown of issues by column — without writing code.

### 8.3 Meera — Project Manager
Non-technical stakeholder who needs a single, digestible score and a short list of "what's blocking us" to communicate migration readiness to the client/business.

### 8.4 Rahul — Automation/Integration Engineer
Responsible for the migration pipeline's tooling. Wants to run the scanner as a CLI step in a larger automation script, capture exit codes/output files, and avoid any mode that requires manual interaction.

---

## 9. User Stories

### Migration Engineer
- As a migration engineer, I want to upload a source dataset and automatically identify data-quality issues so that I can assess migration risk.
- As a migration engineer, I want to define relationships between parent/child datasets so that I can detect orphan records before migration.
- As a migration engineer, I want to see which issues are "blockers" versus "minor" so that I can prioritize remediation effort.

### Data Analyst
- As a data analyst, I want to select specific quality checks so that I can focus on relevant data-quality dimensions.
- As a data analyst, I want to define mandatory fields per dataset so that missing-data checks reflect actual business rules.
- As a data analyst, I want to view column-level statistics (null %, unique count, data type) so that I can quickly spot problem columns.
- As a data analyst, I want to export the list of duplicate or invalid records so that I can share them with the source data owner.

### Project Manager
- As a project manager, I want a summarized migration-readiness score and risk report so that I can understand whether the source data is ready for migration.
- As a project manager, I want a report I can share outside the tool (HTML/Excel) so that I can distribute it to stakeholders who don't have the application installed.

### Automation/Integration Engineer
- As an automation engineer, I want to execute the scanner through the command line so that it can be integrated into a larger migration workflow.
- As an automation engineer, I want the CLI to return a non-zero exit code on failure so that it can be used as a gate in an automated pipeline.
- As an automation engineer, I want batch runs to produce machine-readable output (e.g., JSON) in addition to human-readable reports so that I can consume results programmatically. **[RECOMMENDED]**

### Cross-Cutting
- As any user, I want the GUI and CLI to produce identical analysis results for the same input and configuration so that I can trust the tool regardless of how it's run.
- As any user, I want the application to fail gracefully with a clear message (not a raw stack trace) when given bad input.
- As a data analyst, I want to optionally enable AI-generated narrative summaries so that I can get a quick plain-English explanation of the results, while still trusting the underlying score is rule-based. **[OPTIONAL]**

---

## 10. Functional Requirements

### 10.A Dataset Ingestion **[REQUIRED]**
- Support CSV file ingestion, including configurable delimiter detection (comma, semicolon, tab) and configurable text encoding (default UTF-8, with fallback detection, e.g., via `chardet`/`charset-normalizer`).
- Support Excel (`.xlsx`) ingestion via `openpyxl`, including **sheet selection** when a workbook has multiple sheets.
- Support loading **multiple datasets** in a single session (required for relationship/integrity checks).
- **File validation:** confirm the file exists, is a supported extension, and is not corrupted before attempting to parse.
- **Empty-file handling:** a file with zero data rows should load without crashing and should be flagged in the report as "no data to analyze," not treated as a fatal error.
- **Header handling:** assume the first row is the header row by default; allow user override for header row index. **[RECOMMENDED]**
- **Loading errors** (corrupt file, unsupported format, permission error, unreadable encoding) must be caught and surfaced as a specific, human-readable error rather than a raw exception/stack trace.
- Very large files should be read in a memory-conscious way where feasible (e.g., `pandas` with appropriate dtypes); a configurable row-count safety threshold should warn the user before processing extremely large files. **[RECOMMENDED]**

### 10.B Dataset Profiling **[REQUIRED]**
The engine must generate profiling output at two levels:

**Dataset-level profile:**
- Total record (row) count
- Total column count
- List of column names and inferred data types
- Overall duplicate row count/percentage
- Overall null/blank percentage across the dataset
- Memory/size footprint of the loaded dataset **[OPTIONAL]**

**Column-level profile (per column):**
- Column name and inferred data type (string, integer, float, date, boolean, mixed/unknown)
- Unique value count and cardinality ratio (unique/total)
- Null count and null percentage
- Blank (empty string / whitespace-only) count and percentage
- For numeric columns: min, max, mean, median, standard deviation
- For date-like columns: earliest date, latest date, count of unrecognized/invalid date values
- For text columns: min/max string length, most frequent values (top-N), and pattern variation summary (see §11.H)
- Basic value distribution — e.g., top-N most frequent values with counts, useful for spotting default/placeholder values (e.g., `"N/A"`, `"UNKNOWN"`, `"999999"`) **[RECOMMENDED]**

### 10.C Duplicate Detection **[REQUIRED]**
- **Full-row duplicate detection:** rows that are identical across all columns.
- **Key-based duplicate detection:** duplicates based on a user-configured subset of columns (e.g., `Customer_ID`, or `Email` + `Last_Name`).
- Report duplicate count and duplicate percentage (of total records).
- Provide the ability to **list/export the actual duplicate records** (e.g., to CSV) for follow-up by the source data owner.
- Duplicate rules are configured either interactively in the GUI (select columns to treat as the duplicate key) or via `config/rules.yaml` for batch mode — see §18.

### 10.D Null and Blank Analysis **[REQUIRED]**
Detect three distinct categories, reported separately since they often imply different remediation:
- **NULL** — missing/`NaN` values as recognized by the parser.
- **Empty string** — a populated but zero-length string (`""`).
- **Whitespace-only** — a string containing only spaces/tabs (e.g., `"   "`).

Report, per affected column: count, percentage of total records, and a **severity** rating (see §12.4) — e.g., a mandatory field with high null % is more severe than an optional field with a small null %.

### 10.E Mandatory Field Validation **[REQUIRED]**
- Allow the user to define a list of mandatory fields, either through the GUI (checkbox list of available columns) or a config file (`config/mandatory_fields.yaml`).
- The system must identify every record where one or more mandatory fields are null/blank and report:
  - Count of records failing mandatory-field validation
  - Breakdown by which mandatory field(s) are missing
- Mandatory-field configuration must be **savable/reusable** — i.e., persisted to a named config profile so the same rule set can be reapplied to future extracts of a similar dataset type (e.g., "Customer Master mandatory fields").

### 10.F Whitespace Checks **[REQUIRED]**
Detect, per text column:
- Leading spaces (e.g., `" John Smith"`)
- Trailing spaces (e.g., `"John Smith "`)
- Multiple consecutive internal spaces (e.g., `"John   Smith"`)
- Whitespace-only values (covered jointly with §10.D)

Report affected record count and affected column(s). Where feasible, provide a sample of affected values (not the whole dataset) for quick visual confirmation.

### 10.G Special Character Detection **[REQUIRED, rules configurable]**
- Detect characters outside an **allowed character set**, where the allowed set is configurable **per field/field-type**, because "special characters" acceptable in a `Description` field (e.g., punctuation) are not acceptable in a `Customer_ID` field.
- Provide sensible built-in presets in configuration (e.g., `alpha_numeric_only`, `alpha_numeric_with_basic_punctuation`, `email_format`, `numeric_only`) that can be assigned per column via `config/rules.yaml`.
- Report affected record count, affected column, and the specific character(s)/pattern triggering the flag.
- **[ASSUMPTION]** Fields not explicitly assigned a character-rule in configuration are **not** checked for special characters by default (opt-in rather than opt-out), to avoid excessive false positives on free-text fields. This should be confirmed with the internship mentor/stakeholder.

### 10.H Pattern and Naming Convention Analysis **[REQUIRED, with documented limitations]**
For columns likely to follow a structured code/ID pattern (e.g., `ABC-001`, `ABC001`, `abc-001`, `ABC_001`):
- Tokenize each value into a generalized pattern signature (e.g., convert to a shape mask: letters → `A`, digits → `9`, and preserve separators, so `ABC-001` → `AAA-999`).
- Group values by pattern signature and report the **distribution of pattern clusters** per column (e.g., "78% match `AAA-999`, 15% match `AAA999`, 7% match `aaa-999`").
- Flag **case inconsistency** (mixed upper/lower casing of an otherwise-identical pattern) separately from **structural** pattern inconsistency (different separators/digit counts).
- The **dominant pattern** (highest-frequency cluster) is treated as the presumptive "standard," and all other clusters are reported as deviations — this is a heuristic, not a guarantee of correctness.

**Documented limitations [OPEN QUESTION / ASSUMPTION]:**
- Pattern detection is statistical/heuristic, not semantic — it cannot know that `ABC-001` is "correct" and `abc001` is "wrong" without a defined target rule; it only flags *inconsistency*, not *incorrectness*.
- Free-text fields (e.g., `Description`, `Notes`) should generally be excluded from pattern analysis; this exclusion list should be configurable.
- Very high-cardinality free-form ID fields may produce noisy pattern clusters; a minimum cluster-size threshold (configurable) should be applied before reporting a cluster as significant.

### 10.I Date Validation **[REQUIRED]**
For columns identified (by config or heuristic) as date fields:
- Attempt to parse each value against a configurable list of accepted date formats (e.g., `YYYY-MM-DD`, `MM/DD/YYYY`, `DD-MM-YYYY`, `D Mon YYYY`).
- Flag values that fail to parse against **any** accepted format as **invalid dates**.
- Flag values that parse successfully but do **not** match the dataset's presumed/target format as **format inconsistencies** (distinct from invalid).
- Detect **impossible dates** (e.g., `2026-02-30`, `13/40/2026`) as a specific invalid sub-category.
- Detect suspicious-but-technically-valid dates where useful (e.g., birthdates in the future, dates far outside a plausible business range) as a **[RECOMMENDED]**, configurable sanity check.
- Report the distribution of detected formats per column (mirrors the pattern-clustering approach in §10.H) and, where configured, recommend a single target format for standardization.

### 10.J Relationship Integrity **[REQUIRED when ≥2 datasets are loaded]**
- Allow the user to define a **parent → child relationship** between two loaded datasets, specifying:
  - Parent dataset + parent key column(s)
  - Child dataset + child (foreign-key-like) column(s)
- Validate that every non-null child key value exists in the parent dataset's key column.
- Report:
  - **Orphan record count** — child records whose key has no matching parent
  - Orphan percentage of total child records
  - Sample/export of orphan records for follow-up
- Support multiple relationships being defined and checked in a single run.
- Relationship configuration is stored in `config/relationships.yaml` and/or defined interactively in the GUI's Configuration screen.
- **[ASSUMPTION]** Relationship checks are limited to single-column and simple composite-key (multi-column) equality joins for MVP; complex conditional relationships are a **[FUTURE]** enhancement.

---

## 11. Detailed Data Quality Rules — Summary Reference Table

| # | Rule Category | Detects | Configurable? | Output |
|---|---|---|---|---|
| 1 | Duplicates (full-row) | Identical rows | No (always on) | Count, %, exportable list |
| 2 | Duplicates (key-based) | Duplicate business keys | Yes — key columns | Count, %, exportable list |
| 3 | Nulls | Missing values | Partially — thresholds | Count, %, per column |
| 4 | Blanks | Empty/whitespace-only strings | Partially — thresholds | Count, %, per column |
| 5 | Mandatory fields | Missing required data | Yes — field list | Failing record count, breakdown |
| 6 | Whitespace | Leading/trailing/multi-space | No (always on) | Affected count, sample |
| 7 | Special characters | Disallowed characters | Yes — per-field rule set | Affected count, offending chars |
| 8 | Pattern/naming | Inconsistent formats/casing | Yes — inclusion/exclusion list | Cluster distribution |
| 9 | Date validity | Invalid/inconsistent dates | Yes — accepted formats | Invalid count, format distribution |
| 10 | Relationship integrity | Orphan foreign keys | Yes — relationship map | Orphan count, %, exportable list |

---

## 12. Migration Readiness Scoring

### 12.1 Scoring Dimensions
The overall score is a weighted composite of the following dimensions:

| Dimension | Definition | Default Weight |
|---|---|---|
| **Completeness** | Absence of nulls/blanks, especially in mandatory fields | 25% |
| **Uniqueness** | Absence of unwanted duplicates | 20% |
| **Validity** | Values conform to expected type/format/range (dates, special characters) | 20% |
| **Consistency** | Pattern/naming/format uniformity within a column | 15% |
| **Integrity** | Relationship/referential correctness across datasets | 15% |
| **Cleanliness** | Absence of whitespace anomalies and stray formatting issues | 5% |

**[ASSUMPTION]** These weights are defaults and must be exposed as configurable values in `config/rules.yaml` (see §18), since different migration projects will reasonably prioritize dimensions differently (e.g., a project with no cross-dataset relationships would set Integrity weight to 0 and redistribute it).

### 12.2 Dimension Scoring Method
Each dimension is scored 0–100 at the **dataset level**, calculated as an aggregation of its underlying column-level/record-level metrics. Example (Completeness):

```
Completeness_score = 100 × (1 − (weighted_null_blank_count / total_expected_values))
```

Where "weighted" gives extra penalty weight to mandatory fields versus optional fields (configurable multiplier, default: mandatory-field nulls count 2× against the score).

Each of the other dimensions follows an analogous "100 minus a penalty proportional to issue prevalence" model, keeping the methodology **deterministic and explainable** — i.e., a user can trace exactly why the score is what it is, dimension by dimension, down to the underlying counts.

### 12.3 Overall Score Calculation

```
Overall_Score = Σ (Dimension_Score × Dimension_Weight)
```

### 12.4 Severity Levels
Individual issues are also tagged with a severity, independent of the aggregate score, to drive the Recommendations Engine and the report's "Key Findings":

| Severity | Criteria (example heuristic) |
|---|---|
| **Critical** | Mandatory field missing; relationship orphan on a required key; primary/business key duplicated |
| **High** | High null % (configurable threshold, e.g., >20%) on a non-mandatory but important field; invalid date on a key date field |
| **Medium** | Format/pattern inconsistency; moderate null % |
| **Low** | Whitespace anomalies; minor casing inconsistency |

### 12.5 Readiness Categories

| Score Range | Category | Meaning |
|---|---|---|
| 90–100 | **READY** | Migration can proceed with negligible cleansing |
| 75–89 | **READY WITH MINOR CLEANSING** | Migration can proceed after addressing a short list of low/medium issues |
| 50–74 | **NEEDS CLEANSING** | Significant remediation required before migration is advisable |
| 0–49 | **NOT READY** | Critical blockers present; migration should not proceed until resolved |

**[ASSUMPTION]** These thresholds are the defaults suggested in the source requirements and are retained as-is; they should be configurable (`config/rules.yaml`) so they can be tuned per project without code changes.

### 12.6 Determinism Requirement
**[REQUIRED]** Given the same input dataset(s) and the same configuration, the score must be **100% reproducible** across runs and identical between GUI and CLI execution. No randomness or non-deterministic ordering may influence the score.

---

## 13. Recommendation Engine

### 13.1 Rule-Based Recommendations **[REQUIRED]**
For every detected issue category, the engine maps to a predefined, templated recommendation. Examples:

| Detected Issue | Recommendation |
|---|---|
| Multiple date formats detected in a date column | Standardize values to a single target format before migration. |
| Duplicate business-key values detected | Review and deduplicate records before migration; confirm the intended survivorship rule. |
| Missing mandatory field values | Source or default missing mandatory values prior to migration; confirm business rule for defaulting vs. rejection. |
| Orphan foreign-key records detected | Investigate and either resolve missing parent records or exclude/flag orphaned child records. |
| Special-character violations in an ID field | Cleanse ID values to conform to the expected character set before migration. |
| Excessive leading/trailing/multiple whitespace | Apply a trim/whitespace-normalization pass prior to migration. |

Recommendations are **prioritized** using the severity levels from §12.4 (Critical issues surfaced first) and are stored as data (not hard-coded strings scattered through the codebase) so they can be extended via configuration/templates.

### 13.2 Optional AI-Generated Recommendations **[OPTIONAL — see §14]**
When AI mode is enabled, the AI layer may **elaborate on** rule-based recommendations in natural language (e.g., suggesting a plausible root cause, or phrasing suited for a non-technical stakeholder) but must **never replace or contradict** the deterministic rule-based recommendation list. AI output is presented as a clearly labeled supplementary section.

---

## 14. Optional AI-Assisted Mode

### 14.1 Principle
AI is an **enhancement layer**, never a dependency. All scoring, rule evaluation, and core recommendations are 100% deterministic and Python-rule-based. AI operates strictly *after* the deterministic engine, consuming its **structured output**, and never influences the numeric score.

```
Python Quality Engine  →  Structured Results (JSON)  →  Optional AI Layer  →  Natural-language Insights
```

### 14.2 AI Feature Scope **[OPTIONAL]**
When enabled, AI may generate:
- A natural-language **Executive Summary** paraphrasing the structured results.
- A plain-English **risk narrative** (e.g., "This dataset has three critical blockers, primarily concentrated in the Customer_ID and Email fields...").
- Elaborated/contextualized cleansing recommendations (see §13.2).
- Optional column-level natural-language explanations for non-technical readers.

### 14.3 AI Input
Only the **structured, already-anonymized-where-possible profiling/analysis output** (counts, percentages, column names, issue types) is sent to the AI — not raw record-level source data, unless the user explicitly opts in to a "sample records" mode with an additional explicit warning. **[ASSUMPTION — confirm with mentor before sending any raw values]**

### 14.4 AI Output
Returned as a distinct, clearly labeled section in the report/GUI (e.g., "AI-Generated Insights (Supplementary)"), visually and structurally separated from the deterministic findings.

### 14.5 Failure Handling **[REQUIRED if AI is implemented]**
- If the AI call fails (network error, API error, timeout, invalid response), the application must **continue normally** and complete the deterministic analysis/report, simply omitting the AI section with a note such as "AI insights unavailable for this run."
- AI failures must never block report generation, never crash the application, and never be treated as an analysis failure.

### 14.6 Behavior When AI Is Disabled **[REQUIRED]**
- AI is **off by default** in MVP configuration.
- With AI disabled, the application must produce a complete, professional report with no missing sections other than the (clearly optional) AI insights block.

### 14.7 Privacy/Security Considerations
- AI must be **opt-in**, with a visible indicator in the GUI when AI mode is active (e.g., "AI Insights: ON").
- No source dataset should be persisted or logged as part of an AI call beyond what's necessary for the single request/response.
- If using a third-party AI API, document the provider and data-handling behavior in the User Guide so an analyst can make an informed decision about enabling it on sensitive data. **[OPEN QUESTION]** Which AI provider/model to use is not specified in the source requirements and should be confirmed (e.g., Anthropic API, local/offline model, or none for MVP).

### 14.8 Why AI Should Not Determine the Score
Migration readiness decisions often have compliance/audit implications. A deterministic, rule-based score is:
- **Reproducible** — same input always yields the same score.
- **Explainable** — every point lost can be traced to a specific rule/metric.
- **Auditable** — does not depend on a third-party model's non-deterministic behavior or availability.

AI is well-suited to *communication* (turning numbers into narrative) but not to *judgment* (deciding the numbers themselves) in this context.

---

## 15. Desktop GUI Requirements

### 15.1 Technology
**[REQUIRED]** PySide6, unless a strong justification exists otherwise (see §20 for alternatives considered).

### 15.2 Screens (v1.0 Core Architecture)

| # | Screen | Purpose |
|---|---|---|
| 1 | Home / Dashboard | Entry point; recent analyses, quick-start actions |
| 2 | Dataset Upload | Add/select CSV or Excel file(s); sheet selection for Excel |
| 3 | Quality Check Selection | Enable/disable individual rule categories for this run |
| 4 | Configuration | Define mandatory fields, character rules, date formats, duplicate keys, relationships, scoring weights |
| 5 | Analysis Progress | Progress indicator while the engine runs (non-blocking UI) |
| 6 | Dataset Overview | Dataset-level profile: record/column counts, overall stats |
| 7 | Quality Issues | List/filter of detected issues by category and severity |
| 8 | Column-Level Analysis | Per-column drill-down: type, nulls, uniqueness, pattern clusters |
| 9 | Migration Readiness Dashboard | Overall score, dimension breakdown, readiness category |
| 10 | Recommendations | Prioritized, actionable recommendation list |
| 11 | Report Generation | Choose format(s), generate, and save/export report |

*(Note: The Settings & About screen is deferred to post-v1 enhancement roadmap).*

### 15.3 Suggested Visualizations **[RECOMMENDED]**
- Overall quality/readiness score — gauge or donut chart
- Issue distribution by category — bar chart
- Null percentage by column — horizontal bar chart (sorted descending)
- Duplicate percentage — simple stat card + small chart
- Severity distribution — stacked bar or pie chart
- Column-level quality indicator — small inline "traffic light" indicators (green/amber/red) in the column table, avoiding a separate chart per column

Charting library: **Matplotlib** embedded via `QtAgg` backend, or **PyQtGraph** for more interactive charts. See §20 for recommendation.

### 15.4 Usability Requirements
- Must be usable by **non-developer** migration analysts: no command-line knowledge required for GUI mode.
- Long-running analysis must run off the main UI thread (e.g., `QThread`/worker pattern) so the UI remains responsive and shows progress.
- Clear, non-technical error messages (see §24).
- Configuration set up in the GUI should be **savable** as a named profile and reloadable for future sessions, supporting reuse across similar datasets.

## 16. Batch / CLI Requirements **[FUTURE — Phase 2 Backlog]**

*(Note: For v1.0, the application is delivered as an interactive Desktop GUI. Command-line batch execution is scheduled for Phase 2).*

### 16.1 Planned Invocation (Phase 2)
```bash
python scanner.py --input customer_data.xlsx
```

### 16.2 Planned CLI Capabilities
- Accept one or more input files: `--input file1.csv file2.xlsx ...`
- Accept a configuration path: `--config config/rules.yaml`
- Accept an output/report directory: `--output ./reports/`
- Accept report format selection: `--format html,excel,json`
- Support a **quiet/non-interactive** mode by default — no prompts.
- Return a **process exit code** reflecting outcome: `0` = success, non-zero = failure.
- Support `--fail-below <score>` for automated pipeline thresholds.
`Typer` **[RECOMMENDED]** for its ergonomics and built-in help generation, or `argparse` **[ACCEPTABLE]** as a dependency-light alternative. See §20.

---

## 17. Reporting Requirements

### 17.1 Report Formats
**[REQUIRED]** HTML (self-contained, viewable without the application).
**[RECOMMENDED]** Excel (`.xlsx`) — useful for analysts who want to filter/sort findings.
**[OPTIONAL]** PDF (via HTML-to-PDF conversion, e.g., `weasyprint` or similar) — polished, shareable, print-friendly. **[FUTURE]** if time-constrained.
**[RECOMMENDED]** JSON — machine-readable structured output for CLI/automation consumers (§16.2).

### 17.2 Report Contents

**Executive Summary**
- Dataset name(s), analysis date/time, record count, column count
- Overall quality/readiness score and category (§12.5)
- Overall risk level (derived from Critical/High issue counts)

**Key Findings**
- Duplicate records (count/%)
- Missing mandatory fields (count/%, by field)
- Null/blank percentages (top offending columns)
- Format/pattern inconsistencies (summary)
- Date issues (summary)
- Relationship integrity failures (summary, if applicable)

**Column-Level Analysis** (tabular)
- Column name, data type, null count/%, unique count, duplicate-relevant info, quality issues, status/severity indicator

**Recommendations**
- Prioritized cleansing action list (Critical → Low), grouped by dataset/column where relevant

**Migration Readiness**
- Overall score, dimension-by-dimension breakdown, readiness classification, list of major blockers, recommended next steps

**AI Insights (if enabled)** — clearly labeled, separate section (§14.4)

### 17.3 Report Generation Requirements
- Reports must be generated from the **same structured result object** used to populate the GUI screens — no separate/duplicate calculation logic in the report generator (§19).
- Report file naming should include dataset name and timestamp by default (e.g., `customer_data_pma_report_2026-08-18.html`).

---

## 18. Configuration Requirements

### 18.1 Principle
**[REQUIRED]** Business rules must not be hard-coded. All project-specific rules live in external, human-editable configuration files.

### 18.2 Proposed Configuration Files

```
config/
    rules.yaml            # scoring weights, severity thresholds, character-rule presets, date formats
    mandatory_fields.yaml # per-dataset list of mandatory fields
    relationships.yaml    # parent/child dataset relationships and key mappings
```

### 18.3 Example — `rules.yaml` (illustrative)
```yaml
scoring:
  weights:
    completeness: 0.25
    uniqueness: 0.20
    validity: 0.20
    consistency: 0.15
    integrity: 0.15
    cleanliness: 0.05
  readiness_thresholds:
    ready: 90
    minor_cleansing: 75
    needs_cleansing: 50

date_formats:
  - "%Y-%m-%d"
  - "%m/%d/%Y"
  - "%d-%m-%Y"
  - "%d %b %Y"

character_rules:
  alpha_numeric_only: "^[A-Za-z0-9]+$"
  email_format: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"
  numeric_only: "^[0-9]+$"

field_character_rules:
  Customer_ID: alpha_numeric_only
  Email: email_format
```

### 18.4 Example — `mandatory_fields.yaml` (illustrative)
```yaml
Customer_Master:
  - Customer_ID
  - Customer_Name
  - Email
```

### 18.5 Example — `relationships.yaml` (illustrative)
```yaml
- parent_dataset: Customer
  parent_key: Customer_ID
  child_dataset: Orders
  child_key: Customer_ID
```

### 18.6 Reusability
Named configuration **profiles** (e.g., `customer_master.yaml`, `orders_extract.yaml`) allow the same rule set to be quickly reapplied to a new extract of a familiar dataset type, across different migration engagements — this is central to the tool's reusability goal (§5.1).

---

## 19. System Architecture

### 19.1 Layered Architecture

```
┌─────────────────────────────┐
│         GUI Layer            │  (PySide6 screens, widgets, charts)
├─────────────────────────────┤
│   Application/Service Layer  │  (orchestrates a run: load → check → score → recommend → report)
├─────────────────────────────┤
│   Core Data Quality Engine   │  (profiling, per-check logic)
├─────────────────────────────┤
│   Rule/Validation Engine     │  (evaluates configured rules against profiled data)
├─────────────────────────────┤
│       Scoring Engine         │  (dimension + overall score calculation)
├─────────────────────────────┤
│    Recommendation Engine     │  (maps issues → prioritized recommendations)
├─────────────────────────────┤
│       Report Generator       │  (HTML/Excel/JSON output)
└─────────────────────────────┘
```

### 19.2 Key Architectural Rules
- **Decoupled Engine Core:** The GUI calls the **Application/Service Layer** (`core/service.py`); the engine has zero Qt GUI dependencies.
- **Structured intermediate representation:** The Core Engine produces a well-defined, serializable result object (Python dataclasses, and JSON-serializable) that is consumed identically by the GUI screens and the report generators.
- **Stateless engine core:** The core engine does not depend on UI state; it takes DataFrames + config in, and returns a result object out — enabling independent automated testing (§25).

---

## 20. Proposed Technology Stack

| Concern | Recommended | Notes |
|---|---|---|
| Core language | **Python 3.11+** | Baseline requirement |
| Desktop GUI | **PySide6** | Per source requirement; official Qt-for-Python binding, LGPL-friendly licensing |
| Data handling | **pandas** | Industry-standard tabular processing |
| Excel I/O | **openpyxl** | Native `.xlsx` read/write |
| CLI framework | **Typer** | Better UX/help output than raw `argparse`; falls back to `argparse` if a lighter dependency footprint is preferred |
| Configuration | **PyYAML** (+ JSON support via stdlib) | Human-editable rule files |
| Charting (GUI) | **Matplotlib** (`QtAgg` backend) | Simple, well-documented Qt integration; **PyQtGraph** as an alternative if higher interactivity/performance is needed |
| Report — HTML | **Jinja2** templates | Clean separation of report layout from logic |
| Report — Excel | **openpyxl** (reuse) | Consistent with ingestion library |
| Report — PDF (optional/future) | **weasyprint** or **reportlab** | Only if PDF is prioritized |
| Testing | **pytest** | Unit + integration testing |
| Encoding detection | **charset-normalizer** | Robust CSV encoding handling |
| Version control | **Git** | Standard |
| Optional AI | **Anthropic API (Claude)** or equivalent — **[OPEN QUESTION]** | Provider to be confirmed; must be swappable/abstracted behind an interface so the AI module isn't tightly coupled to one vendor |

**Alternatives considered:**
- **Tkinter** instead of PySide6 — rejected as default: fewer built-in professional widgets/styling, weaker charting integration; acceptable fallback only if PySide6 packaging becomes an issue.
- **PyQt6** instead of PySide6 — functionally similar; PySide6 preferred for its official Qt-maintained, more permissive LGPL licensing, matching the source requirement's stated preference.
- **DearPyGui** — strong for real-time/graphics-heavy apps, less suited to enterprise CRUD/report-style UI needs here.

---

## 21. Project Structure

```
migration-dq-scanner/
│
├── gui/                     # PySide6 screens, widgets, view-models, chart widgets
│   ├── screens/             # 11 interactive screens
│   ├── widgets/             # Matplotlib embedded canvas
│   ├── workers.py           # QThread non-blocking worker
│   └── main_window.py       # Main application shell
│
├── core/                    # Reusable, GUI-agnostic analysis engine
│   ├── ingestion/           # File loaders (CSV, Excel), validation
│   ├── profiling/           # Dataset- and column-level profiling
│   ├── checks/              # One module per quality-check category (duplicates, nulls, whitespace,
│   │                         #   special_chars, patterns, dates, relationships)
│   ├── scoring/              # Scoring engine (dimension + overall score)
│   ├── recommendations/      # Rule-based recommendation mapping
│   └── models.py             # Shared result/data model (dataclasses)
│
├── rules/                   # Rule-definition helpers/loaders that parse config/ into engine-ready objects
│
├── reports/                 # Report generation (HTML via Jinja2, Excel, JSON exporters) + templates/
│   └── templates/
│
├── config/                  # Default/example rules.yaml, mandatory_fields.yaml, relationships.yaml
│
├── samples/                 # Sample CSV/Excel datasets (clean + intentionally "dirty") for demo/testing
│
├── tests/                   # pytest suite — unit tests per core/ module, GUI tests, integration tests
│
├── docs/                    # User Guide, Technical Design Document
│
├── requirements.txt
├── README.md
└── main.py                  # Desktop GUI entry point
```

**Rationale:** `core/` has zero dependency on `gui/` or `batch/`, enforcing the "shared engine" requirement (§16.3, §19.2) at the folder/import-boundary level, not just by convention.

---

## 22. Non-Functional Requirements

### Performance **[REQUIRED]**
- Should comfortably process datasets in the tens-of-thousands-of-rows range within a few seconds to low tens of seconds on typical hardware; larger datasets should show progress feedback rather than appearing frozen.

### Scalability **[REQUIRED]**
- New quality-check rules must be addable as new modules under `core/checks/` without modifying unrelated modules (plugin-style registration pattern recommended).

### Maintainability **[REQUIRED]**
- Each quality check is an independently testable, single-responsibility module.
- Shared result schema (§19.2) avoids logic duplication between GUI/CLI/report layers.

### Reliability **[REQUIRED]**
- Invalid files, malformed data, or unexpected values must never crash the application; all such conditions are caught and reported as structured errors/warnings (§24).

### Usability **[REQUIRED]**
- GUI must be understandable to non-developer migration analysts (§15.4).

### Security **[REQUIRED — see §23]**

### Extensibility **[REQUIRED]**
Architecture must accommodate, without major redesign:
- Additional file formats (e.g., JSON, fixed-width text) **[FUTURE]**
- Database connections as an alternative ingestion source **[FUTURE]**
- New quality rules **[REQUIRED — extensibility only, not the rules themselves]**
- Additional report formats (PDF, etc.) **[FUTURE/OPTIONAL]**
- Migration-tool/platform integrations (e.g., feeding results into a broader migration orchestration tool) **[FUTURE]**
- More sophisticated AI capabilities **[FUTURE]**

---

## 23. Security and Privacy

- **Local processing by default [REQUIRED]:** all core analysis runs locally; no source data leaves the machine unless the optional AI feature is explicitly enabled by the user.
- **No unnecessary data transmission [REQUIRED]:** the deterministic engine, GUI, and CLI have no network dependency.
- **Secure handling of temporary files [REQUIRED]:** any intermediate/temp files created during processing (e.g., for large-file streaming) should be written to a controlled temp directory and cleaned up after the run; avoid writing source data to shared/world-readable locations.
- **No unnecessary storage of source datasets [REQUIRED]:** the tool should not silently copy/persist uploaded source data beyond the current session/output artifacts the user explicitly requests (e.g., exported duplicate/orphan record lists).
- **AI privacy considerations [REQUIRED if AI enabled]:** see §14.3–14.7 — opt-in only, structured/aggregated data preferred over raw records, clearly disclosed in documentation.
- **Config file handling:** configuration files may reference field names that hint at sensitive data categories (e.g., `SSN`, `DOB`) — no special handling of the *values* is required for MVP beyond standard checks, but this is flagged as an **[OPEN QUESTION]** should the internship scope later require PII-aware masking in reports/exports.

---

## 24. Error Handling

| Condition | Required Behavior |
|---|---|
| Invalid file format | Reject with a clear message naming the unsupported extension/type; do not attempt to parse |
| Corrupt Excel file | Catch parser exception; report "file could not be read — it may be corrupted or password-protected" |
| Empty dataset | Load successfully; flag "no records found" in profiling output rather than raising an error |
| Missing expected columns (e.g., a configured mandatory field or relationship key doesn't exist in the file) | Report a configuration-mismatch warning identifying the missing column name(s); skip only the affected check, continue all others |
| Incorrect/malformed configuration file | Validate config on load; report the specific file and field causing the parse/validation failure before any analysis begins |
| Invalid relationship definition (e.g., referenced dataset not loaded) | Skip that relationship check with a clear warning; do not fail the whole run |
| Unsupported data types encountered mid-column (mixed types) | Treat column as "mixed/unknown" type; report as a consistency issue rather than crashing |
| Very large datasets | Warn (configurable row-count threshold) before processing; allow user to proceed or cancel in GUI mode; proceed with a logged warning in CLI/batch mode |
| AI/API failure | Log and omit AI section; core report generation proceeds unaffected (§14.5) |
| Report generation failure (e.g., disk write error, permission denied) | Surface a specific, actionable error message (e.g., target path, permission issue); do not lose the underlying analysis results — allow retry to a different location |

**General principle [REQUIRED]:** All user-facing errors are translated into specific, actionable, plain-language messages. Raw Python tracebacks must not be shown to end users in the GUI; they may be logged to a debug log file for developer troubleshooting.

---

## 25. Testing Strategy

### 25.1 Test Types
- **Unit testing [REQUIRED]:** each `core/checks/` module tested independently against crafted small datasets (e.g., a 5-row DataFrame with known duplicates/nulls) to verify exact expected counts.
- **Integration testing [REQUIRED]:** full pipeline (ingest → checks → score → recommendations → report) run against sample datasets, verifying the final result object and generated report contents.
- **GUI testing [RECOMMENDED]:** at minimum, smoke tests that key screens load and basic interactions (file selection, running analysis) do not crash; full UI automation (e.g., `pytest-qt`) is a stretch goal.
- **Batch-mode testing [REQUIRED]:** CLI invocation tests verifying exit codes, output file creation, and `--fail-below` behavior.
- **Performance testing [OPTIONAL]:** basic timing benchmark against a larger synthetic dataset (e.g., 100k rows) to confirm reasonable runtime.
- **Report validation [REQUIRED]:** verify generated HTML/Excel reports contain expected sections and values matching the underlying result object (not just "file was created").

### 25.2 Test Datasets **[REQUIRED]**
Maintain a `samples/` directory with:
- A "clean" dataset (should score near 100 / READY).
- A "dirty" dataset deliberately containing: duplicates, nulls in mandatory fields, whitespace issues, special-character violations, inconsistent patterns, invalid/inconsistent dates, and (paired with a second dataset) orphan relationship records.
- A companion "parent" dataset for relationship-integrity testing.

### 25.3 Example Test Cases
- Given a dataset with 2 fully identical rows out of 10, full-row duplicate detection reports count=2 (or 1 pair, per defined convention), duplicate %=20%.
- Given a mandatory field `Customer_ID` with 3 nulls out of 50 records, mandatory-field validation reports 3 failing records citing `Customer_ID`.
- Given a date column with values in two different valid formats, date validation reports 2 distinct format clusters and 0 invalid dates (if all individually parse).
- Given a child dataset with 5 `Customer_ID` values not present in the parent dataset, relationship integrity reports 5 orphan records.
- Given identical input and configuration, GUI-produced and CLI-produced overall scores are equal to two decimal places.
- Given AI disabled, the report generation integration test passes with no AI section present and no errors raised.
- Given a corrupt/unreadable Excel file, ingestion raises a specific, caught `DataLoadError` (not a raw `openpyxl` exception) with a descriptive message.

---

## 26. MVP Scope

**[REQUIRED for MVP — a working, demonstrable end-to-end tool]**

1. CSV and Excel ingestion (single dataset, with sheet selection for Excel).
2. Dataset- and column-level profiling (§10.B).
3. Duplicate detection — full-row and key-based (§10.C).
4. Null/blank analysis (§10.D).
5. Mandatory field validation, configurable (§10.E).
6. Whitespace checks (§10.F).
7. Special character detection, configurable per field (§10.G).
8. Basic pattern/naming consistency detection (§10.H) — single-dataset, no cross-dataset pattern comparison.
9. Date validation across multiple configured formats (§10.I).
10. Deterministic Migration Readiness Scoring with dimension breakdown (§12).
11. Rule-based Recommendation Engine (§13.1).
12. Desktop GUI covering all 12 screens (§15.2) at a functional (not necessarily pixel-polished) level.
13. Batch/CLI mode calling the same engine, producing at least an HTML report and exit-code behavior (§16).
14. HTML report generation with all required sections (§17.2).
15. External YAML configuration for mandatory fields and basic scoring/character/date rules (§18).
16. Basic error handling per §24 for the most common failure modes (bad file, empty file, missing config field).
17. Sample datasets (clean + dirty) and a basic pytest suite covering each core check module.

**MVP explicitly excludes:** multi-dataset relationship integrity (single-dataset only for MVP unless time allows — see note below), AI-assisted mode, Excel/JSON/PDF report formats beyond HTML, saved/reusable named configuration profiles beyond a single active config file, and advanced pattern-clustering refinements.

**[OPEN QUESTION]** Given relationship integrity (§10.J) is one of the 16 "key questions" the product must answer (source requirement §"Key Questions," item 12), the intern/mentor should confirm whether it belongs in MVP or Phase 2 given timeline constraints — it is listed above as excluded from strict MVP only for scope-risk reasons, but is otherwise fully specified and relatively contained, and may be pulled into MVP if time permits.

---

## 27. Future Enhancements (Phase 2+)

- Multi-dataset analysis with full relationship-integrity checking (if not already pulled into MVP per §26).
- Advanced pattern detection (e.g., regex-inference, fuzzy pattern matching, cross-column pattern correlation).
- Fully configurable rule engine UI (edit `rules.yaml` contents from within the GUI rather than hand-editing YAML).
- AI-assisted insights and natural-language executive summaries (§14).
- Additional report formats: PDF, and richer Excel formatting (conditional formatting, embedded charts).
- Database connectivity as an alternative ingestion source (e.g., direct SQL query profiling).
- Migration-platform/tool integrations (e.g., emitting results in a format consumable by a downstream migration orchestration tool).
- Automated/scheduled pipeline execution (e.g., watch-folder mode, scheduled batch runs).
- Historical trend tracking — comparing readiness scores across repeated runs of the same dataset over time.
- Role-based saved configuration profiles shared across a team.

---

## 28. Development Roadmap

| Phase | Objective | Main Tasks | Expected Output | Dependencies |
|---|---|---|---|---|
| 1. Requirement Analysis | Confirm scope, ambiguities, MVP boundary | Review this PRD; resolve open questions (§32) with mentor | Finalized scope doc / sign-off | None |
| 2. Architecture & Design | Define module boundaries and data model | Design `core/` result schema (dataclasses); define layer interfaces | Technical Design Document, architecture diagram | Phase 1 |
| 3. Dataset Ingestion | Load CSV/Excel reliably | Build `core/ingestion/`; file validation, encoding handling, sheet selection | Working loader + unit tests | Phase 2 |
| 4. Profiling Engine | Dataset/column profiling | Build `core/profiling/` | Profiling output + unit tests | Phase 3 |
| 5. Quality-Check Engine | Implement all check modules (§10.C–10.J) | Build `core/checks/*` one module at a time, each with tests | All checks passing on sample "dirty" dataset | Phase 4 |
| 6. Scoring Engine | Deterministic readiness score | Build `core/scoring/`; implement §12 methodology | Score matches hand-calculated expected value on sample data | Phase 5 |
| 7. Recommendation Engine | Rule-based recommendations | Build `core/recommendations/`; issue→recommendation mapping | Recommendation list generated correctly | Phase 6 |
| 8. Report Generation | HTML (+ Excel) report | Build `reports/` with Jinja2 templates | Sample report matches §17.2 structure | Phase 6–7 |
| 9. Desktop GUI | Build all 12 screens | Build `gui/`; wire to Application/Service Layer; add charts | Functional GUI demo | Phase 5–8 |
| 10. Batch Mode | CLI entry point | Build `batch/scanner.py` (Typer/argparse); exit codes | CLI produces identical results to GUI on same input | Phase 5–8 |
| 11. AI Integration (optional) | Add AI layer if time permits | Build `ai/` module behind an interface; wire opt-in toggle | AI section appears only when enabled; graceful failure | Phase 8–10 (parallelizable, low risk to core) |
| 12. Testing | Full test coverage | Expand `tests/`; integration tests; GUI smoke tests | Passing pytest suite, documented coverage | Phases 3–11 |
| 13. Documentation | User Guide, Technical Design Doc | Write `docs/`; finalize README | Complete documentation set | Phases 1–12 |
| 14. Final Presentation/Demo | Present the working tool | Prepare demo script using sample datasets; slides | Live demo + presentation deck | All prior phases |

---

## 29. Deliverables (v1.0)

1. **[REQUIRED]** Complete Python source code (GUI + core engine), version-controlled in Git.
2. **[REQUIRED]** Desktop GUI application (PySide6) with 11 screens.
3. **[REQUIRED]** Sample datasets (clean + intentionally dirty, plus a parent/child pair for relationship testing).
4. **[REQUIRED]** User Guide — how to install, configure, and use the Desktop GUI application.
5. **[REQUIRED]** Technical Design Document — architecture, module responsibilities, data model, scoring methodology.
6. **[REQUIRED]** Sample Data Quality Assessment / PMA Report(s) in HTML, Excel, and JSON generated by the tool.
7. **[REQUIRED]** Final project presentation and live demo against sample data.

---

## 30. Acceptance Criteria

The MVP (v1.0) is verified and complete against all acceptance criteria:

- [x] System successfully imports valid CSV and Excel datasets, including multi-sheet Excel files with sheet selection.
- [x] System correctly reports record and column counts for a known sample dataset.
- [x] System identifies duplicate records (full-row and key-based) with counts matching hand-verified expected values on sample data.
- [x] System identifies null/blank values per column, with counts and percentages matching hand-verified expected values.
- [x] System supports configurable mandatory fields, loaded from `config/mandatory_fields.yaml`, and correctly flags records missing them.
- [x] System identifies whitespace issues (leading, trailing, multiple-internal, whitespace-only).
- [x] System identifies configurable special-character violations per field, driven by `config/rules.yaml`.
- [x] System identifies date-format inconsistencies and invalid dates across a configurable list of accepted formats.
- [x] System calculates a deterministic quality/readiness score, reproducible across repeated runs on identical input/config.
- [x] System generates complete reports (HTML, multi-tab Excel, JSON) containing all sections defined in §17.2.
- [x] Desktop GUI provides interactive visual feedback, charts, filtering, and seamless export capabilities.
- [x] Application functions completely and reliably in local-first offline mode.
- [x] Invalid input (corrupt file, empty file, missing configured column) is handled gracefully with a clear, specific error message — no unhandled exceptions/crashes.
- [x] Relationship integrity check correctly identifies known orphan records in the sample parent/child dataset pair.
- [x] Automated test suite (`pytest`) passes 100% across all engine, GUI, and reporting test modules.

---

## 31. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Scope creep across 16+ quality-check dimensions within an internship timeline | Missed deadline / incomplete MVP | Medium-High | Strict MVP boundary (§26); defer relationship integrity/AI if needed; timebox each Phase-5 check module |
| Pattern/naming detection producing noisy or misleading clusters on free-text columns | Confusing/low-value output, erodes trust in the tool | Medium | Restrict pattern analysis to configured/likely-structured columns by default; document limitations (§10.H) |
| GUI and CLI logic drifting out of sync if not carefully architected | Inconsistent results, undermines core reliability requirement | Medium | Enforce shared `core/` layer via project structure and code review; add an explicit integration test asserting GUI-path and CLI-path results match |
| AI integration adding complexity/fragility close to deadline | Destabilizes an otherwise-complete MVP | Medium | Keep AI fully optional and last in the roadmap (§28, Phase 11); ensure it's additive-only and independently disable-able |
| Ambiguous or conflicting business rules across different sample datasets | Inconsistent scoring perception during demo | Low-Medium | Use configuration profiles per dataset type (§18.6); document assumptions clearly in demo narrative |
| Large dataset performance issues | Poor demo experience, timeouts | Low-Medium | Use `pandas` vectorized operations throughout (avoid row-by-row Python loops); add row-count warning threshold (§22) |
| PySide6 packaging/distribution issues (for demo on a different machine) | Demo-day failure | Low | Test packaging (e.g., `PyInstaller`) well ahead of the final demo; keep a working `pip install -r requirements.txt` fallback |

---

## 32. Open Questions / Assumptions

The following items are explicitly flagged as needing confirmation from the mentor/stakeholder rather than being silently decided:

1. **[OPEN QUESTION]** Should relationship integrity checking (§10.J) be included in strict MVP, or deferred to Phase 2, given internship timeline constraints? (See §26.)
2. **[OPEN QUESTION]** Which AI provider/model should back the optional AI-assisted mode (§14), or should MVP simply stub the interface without a live integration?
3. **[OPEN QUESTION]** Should AI calls ever be permitted to see sample raw record values (with explicit opt-in and warning), or should AI input be strictly limited to aggregated/structured statistics? (§14.3)
4. **[ASSUMPTION]** Special-character rules are **opt-in per field** (a field with no assigned rule is not checked) rather than opt-out globally. (§10.G)
5. **[ASSUMPTION]** Default scoring dimension weights are Completeness 25%, Uniqueness 20%, Validity 20%, Consistency 15%, Integrity 15%, Cleanliness 5%, fully overridable via configuration. (§12.1)
6. **[ASSUMPTION]** Default readiness thresholds (90/75/50) are retained from the source requirements as configurable defaults, not hard-coded. (§12.5)
7. **[ASSUMPTION]** Relationship checks are limited to single-column or simple composite-key equality joins for MVP; conditional/fuzzy relationship logic is Phase 2+. (§10.J)
8. **[OPEN QUESTION]** Is there a specific target enterprise system (e.g., Salesforce, SAP, an ERP) this tool is meant to emulate PMA for, which might imply additional domain-specific rules? Source requirements do not specify one — the tool is designed to be **target-system-agnostic**.
9. **[OPEN QUESTION]** Should PII-aware handling (e.g., masking sensitive columns like SSN/DOB in exported reports) be considered for this internship's scope, or is it explicitly out of scope? (§23)
10. **[ASSUMPTION]** PDF report generation is treated as optional/future rather than MVP-required, since HTML and Excel already satisfy the "professional, shareable report" requirement. (§17.1)

---

*End of Document.*

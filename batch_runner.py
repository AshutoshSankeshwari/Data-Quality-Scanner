"""
batch_runner.py
Headless command-line execution interface for Data Quality Scanner.

Provides automated, non-interactive pre-migration data quality analysis,
readiness scoring, referential integrity validation, report generation,
and SQLite persistence without initializing any GUI/QApplication components.

Exit Codes:
  0 - Analysis completed successfully (regardless of data quality findings)
  1 - Command-line argument syntax or validation error
  2 - Input dataset loading error or configuration parse/validation error
  3 - Unexpected application or runtime error
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

# Core engine and loader imports (zero GUI dependencies)
from core.ingestion.loader import load_file, DataLoadError
from rules.config_loader import build_analysis_config_from_v2, get_config_hash, ConfigError
from core.service import AnalysisService, AnalysisConfig
from core.models import AnalysisResult
from db.connection import DEFAULT_DB_PATH
from db.repository import ScanRepository
from reports import generate_html, generate_excel, generate_json, get_report_filename
from reports.summary_builder import build_issue_summary_counts, count_affected_rows


def create_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for headless batch execution."""
    parser = argparse.ArgumentParser(
        prog="batch_runner.py",
        description="Data Quality Scanner — Headless Batch Analysis Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_runner.py samples/customers_clean_100pct.csv
  python batch_runner.py samples/customers_clean_100pct.csv samples/orders_related_to_customers.csv
  python batch_runner.py data/input.xlsx --sheet Customers --config custom_config.yaml --output out_dir/
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        metavar="DATASET",
        help="One or more dataset files (CSV or Excel .xlsx/.xls) to analyze.",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to YAML configuration file (defaults to 'config/config.yaml' if present).",
    )
    parser.add_argument(
        "--profile", "-p",
        type=str,
        default=None,
        help="Mandatory fields profile name defined in configuration (e.g., 'Customer_Master').",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="reports",
        help="Directory to save generated assessment reports (default: 'reports').",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database file for scan persistence (default: 'data/scanner.db').",
    )
    parser.add_argument(
        "--no-db", "--skip-db",
        action="store_true",
        help="Disable persisting scan findings to SQLite.",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=0,
        help="Excel sheet name or 0-based index to load when analyzing Excel files (default: 0 / first sheet).",
    )

    # Report format controls
    rpt_group = parser.add_argument_group("Report Options")
    rpt_group.add_argument(
        "--html",
        action="store_true",
        help="Generate standalone HTML assessment report.",
    )
    rpt_group.add_argument(
        "--excel",
        action="store_true",
        help="Generate multi-sheet Excel (.xlsx) assessment report.",
    )
    rpt_group.add_argument(
        "--json",
        action="store_true",
        help="Generate machine-readable JSON structured report.",
    )
    rpt_group.add_argument(
        "--no-reports",
        action="store_true",
        help="Disable file-based report export entirely.",
    )

    # Console output controls
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress human-readable console progress and summary.",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="Data Quality Scanner (Batch Mode)",
    )

    return parser


PROMPT_EXPORT_TEXT = """Select export format(s):

1. Excel
2. JSON
3. HTML
4. All formats

Enter the option(s) you would like for exporting: """


def parse_export_selection(user_input: str) -> dict[str, bool] | None:
    """
    Parse a user selection string (e.g. '1', '1,3', '1, 2, 3', '4').
    Returns a dict with bool flags for 'excel', 'json', 'html', or None if invalid.
    """
    if not user_input or not user_input.strip():
        return None

    raw_tokens = user_input.split(",")
    tokens = [t.strip() for t in raw_tokens]

    if any(t == "" for t in tokens):
        return None

    valid_options = {"1", "2", "3", "4"}
    if not all(t in valid_options for t in tokens):
        return None

    if "4" in tokens:
        return {"excel": True, "json": True, "html": True}

    return {
        "excel": "1" in tokens,
        "json": "2" in tokens,
        "html": "3" in tokens,
    }


def prompt_export_selection(input_func=input) -> dict[str, bool]:
    """
    Prompt the user to interactively select export formats until valid input is given.
    """
    while True:
        try:
            choice = input_func(PROMPT_EXPORT_TEXT)
        except EOFError:
            return {"excel": False, "json": False, "html": False}

        parsed = parse_export_selection(choice)
        if parsed is not None:
            return parsed

        print("Invalid selection. Please choose 1, 2, 3, or 4.\n")


def run_batch(argv: list[str] | None = None, input_func=input) -> int:
    """
    Main batch execution routine.
    Returns integer exit code (0 = success, 1 = CLI error, 2 = load/config error, 3 = runtime error).
    """
    parser = create_parser()

    # 1. Parse command-line arguments
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # argparse exit: 0 for --help/--version, 2 for syntax errors -> map to 1 for standard CLI syntax error
        return 0 if e.code == 0 else 1
    except Exception as e:
        sys.stderr.write(f"Error parsing command-line arguments: {e}\n")
        return 1

    # 2. Load and validate configuration
    config_path = args.config
    if config_path is None:
        default_cfg = Path(__file__).parent / "config" / "config.yaml"
        if default_cfg.exists():
            config_path = str(default_cfg)

    cfg: AnalysisConfig | None = None
    config_hash = ""
    if args.config:
        if not Path(args.config).exists():
            sys.stderr.write(f"Configuration file not found: {args.config}\n")
            return 2
        try:
            cfg = build_analysis_config_from_v2(
                config_path=args.config,
                mandatory_fields_profile=args.profile,
            )
            config_hash = get_config_hash(args.config)
        except ConfigError as ce:
            sys.stderr.write(f"Configuration Error: {ce}\n")
            return 2
        except Exception as e:
            sys.stderr.write(f"Failed to load configuration '{args.config}': {e}\n")
            return 2
    elif config_path:
        cfg = build_analysis_config_from_v2(
            config_path=config_path,
            mandatory_fields_profile=args.profile,
        )
        config_hash = get_config_hash(config_path)
    else:
        cfg = AnalysisConfig()

    # 3. Ingest and validate dataset files
    datasets: list[tuple[str, object]] = []
    for file_str in args.files:
        f_path = Path(file_str)
        stem_name = f_path.stem
        try:
            df = load_file(f_path, sheet_name=args.sheet)
            datasets.append((stem_name, df))
        except DataLoadError as dle:
            sys.stderr.write(f"Dataset Loading Error: {dle}\n")
            return 2
        except Exception as e:
            sys.stderr.write(f"Unexpected error loading '{file_str}': {e}\n")
            return 2

    if not datasets:
        sys.stderr.write("Error: No datasets were loaded.\n")
        return 1

    # 4. Execute Core Analysis Pipeline
    try:
        service = AnalysisService()
        result = service.run(datasets=datasets, config=cfg)
    except Exception as e:
        sys.stderr.write(f"Analysis Execution Error: {e}\n")
        return 3

    # 5. Persist to SQLite (unless disabled)
    if not args.no_db:
        try:
            db_path = Path(args.db)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            repo = ScanRepository(db_path)
            repo.save_scan(
                result,
                app_version=None,
                config_hash=config_hash,
            )
        except Exception as e:
            # Persistence failure is non-blocking
            if not args.quiet:
                sys.stderr.write(f"Warning: Failed to save scan to SQLite database ({args.db}): {e}\n")

    # 6. Generate Assessment Reports
    report_paths: dict[str, Path] = {}
    if not args.no_reports:
        # Determine formats: explicit CLI flags vs. interactive prompt
        has_cli_flags = args.html or args.excel or args.json
        if has_cli_flags:
            gen_excel = args.excel
            gen_json = args.json
            gen_html = args.html
        elif not args.quiet:
            selected = prompt_export_selection(input_func=input_func)
            gen_excel = selected.get("excel", False)
            gen_json = selected.get("json", False)
            gen_html = selected.get("html", False)
        else:
            # Quiet / non-interactive without format flags: skip reports
            gen_excel = False
            gen_json = False
            gen_html = False

        if gen_excel or gen_json or gen_html:
            out_dir = Path(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)

            try:
                if gen_excel:
                    excel_name = get_report_filename(result, "xlsx")
                    excel_path = generate_excel(result, out_dir / excel_name, datasets=datasets)
                    report_paths["Excel"] = excel_path

                if gen_json:
                    json_name = get_report_filename(result, "json")
                    json_path = generate_json(result, out_dir / json_name, datasets=datasets)
                    report_paths["JSON"] = json_path

                if gen_html:
                    html_name = get_report_filename(result, "html")
                    html_path = generate_html(result, out_dir / html_name, datasets=datasets)
                    report_paths["HTML"] = html_path
            except Exception as e:
                sys.stderr.write(f"Warning: Report generation encountered an error: {e}\n")

    # 7. Print Console Summary
    if not args.quiet:
        _print_console_summary(result, report_paths)

    return 0


def _print_console_summary(result: AnalysisResult, report_paths: dict[str, Path]):
    """Print human-readable and automation-friendly summary to standard output."""
    print("=" * 60)
    print("Data Quality Scanner -- Batch Mode")
    print("=" * 60)

    # Dataset details
    print("Dataset(s):")
    for idx, ds in enumerate(result.datasets):
        role = " [Primary]" if idx == 0 and len(result.datasets) > 1 else ""
        print(f"  - {ds.name} ({ds.row_count:,} records, {ds.column_count} columns){role}")
    print()

    # Readiness Score & Issues
    if result.score:
        print(f"Overall Score:  {result.score.overall:.1f} / 100.0")
        print(f"Readiness:      {result.score.category.value}")

    summary_counts = build_issue_summary_counts(result)
    total_issues = summary_counts.get("total_problems", 0)
    print(f"Total Issues:   {total_issues:,}")
    aff = count_affected_rows(result)
    aff_str = f"{aff:,}" if aff is not None else "—"
    print(f"Affected Rows:  {aff_str}")
    print()

    # Relationship Status
    if result.relationship_results:
        for rel in result.relationship_results:
            p_k = ", ".join(rel.parent_key) if isinstance(rel.parent_key, list) else str(rel.parent_key)
            c_k = ", ".join(rel.child_key) if isinstance(rel.child_key, list) else str(rel.child_key)
            print("Relationship Detected:  YES")
            print(f"Origin:                 {rel.origin_display}")
            print(f"Parent:                 {rel.parent_dataset}.{p_k}")
            print(f"Child:                  {rel.child_dataset}.{c_k}")
            print(f"Integrity Status:       {rel.status}")
            print(f"Child Records:          {rel.total_child_records:,}")
            print(f"Invalid References:     {rel.orphan_count:,} ({rel.orphan_pct:.1f}%)")
            print()
    else:
        print("Relationship Detected:  NO")
        if len(result.datasets) >= 2:
            print("Note: No parent-child relationship detected between loaded datasets.")
        print()

    # Reports
    if report_paths:
        print("Reports Generated:")
        for fmt, path in report_paths.items():
            print(f"  - {fmt:5s}: {path}")
        print()

    print(f"Scan completed successfully. (Scan ID: {result.run_id})")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(run_batch())

"""
db/repository.py
Repository layer for SQLite persistence operations.
Uses Python's built-in sqlite3 module with parameterised queries and transactions.
Never stores raw dataset rows. Degrades gracefully on database errors.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Optional

from core.models import AnalysisResult
from db.connection import get_connection
from db.serializer import (
    serialize_column_profile,
    extract_check_results_for_db,
    reconstruct_analysis_result,
)

logger = logging.getLogger(__name__)


class ScanRepository:
    """Repository managing scan persistence and history retrieval in SQLite."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = db_path

    def save_scan(
        self,
        result: AnalysisResult,
        app_version: str = "2.0.0",
        config_hash: str = "",
    ) -> Optional[int]:
        """
        Save an AnalysisResult and its aggregated child records to SQLite.
        Atomic transaction: commits all tables together or rolls back cleanly.
        Returns the new scan integer ID, or None if save failed.
        """
        try:
            conn = get_connection(self.db_path)
            with conn:
                cursor = conn.cursor()

                # Calculate issue totals from score if present
                blocker_c = result.score.blocker_count if result.score else 0
                high_c = result.score.high_count if result.score else 0
                med_c = result.score.medium_count if result.score else 0
                low_c = result.score.low_count if result.score else 0
                total_issues = blocker_c + high_c + med_c + low_c

                overall_score = result.score.overall if result.score else None
                readiness_cat = result.score.category.value if result.score else None

                # 1. Insert scans root record
                cursor.execute(
                    """
                    INSERT INTO scans (
                        run_id, started_at, completed_at, app_version, config_hash,
                        overall_score, readiness_category, blocker_count, high_count,
                        medium_count, low_count, total_issues, dataset_count,
                        enabled_checks_json, ai_insights, warnings_json, affected_rows
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        result.run_id,
                        result.timestamp,
                        result.timestamp,
                        app_version,
                        config_hash,
                        overall_score,
                        readiness_cat,
                        blocker_c,
                        high_c,
                        med_c,
                        low_c,
                        total_issues,
                        len(result.datasets),
                        json.dumps(result.enabled_checks),
                        result.ai_insights,
                        json.dumps(result.warnings),
                        result.affected_rows_count,
                    ),
                )
                scan_id = cursor.lastrowid

                # 2. Insert scan_datasets (metadata & column profiles only, NO raw rows)
                for idx, ds in enumerate(result.datasets):
                    cols_summary = [serialize_column_profile(c) for c in ds.columns]
                    cursor.execute(
                        """
                        INSERT INTO scan_datasets (
                            scan_id, dataset_name, row_count, column_count,
                            duplicate_row_count, duplicate_row_pct, overall_null_pct,
                            size_bytes, is_primary, columns_summary_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            scan_id,
                            ds.name,
                            ds.row_count,
                            ds.column_count,
                            ds.duplicate_row_count,
                            ds.duplicate_row_pct,
                            ds.overall_null_pct,
                            ds.size_bytes,
                            1 if idx == 0 else 0,
                            json.dumps(cols_summary),
                        ),
                    )

                # 3. Insert check_results
                check_rows = extract_check_results_for_db(result)
                for cr in check_rows:
                    cursor.execute(
                        """
                        INSERT INTO check_results (
                            scan_id, dataset_name, check_type, severity,
                            affected_count, affected_pct, details_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            scan_id,
                            cr["dataset_name"],
                            cr["check_type"],
                            cr["severity"],
                            cr["affected_count"],
                            cr["affected_pct"],
                            cr["details_json"],
                        ),
                    )

                # 4. Insert scoring_factors
                if result.score and result.score.dimensions:
                    for dim in result.score.dimensions:
                        cursor.execute(
                            """
                            INSERT INTO scoring_factors (
                                scan_id, dimension_name, score, weight,
                                weighted_score, explanation
                            ) VALUES (?, ?, ?, ?, ?, ?);
                            """,
                            (
                                scan_id,
                                dim.name,
                                dim.score,
                                dim.weight,
                                dim.weighted,
                                dim.explanation,
                            ),
                        )

                # 5. Insert relationship_results
                for rel in result.relationship_results:
                    desc_payload = json.dumps({
                        "text": rel.description,
                        "samples": rel.sample_orphan_records,
                        "origin": rel.origin,
                        "automatically_confirmed": rel.automatically_confirmed,
                        "is_automatically_detected": rel.is_automatically_detected,
                    })
                    cursor.execute(
                        """
                        INSERT INTO relationship_results (
                            scan_id, parent_dataset, parent_key, child_dataset,
                            child_key, total_child_records, orphan_count, orphan_pct,
                            severity, description
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            scan_id,
                            rel.parent_dataset,
                            rel.parent_key,
                            rel.child_dataset,
                            rel.child_key,
                            rel.total_child_records,
                            rel.orphan_count,
                            rel.orphan_pct,
                            rel.severity.value,
                            desc_payload,
                        ),
                    )

                # 6. Insert recommendations
                for rec in result.recommendations:
                    cursor.execute(
                        """
                        INSERT INTO recommendations (
                            scan_id, title, description, severity,
                            issue_type, dataset_name, affected_columns_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            scan_id,
                            rec.title,
                            rec.description,
                            rec.severity.value,
                            rec.issue_type,
                            rec.dataset_name,
                            json.dumps(rec.affected_columns),
                        ),
                    )

            conn.close()
            return scan_id

        except Exception as exc:
            logger.error("Failed to save scan to SQLite: %s", exc, exc_info=True)
            return None

    def list_scans(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Return summaries of historical scans ordered by started_at descending.
        Each item includes primary dataset name, score, and issue counts.
        """
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    s.id,
                    s.run_id,
                    s.started_at,
                    s.completed_at,
                    s.app_version,
                    s.config_hash,
                    s.overall_score,
                    s.readiness_category,
                    s.blocker_count,
                    s.high_count,
                    s.medium_count,
                    s.low_count,
                    s.total_issues,
                    s.dataset_count,
                    s.affected_rows,
                    (SELECT dataset_name FROM scan_datasets WHERE scan_id = s.id AND is_primary = 1 LIMIT 1) as primary_dataset,
                    (SELECT GROUP_CONCAT(dataset_name, ', ') FROM scan_datasets WHERE scan_id = s.id) as all_datasets
                FROM scans s
                ORDER BY s.started_at DESC, s.id DESC
                LIMIT ?;
                """,
                (limit,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as exc:
            logger.error("Failed to list scans from SQLite: %s", exc, exc_info=True)
            return []

    def get_scan_result(self, scan_id_or_run_id: int | str) -> Optional[AnalysisResult]:
        """
        Fetch and reconstruct an AnalysisResult from SQLite by integer ID or string run_id.
        Allows viewing or exporting historical reports without original files.
        """
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()

            # Find scan row
            if isinstance(scan_id_or_run_id, int) or (isinstance(scan_id_or_run_id, str) and scan_id_or_run_id.isdigit()):
                cursor.execute("SELECT * FROM scans WHERE id = ?;", (int(scan_id_or_run_id),))
            else:
                cursor.execute("SELECT * FROM scans WHERE run_id = ?;", (str(scan_id_or_run_id),))

            scan_row = cursor.fetchone()
            if not scan_row:
                conn.close()
                return None

            scan_dict = dict(scan_row)
            scan_id = scan_dict["id"]

            # Child rows
            cursor.execute("SELECT * FROM scan_datasets WHERE scan_id = ? ORDER BY is_primary DESC, id ASC;", (scan_id,))
            dataset_rows = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM check_results WHERE scan_id = ?;", (scan_id,))
            check_rows = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM scoring_factors WHERE scan_id = ?;", (scan_id,))
            factor_rows = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM relationship_results WHERE scan_id = ?;", (scan_id,))
            rel_rows = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM recommendations WHERE scan_id = ?;", (scan_id,))
            rec_rows = [dict(r) for r in cursor.fetchall()]

            conn.close()

            return reconstruct_analysis_result(
                scan_row=scan_dict,
                dataset_rows=dataset_rows,
                check_rows=check_rows,
                factor_rows=factor_rows,
                relationship_rows=rel_rows,
                recommendation_rows=rec_rows,
            )

        except Exception as exc:
            logger.error("Failed to retrieve scan result: %s", exc, exc_info=True)
            return None

    def delete_scan(self, scan_id_or_run_id: int | str) -> bool:
        """Delete a scan and cascade to child tables."""
        try:
            conn = get_connection(self.db_path)
            with conn:
                cursor = conn.cursor()
                if isinstance(scan_id_or_run_id, int) or (isinstance(scan_id_or_run_id, str) and scan_id_or_run_id.isdigit()):
                    cursor.execute("DELETE FROM scans WHERE id = ?;", (int(scan_id_or_run_id),))
                else:
                    cursor.execute("DELETE FROM scans WHERE run_id = ?;", (str(scan_id_or_run_id),))
                deleted = cursor.rowcount > 0
            conn.close()
            return deleted
        except Exception as exc:
            logger.error("Failed to delete scan: %s", exc, exc_info=True)
            return False

    def count_scans(self) -> int:
        """Return total count of persisted scans."""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM scans;")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as exc:
            logger.error("Failed to count scans: %s", exc, exc_info=True)
            return 0

"""Text-preview validation inspectors."""

from typing import Any


class TextPreviewValidationInspectorMixin:
    @staticmethod
    def _normalized_preview_headers(headers: list[Any] | None) -> list[str]:
        return [str(value).strip() for value in (headers or []) if str(value).strip()]

    @classmethod
    def _inspect_text_preview_generic(
        cls,
        headers: list[Any] | None,
        total_rows: int,
        *,
        need_detail: bool | None,
    ) -> list[str]:
        issues: list[str] = []
        normalized = cls._normalized_preview_headers(headers)
        if need_detail is True and len(normalized) < 2:
            issues.append("Text-preview output must contain at least two columns.")
        if need_detail is True and total_rows < 1:
            issues.append("Text-preview output does not contain any data rows.")
        return issues

    @classmethod
    def _inspect_text_preview_temporal_aggregation(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if normalized and normalized[0] != "Period":
            issues.append("Temporal aggregation text preview should start with a `Period` column.")
        if len(normalized) >= 2 and not any(
            normalized[1].startswith(prefix)
            for prefix in ("Average ", "Total ", "Count ", "Median ", "Minimum ", "Maximum ")
        ):
            issues.append("Temporal aggregation text preview metric column label is missing the aggregate prefix.")
        return issues

    @classmethod
    def _inspect_text_preview_grouped_aggregation(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if len(normalized) >= 2 and not any(
            normalized[-1].startswith(prefix)
            for prefix in ("Average ", "Total ", "Count ", "Median ", "Minimum ", "Maximum ")
        ):
            issues.append("Grouped aggregation text preview metric column label is missing the aggregate prefix.")
        return issues

    @classmethod
    def _inspect_text_preview_relational_join(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        return cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)

    @classmethod
    def _inspect_text_preview_allocation(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if normalized and "Allocation Status" not in normalized:
            issues.append("Allocation text preview should include an `Allocation Status` column.")
        if normalized and "Allocated Quantity" not in normalized:
            issues.append("Allocation text preview should include an `Allocated Quantity` column.")
        return issues

    @classmethod
    def _inspect_text_preview_dependency_schedule(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if normalized and ("Start Time" not in normalized or "End Time" not in normalized):
            issues.append("Dependency-schedule text preview should include `Start Time` and `End Time` columns.")
        if normalized and "Task ID" not in normalized:
            issues.append("Dependency-schedule text preview should include a `Task ID` column.")
        return issues

    @classmethod
    def _inspect_text_preview_assignment_schedule(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if normalized:
            scheduling_markers = ("day", "time", "slot", "room", "session")
            entity_markers = ("student", "candidate", "participant", "attendee", "member", "name", "id")
            if not any(any(marker in column.lower() for marker in scheduling_markers) for column in normalized):
                issues.append("Assignment-schedule text preview should include at least one scheduling/location column.")
            if not any(any(marker in column.lower() for marker in entity_markers) for column in normalized):
                issues.append("Assignment-schedule text preview should include at least one entity-identifying column.")
        return issues

    @classmethod
    def _inspect_text_preview_region_growth(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if normalized and normalized[0] != "Region":
            issues.append("Region-growth text preview should start with a `Region` column.")
        if normalized and not any("Avg Penetration" in value for value in normalized[1:]):
            issues.append("Region-growth text preview is missing an average-penetration column.")
        if normalized and not any(value.startswith("Growth (") for value in normalized[1:]):
            issues.append("Region-growth text preview is missing a growth column.")
        return issues

    @classmethod
    def _inspect_text_preview_regression(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if normalized[:2] != ["Factor", "Weight"]:
            issues.append("Regression text preview should start with `Factor` and `Weight` columns.")
        return issues

    @classmethod
    def _inspect_text_preview_correlation(
        cls,
        headers: list[Any] | None,
        total_rows: int,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        normalized = cls._normalized_preview_headers(headers)
        if len(normalized) < 2:
            issues.append("Correlation text preview must contain at least two numeric columns.")
        if total_rows < 2:
            issues.append("Correlation text preview does not contain enough matrix rows.")
        return issues

    @classmethod
    def _inspect_text_preview_comparative_multi_sheet(
        cls,
        headers: list[Any] | None,
        total_rows: int,
        extra_sheet_names: list[Any] | None,
    ) -> list[str]:
        issues = cls._inspect_text_preview_generic(headers, total_rows, need_detail=True)
        required_sheets = {"HolidayVsNonHoliday"}
        present = {str(name).strip() for name in (extra_sheet_names or []) if str(name).strip()}
        missing = sorted(required_sheets.difference(present))
        if missing:
            issues.append(
                "Comparative multi-sheet text preview is missing required additional sheet(s): "
                + ", ".join(missing)
            )
        return issues

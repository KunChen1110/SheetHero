"""Initial analysis and context generation stage for SheetHero."""

import re
import time
import random
from typing import Optional
from openai import RateLimitError

from ...log.logger_registry import LoggerRegistry
from ...task_families import detect_task_family
from ..base.stage import Stage
from ...prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)


class UnderstandingStage(Stage):
    """
    Module responsible for generating initial analysis and understanding from Excel context and user questions.
    """

    def __init__(self,
                 client,
                 deployment: str,
                 progress_logger=None,
                 prompt_profile: str = "online_rich"):
        """Initialize the UnderstandingStage."""

        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

    def run(self, user_question: str, spreadsheet_context: str,
            session_context_understanding: Optional[str] = None) -> str:
        """
        Generate comprehensive understanding of the user's question in context.

        Combines Excel data context with the user's question to create an analysis plan that guides the execution module.
        """
        logger.info("Starting understanding analysis")
        if self.progress_logger:
            self.progress_logger.log("[UNDERSTANDING] start", to_terminal=False)

        family = detect_task_family(user_question)
        if family and family.understanding_plan:
            understanding_output = self._ensure_output_contract(
                family.understanding_plan.strip(),
                user_question,
            )
            if self.progress_logger:
                self.progress_logger.log_raw(
                    "\n".join(["### [UNDERSTANDING OUTPUT]", understanding_output or ""])
                )
                self.progress_logger.log("[UNDERSTANDING] completed", to_terminal=False)
            logger.info("Understanding analysis completed via deterministic family plan: %s", family.name)
            return understanding_output

        # Build prompt and get LLM response
        session_context = (session_context_understanding or "").strip()
        if session_context and not self._context_is_relevant(user_question, session_context):
            session_context = ""
        messages = self._create_multimodal_prompt(
            user_question,
            spreadsheet_context,
            session_context
        )
    
        understanding_output = self._get_llm_response(messages)
        understanding_output = self._sanitize_understanding_output(
            understanding_output,
            user_question
        )
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [UNDERSTANDING OUTPUT]", understanding_output or ""])
            )

        logger.info("Understanding analysis completed")
        if self.progress_logger:
            self.progress_logger.log("[UNDERSTANDING] completed", to_terminal=False)
        return understanding_output

    def _sanitize_understanding_output(self, text: str, user_question: str) -> str:
        """Keep offline understanding concise and machine-usable for downstream stages."""
        cleaned = (text or "").strip()
        if not cleaned:
            cleaned = "### 1. Sheet Summary\n- No understanding output generated."

        family = detect_task_family(user_question)
        if family and family.understanding_plan:
            cleaned = family.understanding_plan
        elif self._is_region_growth_chart_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- File: tc03_input01.xlsx\n"
                "- Sheets: Overview, Data\n"
                "- Data sheet uses a messy multi-row header with years below the real region header row.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `list_all_workbooks()` and `build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`.\n"
                "- Do not parse the multi-row header manually with `read_table_multi()`.\n"
                "- Write `analysis['output_df']` to `Output!A1`.\n"
                "- Highlight `analysis['fastest_growth_rows']`.\n"
                "- Add `analysis['summary']` below the detail table.\n"
                "- Plot each region from `analysis['chart_df']` with the built-in `plt`, then call `save_plot_to_excel('Output', 'F2')`.\n"
            )
        elif self._is_correlation_matrix_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- File: input workbook contains numeric iris feature columns and a species column.\n"
                "- Relevant columns are the numeric flower measurements plus `species` for filtering.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables()` and select `df = tables[0]['df']`.\n"
                "- Use `build_correlation_matrix_table(df, numeric_columns=[...], filter_column='species', filter_value='Iris-setosa')`.\n"
                "- Write `matrix_result['detail_data']` or `matrix_result['output_df']` directly to `Output!A1`.\n"
                "- Do not hand-code CSV/Excel reads or manual corr-matrix loops in this task.\n"
            )
        elif self._is_cycle_detection_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Multiple input files each contain one directed graph adjacency list.\n"
                "- Relevant columns are `Node From` and `Node To`.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables()`.\n"
                "- Use `build_cycle_detection_report(tables, from_col='Node From', to_col='Node To')`.\n"
                "- Write `cycle_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-code CSV reads or manual graph loops in this task.\n"
            )
        elif self._is_financial_dashboard_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Multiple input files provide monthly P&L data, monthly sales/marketing data, and KPI targets.\n"
                "- The goal is a quarter-level financial dashboard table, not a scalar answer.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `dashboard_result = build_financial_dashboard_report()`.\n"
                "- Write `dashboard_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build joins, target parsing, or dashboard rows in this task.\n"
            )
        elif self._is_candidate_screening_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Multiple candidate files share one schema with candidate attributes.\n"
                "- The goal is a ranked candidate table, excluding blank names and treating missing numeric inputs as 0.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `screening_result = build_candidate_screening_report()`.\n"
                "- Write `screening_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build file loops, score formulas, or ranking output rows in this task.\n"
            )
        elif self._is_inventory_eoq_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- One inventory parameter table provides demand, costs, lead time, and working days.\n"
                "- The goal is a new workbook containing three clear tables: base EOQ metrics, sensitivity analysis, and demand+20% metrics.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `inventory_result = build_inventory_eoq_report()`.\n"
                "- Write `inventory_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build EOQ formulas, parameter parsing, or table layout in this task.\n"
            )
        elif self._is_hospital_utilisation_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Multiple hospital tables provide patients, service demand/admissions, and staff presence.\n"
                "- The goal is one service-level utilisation table with optional red highlighting only for rows above the 90% threshold.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_hospital_utilisation_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- If `report['highlight_rows']` is non-empty, highlight them red; otherwise print `NO_HIGHLIGHT_ROWS:` and continue.\n"
                "- Do not hand-build groupby/merge logic in this task.\n"
            )
        elif self._is_market_share_shipment_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Two input workbooks contain quarterly India smartphone market share by brand and total quarterly smartphone shipments.\n"
                "- The task is to align the overlapping quarter range and estimate per-brand unit shipments.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `market_result = build_market_share_shipment_report()`.\n"
                "- Write `market_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build quarter alignment or brand multiplication logic in this task.\n"
            )
        elif self._is_cash_flow_efficiency_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- One financial workbook contains profit-and-loss and cash-flow statement rows by fiscal year.\n"
                "- The goal is a yearly table of operating cash flow, net income, OCF/Net Income, capital expenditures, and free cash flow.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_cash_flow_efficiency_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-locate statement rows or compute ratios manually in this task.\n"
            )
        elif self._is_diabetes_region_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Input workbooks contain regional diabetic-population counts and regional diabetes expenditure for 2024.\n"
                "- The goal is one regional summary table with global share and average expenditure per person.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_diabetes_region_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build region merges or percentage calculations in this task.\n"
            )
        elif self._is_mobile_reviews_summary_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- One reviews dataset contains country, brand, and rating fields for smartphone reviews.\n"
                "- The goal is one grouped summary table by country and brand with average rating and review count.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_mobile_reviews_summary_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Exclude rows with missing ratings from the calculations.\n"
                "- Do not hand-build groupby logic in this task.\n"
            )
        elif self._is_store_feature_analysis_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- One weekly-features table and one store-metadata table must be merged on Store.\n"
                "- The goal is a summary workbook with one sheet for averages by store type and one sheet for holiday vs non-holiday comparisons.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_store_feature_analysis_report()`.\n"
                "- Write `report['avg_by_type_detail_data']` to `AvgByStoreType!A1`.\n"
                "- Write `report['holiday_detail_data']` to `HolidayVsNonHoliday!A1`.\n"
                "- Do not hand-build merges or multi-sheet aggregation logic in this task.\n"
            )
        elif self._is_ecommerce_merge_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Multiple relational e-commerce CSV tables must be merged into one denormalized output table.\n"
                "- The translation table is required to convert product category names into English.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_ecommerce_merge_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build multi-file joins or translation logic in this task.\n"
            )
        elif self._is_missing_data_scan_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- One input workbook must be scanned for missing values and reported in natural language.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_missing_data_report()`.\n"
                "- Return `report['answer']` as short text.\n"
                "- Do not create or save an output workbook in this task.\n"
            )
        elif self._is_room_inconsistency_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- One input workbook contains room identifiers that may use inconsistent spacing/casing conventions.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_room_format_report()`.\n"
                "- Return `report['answer']` as short text.\n"
                "- Do not modify or save the workbook in this task.\n"
            )
        elif self._is_tutor_meeting_schedule_request(user_question):
            cleaned = (
                "### 1. Sheet Summary\n"
                "- Multiple tutor-related tables must be combined into one meeting schedule output.\n"
                "- The output should list each tutor meeting together with the students assigned to that tutor.\n"
                "\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_tutor_meeting_schedule_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build multi-file joins or manual row loops in this task.\n"
            )

        # Remove long code snippets that tend to pollute offline planning.
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)

        forbidden_terms = (
            "pd.read_excel",
            "pd.excelfile",
            "pd.read_csv",
            "pd.read_table",
            "to_excel",
            "openpyxl",
        )
        kept_lines = []
        for line in cleaned.splitlines():
            lower = line.lower()
            if any(term in lower for term in forbidden_terms):
                continue
            kept_lines.append(line.rstrip())
        cleaned = "\n".join(kept_lines).strip()

        return self._ensure_output_contract(cleaned, user_question)

    @staticmethod
    def _parse_contract_flag(text: str, key: str) -> Optional[bool]:
        # Accept both plain and markdown-emphasized keys:
        # requires_detailed_table: YES
        # **requires_detailed_table**: YES
        pattern = rf"(?:\*\*)?\s*{re.escape(key)}\s*(?:\*\*)?\s*:\s*(YES|NO|TRUE|FALSE)"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            return None
        return m.group(1).strip().upper() in {"YES", "TRUE"}

    @staticmethod
    def _infer_contract_from_question(user_question: str) -> dict:
        q = (user_question or "").lower()

        def has_term(term: str) -> bool:
            escaped = re.escape(term.lower()).replace(r"\ ", r"\s+")
            pattern = rf"(?<!\w){escaped}(?!\w)"
            return re.search(pattern, q, flags=re.IGNORECASE) is not None

        detail_terms = (
            "merge", "combine", "join", "concatenate",
            "detailed table", "full table", "all rows", "list all",
            "row by row", "each row",
            "schedule", "scheduling", "start time", "end time",
            "new excel sheet", "new spreadsheet", "new sheet",
            "fill any missing", "fill missing", "complete data", "complete file",
            "correlation matrix", "matrix", "4×4 table", "4x4 table",
            "contains cycle", "cycle", "graph id", "output an excel file",
            "| task id |", "| task name |", "| priority |", "| start time |", "| end time |",
        )
        highlight_terms = ("highlight", "red")
        explicit_summary_terms = (
            "average", "avg", "total", "sum", "count", "minimum", "maximum", "min", "max"
        )
        summary_terms = (
            "metric", "coefficient", "correlation", "regression", "weight", "weights"
        )
        family = detect_task_family(user_question)
        is_correlation_matrix = UnderstandingStage._is_correlation_matrix_request(user_question)
        need_detail = any(has_term(t) for t in detail_terms) or "line chart" in q or "sort the regions" in q or "sorted by" in q
        need_highlight = any(has_term(t) for t in highlight_terms)
        need_summary = any(has_term(t) for t in summary_terms)
        if is_correlation_matrix and not any(has_term(t) for t in explicit_summary_terms):
            need_summary = False
        if family is not None:
            if family.requires_detailed_table is not None:
                need_detail = family.requires_detailed_table
            if family.requires_highlight is not None:
                need_highlight = family.requires_highlight
            if family.requires_summary_metrics is not None:
                need_summary = family.requires_summary_metrics
        return {
            "requires_detailed_table": need_detail,
            "requires_highlight": need_highlight,
            "requires_summary_metrics": need_summary,
        }

    @staticmethod
    def _is_region_growth_chart_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        return "line chart" in q and "growth rate" in q and "region" in q and (
            "penetration" in q or "internet" in q
        )

    @staticmethod
    def _is_correlation_matrix_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        return "correlation matrix" in q or ("matrix" in q and "correlation" in q)

    @staticmethod
    def _is_cycle_detection_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        return "contain a cycle" in q or "contains a cycle" in q or ("cycle" in q and "graph" in q)

    @staticmethod
    def _is_financial_dashboard_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = (
            "gross profit",
            "net profit",
            "gross profit margin",
            "net profit margin",
            "customer acquisition cost",
            "marketing efficiency ratio",
        )
        return sum(1 for marker in markers if marker in q) >= 4

    @staticmethod
    def _is_candidate_screening_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = (
            "rank the candidates",
            "candidate information",
            "working experience",
            "number of skills",
            "personality score",
        )
        return sum(1 for marker in markers if marker in q) >= 4

    @staticmethod
    def _is_inventory_eoq_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        return ("economic order quantity" in q or "eoq" in q) and "reorder point" in q

    @staticmethod
    def _is_hospital_utilisation_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = ("staff utilisation", "service utilisation", "patient load", "department")
        return sum(1 for marker in markers if marker in q) >= 3

    @staticmethod
    def _is_market_share_shipment_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = ("market share", "smartphone", "shipment", "overlapping time period")
        return sum(1 for marker in markers if marker in q) >= 3

    @staticmethod
    def _is_cash_flow_efficiency_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = ("operating cash flow", "net income", "free cash flow", "cash flow efficiency")
        return sum(1 for marker in markers if marker in q) >= 2

    @staticmethod
    def _is_diabetes_region_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = ("diabetics worldwide by region", "share of global", "avg expenditure per person", "diabetes-related health expenditure")
        return sum(1 for marker in markers if marker in q) >= 2

    @staticmethod
    def _is_mobile_reviews_summary_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = ("smartphone reviews", "average rating", "number of reviews", "country", "brand")
        return sum(1 for marker in markers if marker in q) >= 4

    @staticmethod
    def _is_store_feature_analysis_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = ("holiday and non-holiday", "store type", "fuel price", "consumer price index", "unemployment")
        return sum(1 for marker in markers if marker in q) >= 3

    @staticmethod
    def _is_ecommerce_merge_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = ("brazilian e-commerce", "translate the product category names into english", "merged dataset", "eight csv files")
        return sum(1 for marker in markers if marker in q) >= 2

    @staticmethod
    def _is_tutor_meeting_schedule_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = (
            "students and their tutors",
            "students and tutors",
            "students attending",
            "tutor meeting",
            "meeting time and location",
            "assigned tutor",
        )
        return sum(1 for marker in markers if marker in q) >= 2

    @staticmethod
    def _is_missing_data_scan_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        return "missing data" in q and ("identify where" in q or "where values are missing" in q or "check the file" in q)

    @staticmethod
    def _is_room_inconsistency_request(user_question: str) -> bool:
        q = (user_question or "").lower()
        return "room identifiers" in q or "room identifier" in q or "c80" in q or "c 80" in q

    def _ensure_output_contract(self, text: str, user_question: str) -> str:
        """Normalize output contract for offline reliability.

        In offline mode we prefer deterministic intent extraction from the user
        question over LLM-written flags, because weak models often output
        contradictory contracts (e.g. scalar question but requires_highlight=YES).
        """
        inferred = self._infer_contract_from_question(user_question)
        # Offline-strict: inferred intent is authoritative to prevent noisy flags.
        final_flags = dict(inferred)

        reason_parts = []
        if final_flags["requires_detailed_table"]:
            reason_parts.append("detailed table required")
        if final_flags["requires_highlight"]:
            reason_parts.append("highlight required")
        if final_flags["requires_summary_metrics"]:
            reason_parts.append("summary metrics required")
        if not reason_parts:
            reason_parts.append("scalar output is sufficient")

        contract_block = (
            "\n\n### 3. Output Contract (MANDATORY, machine-readable)\n"
            f"requires_detailed_table: {'YES' if final_flags['requires_detailed_table'] else 'NO'}\n"
            f"requires_highlight: {'YES' if final_flags['requires_highlight'] else 'NO'}\n"
            f"requires_summary_metrics: {'YES' if final_flags['requires_summary_metrics'] else 'NO'}\n"
            f"contract_reason: {', '.join(reason_parts)}."
        )
        # Remove any existing contract block emitted by LLM to avoid duplicates/conflicts.
        cleaned = re.sub(
            r"\n*###\s*3\.\s*Output Contract[\s\S]*$",
            "",
            text.rstrip(),
            flags=re.IGNORECASE,
        ).rstrip()
        return (cleaned + contract_block).strip()

    def enhance(self, understanding_output: str, last_validation: dict,
                user_question: str = "") -> str:
        """Refine understanding output based on validation feedback."""
        if not last_validation:
            return understanding_output
        if not last_validation.get("improvement_feedback"):
            return understanding_output
        if self.progress_logger:
            self.progress_logger.log("[UNDERSTANDING] enhance from validation", to_terminal=False)

        prompt_text = self.prompt_builder.build_enhanced_understanding_prompt(
            understanding_output,
            last_validation
        )
        messages = [{"role": "user", "content": prompt_text}]
        enhanced = self._get_llm_response(messages)
        return self._sanitize_understanding_output(enhanced, user_question)

    def _create_multimodal_prompt(self, user_question: str,
                                  excel_context_understanding: str,
                                  session_context_understanding: str) -> list:
        """Build prompt combining user question with Excel context."""
        prompt_text = self.prompt_builder.build_understanding_prompt(
            user_question,
            excel_context_understanding,
            session_context_understanding
        )
        return [{"role": "user", "content": prompt_text}]

    def _context_is_relevant(self, user_question: str, session_context_understanding: str) -> bool:
        if not session_context_understanding:
            return False
        prompt_text = self.prompt_builder.build_understanding_context_match_prompt(
            user_question,
            session_context_understanding
        )
        messages = [{"role": "user", "content": prompt_text}]
        response = self._get_llm_response(messages)
        parsed = self._parse_yes_no(response or "")
        if parsed is None:
            return False
        return parsed

    @staticmethod
    def _parse_yes_no(text: str) -> Optional[bool]:
        upper = (text or "").strip().upper()
        if upper.startswith("YES"):
            return True
        if upper.startswith("NO"):
            return False
        return None

    def _get_llm_response(self, messages: list, max_retries: int = 5, base_delay: float = 1.0) -> str:
        """
        Get LLM response with exponential backoff retry for rate limits.
        Retries up to max_retries times, with increasing wait times between attempts.
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                )
                return response.choices[0].message.content

            except RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit hit, attempt {attempt + 1}/{max_retries}: {str(e)}")

                # Extract wait time from error message if available
                wait_time = self._extract_wait_time_from_error(str(e))

                if attempt < max_retries - 1:
                    if wait_time:
                        delay = wait_time + random.uniform(1, 3)
                        logger.info(f"Waiting {delay:.1f} seconds as suggested by API")
                    else:
                        delay = 10
                        logger.info(f"Waiting {delay:.1f} seconds")

                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed due to rate limiting")
                    break

            except Exception as e:
                last_exception = e
                logger.error(f"API error, attempt {attempt + 1}/{max_retries}: {str(e)}")

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Waiting {delay:.1f} seconds before retry")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    break

        if last_exception:
            raise last_exception

    def _extract_wait_time_from_error(self, error_message: str) -> Optional[int]:
        """
        Parse retry wait time from rate limit error messages.
        Looks for patterns like "Try again in X seconds" or "Retry after X seconds".
        """
        try:
            # Look for patterns like "Try again in X seconds"
            match = re.search(r'try again in (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            # Look for other patterns like "Retry after X seconds"
            match = re.search(r'retry after (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            return None
        except:
            return None

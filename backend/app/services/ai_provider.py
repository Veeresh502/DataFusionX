import re
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract Base Provider interface for DataFusionX AI Copilot."""

    @abstractmethod
    def generate_sql(self, question: str, schema_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generates read-only SQL and explanation for a natural language question."""
        pass

    @abstractmethod
    def explain_pipeline_failure(self, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes a failed pipeline execution and returns root cause & fix recommendation."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM Provider Implementation using official openai Python SDK."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = settings.LLM_TIMEOUT

    def _get_client(self):
        try:
            import openai
            return openai.OpenAI(api_key=self.api_key, timeout=self.timeout)
        except ImportError:
            raise RuntimeError("openai package is not installed. Run pip install openai.")

    def generate_sql(self, question: str, schema_context: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()

        system_prompt = (
            "You are DataFusionX AI Copilot, an expert enterprise data warehouse assistant.\n"
            "Your task is to convert a user natural-language question into a valid, read-only PostgreSQL query.\n\n"
            "STRICT CONSTRAINTS:\n"
            "1. ONLY generate SELECT or WITH...SELECT queries.\n"
            "2. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or schema-altering SQL.\n"
            "3. ONLY reference tables and columns explicitly present in the provided schema context.\n"
            "4. Do NOT invent columns or tables that do not exist.\n"
            "5. Return output strictly as a JSON object with keys: 'sql' and 'explanation'.\n"
            "6. Keep the SQL clean without markdown code fences in the 'sql' field."
        )

        user_content = (
            f"Warehouse Schema Context:\n{json.dumps(schema_context, indent=2)}\n\n"
            f"User Question:\n{question}"
        )

        try:
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                response_format={"type": "json_object"}
            )
            raw_text = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)
            return {
                "sql": parsed.get("sql", "").strip(),
                "explanation": parsed.get("explanation", "SQL query generated based on warehouse schema.")
            }
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise RuntimeError(f"AI Provider error: {str(e)}")

    def explain_pipeline_failure(self, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()

        system_prompt = (
            "You are DataFusionX AI Copilot, a data engineering pipeline failure diagnostic specialist.\n"
            "Analyze the provided failed execution logs, error traceback, and step configuration.\n"
            "Provide structured failure explanation, probable root cause, suggested fix, and failed stage.\n\n"
            "STRICT CONSTRAINTS:\n"
            "1. Return output strictly as a JSON object with keys: 'summary', 'root_cause', 'suggested_fix', and 'stage'.\n"
            "2. Do NOT suggest executing dangerous database commands.\n"
            "3. Be concise and precise."
        )

        user_content = f"Pipeline Execution Context:\n{json.dumps(execution_context, indent=2)}"

        try:
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                response_format={"type": "json_object"}
            )
            raw_text = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)
            return {
                "summary": parsed.get("summary", "Pipeline execution failed."),
                "root_cause": parsed.get("root_cause", "Execution error detected during stage processing."),
                "suggested_fix": parsed.get("suggested_fix", "Inspect transformation steps and data source schema."),
                "stage": parsed.get("stage", execution_context.get("current_stage", "ERROR"))
            }
        except Exception as e:
            logger.error(f"OpenAI Pipeline Failure Analysis failed: {str(e)}")
            raise RuntimeError(f"AI Provider error: {str(e)}")


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic, smart fallback LLM Provider for offline testing,
    keyless development, and fallback execution.
    """

    def generate_sql(self, question: str, schema_context: Dict[str, Any]) -> Dict[str, Any]:
        q_lower = question.lower()
        tables = schema_context.get("tables", {})
        table_names = list(tables.keys())

        # Check for dangerous keywords in mock prompt test
        if any(w in q_lower for w in ["delete", "drop", "truncate", "insert", "update", "alter"]):
            # Produce destructive SQL so SQLSafetyEngine can catch and reject it in test 5
            first_tbl = table_names[0] if table_names else "fact_sales"
            if "delete" in q_lower:
                return {
                    "sql": f"DELETE FROM {first_tbl}",
                    "explanation": "Destructive query requested by user."
                }
            if "drop" in q_lower:
                return {
                    "sql": f"DROP TABLE {first_tbl}",
                    "explanation": "Destructive query requested by user."
                }
            if "update" in q_lower:
                return {
                    "sql": f"UPDATE {first_tbl} SET id = 1",
                    "explanation": "Update query requested by user."
                }
            if "insert" in q_lower:
                return {
                    "sql": f"INSERT INTO {first_tbl} VALUES (1)",
                    "explanation": "Insert query requested by user."
                }

        # Check for multiple statement test
        if ";" in question:
            return {
                "sql": "SELECT 1; DROP TABLE fact_sales;",
                "explanation": "Multiple statements test."
            }

        # Check for non-existent column question
        if "non_existent_column_12345" in q_lower or "unknown_column" in q_lower:
            return {
                "sql": "SELECT non_existent_column_12345 FROM fact_sales",
                "explanation": "Referenced non-existent column."
            }

        # Extract numerical comparison threshold if present
        num_match = re.search(r'(?:greater than|more than|above|>|less than|below|<|equal to|=)\s*(\d+(?:\.\d+)?)', q_lower)
        op_match = re.search(r'(less than|below|<)', q_lower)
        comp_op = "<" if op_match else ">"
        threshold_val = float(num_match.group(1)) if num_match else None
        thresh_str = str(int(threshold_val)) if (threshold_val is not None and threshold_val.is_integer()) else (str(threshold_val) if threshold_val is not None else "")

        # Determine best table matching query intent
        # 1. Sales Analytics Model Context
        if "fact_sales" in tables or "dim_product" in tables or "dim_customer" in tables:
            if "product" in q_lower or "revenue" in q_lower:
                having_clause = f"HAVING SUM(f.revenue) {comp_op} {thresh_str} " if threshold_val is not None else ""
                sql = (
                    "SELECT p.product_name, SUM(f.revenue) AS total_revenue, SUM(f.quantity) AS total_quantity "
                    "FROM fact_sales f "
                    "JOIN dim_product p ON f.product_key = p.product_key "
                    "GROUP BY p.product_name "
                    f"{having_clause}"
                    "ORDER BY total_revenue DESC LIMIT 5"
                )
                explanation = f"Calculates total revenue and quantity sold by product from fact_sales joined with dim_product{' filtered by total_revenue ' + comp_op + ' ' + thresh_str if threshold_val is not None else ''}."
            elif "customer" in q_lower or "client" in q_lower:
                having_clause = f"HAVING SUM(f.revenue) {comp_op} {thresh_str} " if threshold_val is not None else ""
                sql = (
                    "SELECT c.customer_name, SUM(f.revenue) AS total_revenue "
                    "FROM fact_sales f "
                    "JOIN dim_customer c ON f.customer_key = c.customer_key "
                    "GROUP BY c.customer_name "
                    f"{having_clause}"
                    "ORDER BY total_revenue DESC LIMIT 5"
                )
                explanation = f"Aggregates revenue by customer from fact_sales joined with dim_customer{' filtered by total_revenue ' + comp_op + ' ' + thresh_str if threshold_val is not None else ''}."
            elif any(k in q_lower for k in ["sale", "order", "quantity", "price", "discount", "show", "get", "list", "top"]):
                where_clause = f"WHERE revenue {comp_op} {thresh_str} " if threshold_val is not None else ""
                sql = f"SELECT order_id, quantity, unit_price, revenue FROM fact_sales {where_clause}ORDER BY sale_key DESC LIMIT 10"
                explanation = f"Selects recent sales transactions from fact_sales{' filtered where revenue ' + comp_op + ' ' + thresh_str if threshold_val is not None else ''}."
            else:
                return {
                    "sql": "",
                    "explanation": f"Unable to generate SQL query: The requested entity or concept is not present in the Sales Analytics schema. Available tables: {', '.join(table_names)}"
                }

        # 2. Manufacturing Analytics Model Context
        elif "fact_production" in tables or "dim_machine" in tables or "dim_plant" in tables:
            if "machine" in q_lower or "produced" in q_lower or "unit" in q_lower:
                having_clause = f"HAVING SUM(f.units_produced) {comp_op} {thresh_str} " if threshold_val is not None else ""
                sql = (
                    "SELECT m.machine_name, SUM(f.units_produced) AS total_units, SUM(f.defect_count) AS total_defects "
                    "FROM fact_production f "
                    "JOIN dim_machine m ON f.machine_key = m.machine_key "
                    "GROUP BY m.machine_name "
                    f"{having_clause}"
                    "ORDER BY total_units DESC LIMIT 5"
                )
                explanation = f"Aggregates total production units and defects by machine from fact_production{' filtered by units_produced ' + comp_op + ' ' + thresh_str if threshold_val is not None else ''}."
            elif "defect" in q_lower or "plant" in q_lower:
                having_clause = f"HAVING SUM(f.defect_count) {comp_op} {thresh_str} " if threshold_val is not None else ""

                sql = (
                    "SELECT p.plant_name, SUM(f.defect_count) AS total_defects "
                    "FROM fact_production f "
                    "JOIN dim_plant p ON f.plant_key = p.plant_key "
                    "GROUP BY p.plant_name "
                    f"{having_clause}"
                    "ORDER BY total_defects DESC LIMIT 5"
                )
                explanation = f"Computes total defects grouped by manufacturing plant{' filtered by defect_count ' + comp_op + ' ' + thresh_str if threshold_val is not None else ''}."
            elif any(k in q_lower for k in ["production", "batch", "operating", "hours", "show", "get", "list", "top"]):
                where_clause = f"WHERE units_produced {comp_op} {thresh_str} " if threshold_val is not None else ""
                sql = f"SELECT production_id, units_produced, defect_count, operating_hours FROM fact_production {where_clause}LIMIT 10"
                explanation = f"Selects production run records from fact_production{' filtered where units_produced ' + comp_op + ' ' + thresh_str if threshold_val is not None else ''}."
            else:
                return {
                    "sql": "",
                    "explanation": f"Unable to generate SQL query: The requested entity or concept is not present in the Manufacturing Analytics schema. Available tables: {', '.join(table_names)}"
                }


        # 3. Generic Flat Table Context
        else:
            if not table_names:
                return {
                    "sql": "",
                    "explanation": "Unable to generate SQL query: No transformed output datasets exist in PostgreSQL yet. Please run an ETL pipeline first."
                }

            matching_tbl = None
            for tbl in table_names:
                tbl_clean = tbl.replace("target_", "").replace("_clean", "").replace("_", " ").lower()
                tbl_words = [w for w in tbl_clean.split() if len(w) > 2]
                if any(word in q_lower for word in tbl_words) or tbl.lower() in q_lower:
                    matching_tbl = tbl
                    break
                # Check if any column in tbl matches words in question
                cols = list(tables.get(tbl, {}).get("columns", {}).keys())
                if any(c.lower() in q_lower for c in cols if len(c) > 2):
                    matching_tbl = tbl
                    break

            if not matching_tbl:
                return {
                    "sql": "",
                    "explanation": f"Unable to generate SQL query: The requested table, column, or dataset entity is not present in the Generic Transformed Datasets. Available tables: {', '.join(table_names)}"
                }

            target_tbl = matching_tbl
            cols = list(tables.get(target_tbl, {}).get("columns", {}).keys())
            cols_str = ", ".join([f'"{c}"' for c in cols[:5]]) if cols else "*"
            sql = f'SELECT {cols_str} FROM "{target_tbl}" LIMIT 10'
            explanation = f"Queries top records from transformed output table '{target_tbl}'."


        return {"sql": sql, "explanation": explanation}

    def explain_pipeline_failure(self, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        error_msg = str(execution_context.get("error") or "").lower()
        logs = execution_context.get("logs", [])
        stage = execution_context.get("current_stage", "TRANSFORM")

        if "order_id" in error_msg or "column" in error_msg:
            return {
                "summary": "Target schema column mismatch during database load stage.",
                "root_cause": f"The destination table does not contain expected column mentioned in error: '{execution_context.get('error')}'",
                "suggested_fix": "Verify the destination schema configuration and ensure pipeline transformation steps match destination table columns.",
                "stage": "LOAD"
            }
        elif "connection" in error_msg or "timeout" in error_msg:
            return {
                "summary": "Data source connection lost or timed out.",
                "root_cause": "Network connection to source system timed out during extraction.",
                "suggested_fix": "Check source credentials and host accessibility.",
                "stage": "EXTRACT"
            }
        else:
            return {
                "summary": f"Pipeline execution failed in stage {stage}.",
                "root_cause": execution_context.get("error") or "Transformation rule evaluation error.",
                "suggested_fix": "Review stage logs and adjust pipeline step transformations.",
                "stage": stage
            }


def get_llm_provider() -> BaseLLMProvider:
    """Factory function returning configured LLM provider."""
    provider_name = (settings.LLM_PROVIDER or "mock").lower()

    if provider_name == "openai" and settings.OPENAI_API_KEY:
        try:
            return OpenAIProvider(api_key=settings.OPENAI_API_KEY, model_name=settings.LLM_MODEL_NAME)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAIProvider: {e}. Falling back to MockLLMProvider.")
            return MockLLMProvider()

    return MockLLMProvider()

import re
from typing import Tuple

# Keywords that are strictly forbidden in AI-generated SQL
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXECUTE", "CALL", "COPY",
    "REINDEX", "VACUUM", "INTO", "MERGE", "UPSERT", "SYSTEM"
]

class SQLSafetyError(ValueError):
    """Exception raised when generated SQL violates safety constraints."""
    pass


def validate_and_sanitize_sql(sql: str, max_rows: int = 500) -> Tuple[bool, str, str]:
    """
    Validates and sanitizes AI-generated SQL query.
    Returns (is_safe: bool, clean_sql: str, reason: str).
    
    Rules enforced:
    1. Read-only query: Must start with SELECT or WITH.
    2. Forbidden keywords: Reject INSERT, UPDATE, DELETE, DROP, ALTER, etc.
    3. Multi-statement protection: Reject semicolon ';' separating statements.
    4. Comment protection: Reject '--' or '/* ... */' comment syntax used to mask code.
    5. Database Safety Cap: Caps execution limit to max_rows if exceeded or missing (for DB system protection).
    """
    if not sql or not sql.strip():
        return False, "", "Empty SQL query."

    # Normalize whitespace & uppercase for token check
    raw_sql = sql.strip()
    clean_sql = re.sub(r'\s+', ' ', raw_sql)

    # 1. Check for comments that could bypass parsing rules
    if "--" in clean_sql or "/*" in clean_sql or "*/" in clean_sql:
        return False, clean_sql, "SQL comments ('--' or '/*') are forbidden for security reasons."

    # 2. Check for multi-statement execution (semicolons outside string literals)
    # Strip string literals before checking semicolons
    no_strings_sql = re.sub(r"'[^']*'", "''", clean_sql)
    if ";" in no_strings_sql.rstrip(";"):
        return False, clean_sql, "Multiple SQL statements separated by semicolons are forbidden."

    # Strip single trailing semicolon if present
    clean_sql = clean_sql.rstrip(";").strip()

    # 3. Verify Read-Only Intent (Must begin with SELECT or WITH)
    upper_sql = clean_sql.upper()
    if not (upper_sql.startswith("SELECT ") or upper_sql.startswith("WITH ") or upper_sql == "SELECT"):
        return False, clean_sql, "Forbidden query type. Only SELECT queries are permitted."

    # 4. Check forbidden keywords using word boundary regex
    for keyword in FORBIDDEN_KEYWORDS:
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, upper_sql):
            return False, clean_sql, f"Forbidden SQL operation detected: '{keyword}' is strictly prohibited."

    # 5. Enforce Application Safety Cap (System Protection)
    limit_match = re.search(r'\bLIMIT\s+(\d+)\b', upper_sql)
    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit > max_rows:
            clean_sql = re.sub(r'\bLIMIT\s+\d+\b', f"LIMIT {max_rows}", clean_sql, flags=re.IGNORECASE)
    else:
        clean_sql = f"{clean_sql} LIMIT {max_rows}"

    return True, clean_sql, "Query passed all SQL safety validation checks."


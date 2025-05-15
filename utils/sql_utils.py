import json
import re
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any


def extract_json_from_llm_response(response: Any) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from an LLM response, which might contain text before or after the JSON.

    Args:
        response (str or dict): The LLM response that may contain or be JSON.

    Returns:
        dict or None: The extracted JSON data, or None if extraction failed.
    """
    if isinstance(response, dict):
        return response  # Already parsed
    
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Try to find a JSON object in the string
        json_match = re.search(r'({.*?})', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                return None
        return None


def format_sql_query(query: str) -> str:
    """
    Format a SQL query for better readability.

    Args:
        query (str): The SQL query to format.

    Returns:
        str: The formatted SQL query.
    """
    if not isinstance(query, str):
        raise TypeError(f"Expected a string, got {type(query).__name__} instead.")

    query = re.sub(r' +', ' ', query)  # Normalize spaces
    keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT']
    
    for keyword in keywords:
        pattern = rf'\b({keyword})\b'
        query = re.sub(pattern, r'\n\1', query, flags=re.IGNORECASE)
    
    # Add indentation for each line (except the first)
    lines = query.strip().split('\n')
    formatted_lines = [lines[0]] + ['  ' + line for line in lines[1:]]
    return '\n'.join(formatted_lines)

def validate_table_names(tables: List[str], available_tables: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate that table names exist in the available tables list.

    Args:
        tables (list): Table names to validate.
        available_tables (list): List of available table names.

    Returns:
        tuple: (valid_tables, invalid_tables)
    """
    upper_available = {t.upper() for t in available_tables}
    valid_tables = [t for t in tables if t.upper() in upper_available]
    invalid_tables = [t for t in tables if t.upper() not in upper_available]
    return valid_tables, invalid_tables


def log_query(user_query: str, generated_sql: str, timestamp: Optional[datetime] = None) -> None:
    """
    Log user queries and generated SQL for auditing and improvement.

    Args:
        user_query (str): The original natural language query.
        generated_sql (str): The generated SQL query.
        timestamp (datetime, optional): Query timestamp. Defaults to current time.
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    log_entry = {
        "timestamp": timestamp.isoformat(),
        "user_query": user_query,
        "generated_sql": generated_sql
    }

    # Simulate logging by printing (can be replaced with file or DB)
    print(f"[LOG] {json.dumps(log_entry)}")

    # To log to a file, uncomment the following:
    # with open("query_logs.jsonl", "a") as f:
    #     f.write(json.dumps(log_entry) + "\n")

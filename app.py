from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import logging
import traceback
import asyncio
import re
from datetime import datetime
# Import our agents
from agents.intent_agent import IntentAgent
from agents.table_agent import TableAgent
from agents.column_prune_agent import ColumnPruneAgent
from prompts.generate_prompts import QueryPromptGenerator
from retriever.sql_retriever import retrieve_similar_sql
from utils.sql_utils import extract_json_from_llm_response, format_sql_query, log_query
from db.db_pool import init_db_pool, get_connection
from metadata.schema_loader import SCHEMA_MAP, load_schema
from sql_examples import SQL_EXAMPLES
from agents.combined_agents import IntentAndTableAgent
# Define available tables from schema map
TABLES = list(SCHEMA_MAP.keys())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="QueryGPT API", description="Natural language to SQL query API")

# Request model
class QueryRequest(BaseModel):
    query: str
    debug: Optional[bool] = False

# Response model
class QueryResponse(BaseModel):
    sql: str
    explanation: str
    results: List[Dict[str, Any]] = []
    debug_info: Optional[Dict[str, Any]] = None

# Simple error response model
class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None

@app.on_event("startup")
async def startup():
    """Initialize database pool on app startup"""
    logger.info("Initializing database connection pool...")
    try:
        init_db_pool()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {str(e)}")
        # App will continue but DB operations will fail

# Initialize agents lazily when needed to prevent startup failures
intent_agent = None
table_agent = None
column_prune_agent = None
query_generator = None

# Replace intent_agent and table_agent initializations
intent_table_agent = None

def get_intent_table_agent():
    global intent_table_agent
    if intent_table_agent is None:
        intent_table_agent = IntentAndTableAgent()
    return intent_table_agent

def get_intent_agent():
    global intent_agent
    if intent_agent is None:
        intent_agent = IntentAgent()
    return intent_agent

def get_table_agent():
    global table_agent
    if table_agent is None:
        table_agent = TableAgent()
    return table_agent

def get_column_prune_agent():
    global column_prune_agent
    if column_prune_agent is None:
        column_prune_agent = ColumnPruneAgent()
    return column_prune_agent

def get_query_generator():
    global query_generator
    if query_generator is None:
        query_generator = QueryPromptGenerator()
    return query_generator

def oracle_date_syntax_fix(sql_query):
    """Fix Oracle date interval syntax in the SQL query"""
    # Fix MySQL DATE_SUB function to Oracle's ADD_MONTHS
    date_sub_pattern = r'DATE_SUB\s*\(\s*CURRENT_DATE\s*,\s*INTERVAL\s+(\d+)\s+MONTH\s*\)'
    sql_query = re.sub(date_sub_pattern, r'ADD_MONTHS(CURRENT_DATE, -\1)', sql_query)
    
    # Also handle a different pattern with DATE_SUB
    date_sub_alt_pattern = r'DATE_SUB\s*\(\s*CURRENT_DATE\s*,\s*INTERVAL\s+(\d+)\s+MONTH\)'
    sql_query = re.sub(date_sub_alt_pattern, r'ADD_MONTHS(CURRENT_DATE, -\1)', sql_query)
    
    # Handle standard interval pattern if DATE_SUB wasn't matched
    date_interval_pattern = r'CURRENT_DATE\s*-\s*INTERVAL\s+(\d+)\s+MONTH'
    sql_query = re.sub(date_interval_pattern, r'ADD_MONTHS(CURRENT_DATE, -\1)', sql_query)
    
    # Handle interval string patterns
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL '1 month'", "ADD_MONTHS(CURRENT_DATE, -1)")
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL '1 day'", "CURRENT_DATE - 1")
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL '7 day'", "CURRENT_DATE - 7")
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL '30 day'", "CURRENT_DATE - 30")
    
    # Handle interval keyword syntax
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL 1 DAY", "CURRENT_DATE - 1")
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL 7 DAY", "CURRENT_DATE - 7")
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL 30 DAY", "CURRENT_DATE - 30")
    sql_query = sql_query.replace("CURRENT_DATE - INTERVAL 1 MONTH", "ADD_MONTHS(CURRENT_DATE, -1)")
    
    return sql_query

def table_mapping_fix(sql_query):
    """Fix table names based on schema"""
    # Common table name mappings based on what users might ask for vs actual schema
    common_mappings = {
        "purchase_orders": "PO_NORM_TABLE_DUMMY",
        "purchase_order_items": "PO_LINE_TABLE_DUMMY",
        "purchase_order_invoices": "PO_INVOICE_DATA_DUMMY",
        "purchase_requisitions": "PR_DATA_DUMMY",
        "po": "PO_NORM_TABLE_DUMMY",
        "po_items": "PO_LINE_TABLE_DUMMY",
        "po_invoices": "PO_INVOICE_DATA_DUMMY",
        "pr": "PR_DATA_DUMMY"
    }
    
    # Apply the mappings
    for common_name, schema_name in common_mappings.items():
        # Replace full table name with schema name
        sql_query = re.sub(
            r'\b' + common_name + r'\b(?!\s+' + common_name + r'\b)',
            schema_name,
            sql_query
        )
        
        # Fix table with alias pattern (e.g., "purchase_orders po" -> "PO_NORM_TABLE_DUMMY po")
        for alias in ['po', 'poi', 'pr', 'inv']:
            pattern = f"{common_name}\\s+{alias}\\b"
            replacement = f"{schema_name} {alias}"
            sql_query = re.sub(pattern, replacement, sql_query)
    
    # Clean up any duplicate aliases that got created in the transformation
    for table in TABLES:
        sql_query = re.sub(r'' + table + r'\s+' + table + r'\b', table, sql_query)
    
    return sql_query

def clean_sql_for_oracle(sql_query):
    """Clean and prepare SQL for Oracle execution"""
    # Remove leading/trailing whitespace
    sql_query = sql_query.strip()
    
    # Remove trailing semicolons which cause ORA-00911
    if sql_query.endswith(';'):
        sql_query = sql_query[:-1]
    
    # Handle markdown-formatted SQL 
    if sql_query.startswith('```sql') and '```' in sql_query:
        # Extract SQL from markdown code block
        sql_parts = sql_query.split('```')
        if len(sql_parts) >= 3:
            sql_query = sql_parts[1]
            # Remove the "sql" language identifier if present
            if sql_query.lower().startswith('sql'):
                sql_query = sql_query[3:]
            sql_query = sql_query.strip()
            if sql_query.endswith(';'):
                sql_query = sql_query[:-1]
    
    # Fix Oracle date syntax
    sql_query = oracle_date_syntax_fix(sql_query)
    
    # Fix table mappings based on schema
    sql_query = table_mapping_fix(sql_query)
    
    # Fix column references if needed
    # This could be expanded based on common issues with column names
    
    return sql_query

@app.post("/generate_sql", response_model=QueryResponse, responses={500: {"model": ErrorResponse}})
async def generate_sql(request: QueryRequest):
    """
    Generate SQL from natural language query and execute it to return results
    """
    try:
        start_time = time.time()
        user_query = request.query
        debug_mode = request.debug
        debug_info = {}

        # Step 1 removed - Using default intent_data
        intent_data = {
            "operation_type": "SELECT",
            "possible_tables": [],
            "conditions": [],
            "aggregations": [],
            "intent_summary": user_query
        }
        if debug_mode:
            debug_info["intent_analysis"] = intent_data
            debug_info["available_tables"] = TABLES
            debug_info["schemas"] = {table: load_schema(table) for table in TABLES}

        print("Step 2: Identifying relevant tables")
        step_start = time.time()
        table_agent = get_table_agent()
        tables_response = table_agent.identify_tables(intent_data)
        tables_data = extract_json_from_llm_response(tables_response)
        if tables_data is None:
            logger.warning("Failed to parse tables response JSON, using fallback")
            tables_data = {
                "relevant_tables": TABLES[:2],
                "justification": "Fallback selection due to parsing error"
            }
        print(f"Step 2 completed in {time.time() - step_start:.2f} seconds")
        if debug_mode:
            debug_info["table_selection"] = tables_data

        print("Step 3: Selecting relevant columns")
        step_start = time.time()
        column_agent = get_column_prune_agent()
        columns_response = column_agent.prune_columns(intent_data, tables_data)
        columns_data = extract_json_from_llm_response(columns_response)
        if columns_data is None:
            logger.warning("Failed to parse columns response JSON, using fallback")
            columns_data = {
                "columns": {table: ["*"] for table in tables_data.get("relevant_tables", TABLES[:2])},
                "justification": "Fallback selection due to parsing error"
            }
        print(f"Step 3 completed in {time.time() - step_start:.2f} seconds")
        if debug_mode:
            debug_info["column_selection"] = columns_data

        print("Step 4: Retrieving similar SQL examples")
        step_start = time.time()
        try:
            if asyncio.iscoroutinefunction(retrieve_similar_sql):
                similar_sql = await retrieve_similar_sql(user_query)
            else:
                similar_sql = retrieve_similar_sql(user_query)
        except Exception as e:
            logger.error(f"Error retrieving similar SQL: {str(e)}")
            similar_sql = []
        print(f"Step 4 completed in {time.time() - step_start:.2f} seconds")
        if debug_mode:
            debug_info["similar_sql"] = similar_sql

        print("Step 5: Generating SQL query")
        step_start = time.time()
        query_gen = get_query_generator()
        schema_info = {table: load_schema(table) for table in tables_data.get("relevant_tables", [])}
        prompt_data = query_gen.generate_sql_prompt(
            user_query, intent_data, tables_data, columns_data, SQL_EXAMPLES,
            schema_info=schema_info
        )
        sql_query = query_gen.generate_sql(prompt_data)
        if isinstance(sql_query, dict):
            sql_query = sql_query.get("text", "")
            if not sql_query:
                raise ValueError("SQL query not found in the response dictionary")
        if not isinstance(sql_query, str):
            raise TypeError(f"Expected a string, got {type(sql_query).__name__} instead.")
        print(f"Step 5 completed in {time.time() - step_start:.2f} seconds")
        if debug_mode:
            debug_info["sql_query"] = sql_query

        print("Step 6: Formatting SQL query")
        step_start = time.time()
        formatted_sql = format_sql_query(sql_query)
        print(f"Step 6 completed in {time.time() - step_start:.2f} seconds")
        if debug_mode:
            debug_info["formatted_sql"] = formatted_sql

        original_sql = formatted_sql

        print("Step 7: Generating explanation")
        step_start = time.time()
        try:
            if asyncio.iscoroutinefunction(query_gen.generate_explanation):
                explanation = await query_gen.generate_explanation(user_query, formatted_sql)
            else:
                explanation = query_gen.generate_explanation(user_query, formatted_sql)

            if isinstance(explanation, dict):
                explanation = explanation.get("text", "")
                if not explanation:
                    raise ValueError("Explanation text not found in the response dictionary")
            if not isinstance(explanation, str):
                raise TypeError(f"Expected a string for explanation, got {type(explanation).__name__} instead.")
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            explanation = "An explanation could not be generated for this query."
        print(f"Step 7 completed in {time.time() - step_start:.2f} seconds")
        if debug_mode:
            debug_info["explanation"] = explanation

        print("Step 8: Executing SQL query")
        step_start = time.time()
        query_results = []
        try:
            connection = get_connection()
            cursor = connection.cursor()
            try:
                executable_sql = clean_sql_for_oracle(formatted_sql)
                print(f"Executing cleaned SQL with mapped table names: {executable_sql}")
                cursor.execute(executable_sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                for row in rows:
                    result = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        result[col] = value
                    query_results.append(result)
            finally:
                cursor.close()
                connection.close()
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            query_results = []
            if debug_mode:
                debug_info["query_execution_error"] = str(db_error)
                debug_info["attempted_sql"] = executable_sql
        print(f"Step 8 completed in {time.time() - step_start:.2f} seconds")
        if debug_mode:
            debug_info["query_results"] = query_results

        print(f"Total time taken: {time.time() - start_time:.2f} seconds")

        log_query(user_query, formatted_sql)

        return QueryResponse(
            sql=original_sql,
            explanation=explanation,
            results=query_results,
            debug_info=debug_info if debug_mode else None
        )

    except Exception as e:
        logger.error(f"Error generating SQL: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "Error generating SQL", "details": str(e)}
        )

@app.post("/execute_sql")
async def execute_sql(request: Request):
    """
    Execute a SQL query and return the results
    """
    try:
        data = await request.json()
        sql_query = data.get("sql")
        
        if not sql_query:
            return JSONResponse(
                status_code=400,
                content={"error": "SQL query is required"}
            )
        
        try:
            # Get a database connection
            connection = get_connection()
            cursor = connection.cursor()
            
            try:
                # Clean the SQL query for Oracle compatibility
                executable_sql = clean_sql_for_oracle(sql_query)
                
                # Execute the query
                cursor.execute(executable_sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                
                # Convert rows to list of dicts
                results = []
                for row in rows:
                    result = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Convert datetime objects to strings
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        result[col] = value
                    results.append(result)
                
                return JSONResponse(content={"results": results})
                
            finally:
                cursor.close()
                connection.close()
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            return JSONResponse(
                status_code=500,
                content={"error": "Database error", "details": str(db_error)}
            )
            
    except Exception as e:
        logger.error(f"Error executing SQL: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Error executing SQL", "details": str(e)}
        )

@app.get("/tables")
async def list_tables():
    """
    List available tables in the system
    """
    return {"tables": TABLES, "schemas": {table: load_schema(table) for table in TABLES}}

@app.get("/schema/{table_name}")
async def get_table_schema(table_name: str):
    """
    Get schema for a specific table
    """
    schema = load_schema(table_name)
    if schema == "No schema found.":
        return JSONResponse(
            status_code=404,
            content={"error": f"Schema for table '{table_name}' not found"}
        )
    return {"table": table_name, "schema": schema}

if __name__ == "__main__":
    import uvicorn
    import time  # Add import for time module
    uvicorn.run(app, host="0.0.0.0", port=9002)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import logging
import traceback

# Import our agents
from agents.intent_agent import IntentAgent
from agents.table_agent import TableAgent
from agents.column_prune_agent import ColumnPruneAgent
from prompts.generate_prompts import QueryPromptGenerator
from retriever.sql_retriever import retrieve_similar_sql
from utils.sql_utils import extract_json_from_llm_response, format_sql_query, log_query
from db.db_pool import init_db_pool, get_connection
from config import TABLES

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
import time

@app.post("/generate_sql", response_model=QueryResponse, responses={500: {"model": ErrorResponse}})
async def generate_sql(request: QueryRequest):
    """
    Generate SQL from natural language query
    """
    try:
        start_time = time.time()
        user_query = request.query
        debug_mode = request.debug
        debug_info = {}

        print("Step 1: Analyzing query intent")
        step_start = time.time()
        intent_agent = get_intent_agent()
        intent_response = intent_agent.analyze_intent(user_query)
        intent_data = extract_json_from_llm_response(intent_response)
        if intent_data is None:
            logger.warning("Failed to parse intent response JSON, using fallback")
            intent_data = {
                "operation_type": "SELECT",
                "possible_tables": [],
                "conditions": [],
                "aggregations": [],
                "intent_summary": user_query
            }
        print(f"Step 1 completed in {time.time() - step_start:.2f} seconds")

        if debug_mode:
            debug_info["intent_analysis"] = intent_data

        logger.info("Step 2: Identifying relevant tables")
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
        prompt_data = query_gen.generate_sql_prompt(
            user_query, intent_data, tables_data, columns_data, similar_sql
        )
        sql_query = query_gen.generate_sql(prompt_data)
        if isinstance(sql_query, dict):
            sql_query = sql_query.get("text", "")
            if not sql_query:
                raise ValueError("SQL query not found in the response dictionary")
        if not isinstance(sql_query, str):
            raise TypeError(f"Expected a string, got {type(sql_query).__name__} instead.")
        print(f"Step 5 completed in {time.time() - step_start:.2f} seconds")

        print("Step 6: Formatting SQL query")
        step_start = time.time()
        formatted_sql = format_sql_query(sql_query)
        print(f"Step 6 completed in {time.time() - step_start:.2f} seconds")

        print("Step 7: Generating explanation")
        step_start = time.time()
        try:
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

        print(f"Total time taken: {time.time() - start_time:.2f} seconds")

        # Log the query for auditing
        log_query(user_query, formatted_sql)

        # Return the response
        return QueryResponse(
            sql=formatted_sql,
            explanation=explanation,
            debug_info=debug_info if debug_mode else None
        )

    except Exception as e:
        logger.error(f"Error generating SQL: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "Error generating SQL", "details": str(e)}
        )

from datetime import datetime

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
                # Execute the query
                cursor.execute(sql_query)
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
    return {"tables": TABLES}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9002)
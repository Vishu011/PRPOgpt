# agents/intent_table_agent.py

from llm.llm_gateway import get_llm
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from retriever.sql_retriever import retrieve_similar_sql
from metadata.schema_loader import load_schema
from config import TABLES

class IntentAndTableAgent:
    def __init__(self):
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_template(
            """You are an intelligent SQL agent. Given a user query, perform the following:

            1. Understand the user’s intent.
            2. Identify SQL operation type (SELECT, INSERT, UPDATE, DELETE, etc.)
            3. Identify relevant tables and justify their relevance.
            4. Extract main entities, conditions, and aggregations.
            5. Only use the schema information provided.
            6. Do not assume any tables or columns that are not listed.

            *** DATABASE SCHEMA ***
            {available_tables}

            *** USER QUERY ***
            {query}

            *** SIMILAR SQL EXAMPLES ***
            {sql_examples}

            --- OUTPUT FORMAT ---
            {{
                "operation_type": "SELECT|INSERT|UPDATE|DELETE",
                "possible_tables": ["table1", "table2"],
                "conditions": ["..."],
                "aggregations": ["..."],
                "intent_summary": "Brief summary",
                "relevant_tables": ["table1", "table2"],
                "justification": "Why those tables were chosen"
            }}
            """
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def analyze_intent_and_tables(self, user_query):
        # Format schema
        available_tables = "\n".join(
            [f"- {table}: {load_schema(table).split('(')[0]}" for table in TABLES]
        )

        # Fetch similar SQL examples
        similar_sql = retrieve_similar_sql(user_query)
        sql_examples_text = "\n".join([f"Example {i+1}: {sql}" for i, sql in enumerate(similar_sql)])

        # Call LLM
        response = self.chain.invoke({
            "query": user_query,
            "available_tables": available_tables,
            "sql_examples": sql_examples_text
        })

        return response

from llm.llm_gateway import get_llm
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from config import TABLES

class QueryPromptGenerator:
    def __init__(self):
        self.llm = get_llm()
        
        # Prompt for generating the final SQL query
        self.sql_generation_prompt = ChatPromptTemplate.from_template(
            """You are an expert SQL developer tasked with writing a SQL query based on a user's request.
            
            User's natural language query: {user_query}
            
            Intent analysis:
            - Operation type: {operation_type}
            - Intent summary: {intent_summary}
            
            Tables to use:
            {table_schemas}
            
            Selected columns:
            {selected_columns}
            
            Similar SQL examples for reference:
            {sql_examples}
            
            Instructions:
            1. Write a syntactically correct SQL query that addresses the user's request
            2. Use only the tables and columns provided
            3. Make sure to handle joins correctly if multiple tables are used
            4. Add appropriate comments to explain complex parts of the query
            5. Format the query with proper indentation for readability
            
            Provide only the SQL query without any explanation:"""
        )
        
        # Prompt for generating the explanation
        self.explanation_prompt = ChatPromptTemplate.from_template(
            """You are an expert at explaining SQL queries to non-technical users.
            
            User's natural language query: {user_query}
            
            SQL query generated:
            ```sql
            {sql_query}
            ```
            
            Provide a clear, concise explanation of what this SQL query does in simple terms.
            Break down each part of the query (SELECT, FROM, WHERE, etc.) and explain its purpose.
            Avoid technical jargon when possible and focus on helping the user understand what data they will get from this query.
            
            Your explanation:"""
        )
        
        self.sql_chain = LLMChain(llm=self.llm, prompt=self.sql_generation_prompt)
        self.explanation_chain = LLMChain(llm=self.llm, prompt=self.explanation_prompt)
    
    def generate_sql_prompt(self, user_query, intent_data, tables_data, columns_data, sql_examples):
        """
        Generate a prompt for the SQL query generation
        
        Args:
            user_query (str): The original user's natural language query
            intent_data (dict): The intent analysis from IntentAgent
            tables_data (dict): The tables selected by TableAgent
            columns_data (dict): The columns selected by ColumnPruneAgent
            sql_examples (list): Similar SQL examples for reference
            
        Returns:
            dict: The prompt for SQL query generation
        """
        # Extract relevant data
        operation_type = intent_data.get("operation_type", "SELECT")
        intent_summary = intent_data.get("intent_summary", "")
        
        # Format table schemas
        relevant_tables = tables_data.get("relevant_tables", [])
        table_schemas_formatted = []
        
        for table in relevant_tables:
            selected_cols = columns_data.get("columns", {}).get(table, [])
            if selected_cols:
                cols_str = ", ".join(selected_cols)
                table_schemas_formatted.append(f"{table} ({cols_str})")
            else:
                table_schemas_formatted.append(table)
        
        table_schemas = "\n".join(table_schemas_formatted)
        
        # Format selected columns
        selected_columns_formatted = []
        for table, columns in columns_data.get("columns", {}).items():
            for col in columns:
                selected_columns_formatted.append(f"{table}.{col}")
        
        selected_columns = "\n".join(selected_columns_formatted)
        
        # Format SQL examples
        sql_examples_text = "\n".join([f"Example {i+1}: {sql}" for i, sql in enumerate(sql_examples)])
        
        return {
            "user_query": user_query,
            "operation_type": operation_type,
            "intent_summary": intent_summary,
            "table_schemas": table_schemas,
            "selected_columns": selected_columns,
            "sql_examples": sql_examples_text
        }
    
    def generate_sql(self, prompt_data):
        """Generate the SQL query using the prepared prompt"""
        return self.sql_chain.invoke(prompt_data)
    
    def generate_explanation(self, user_query, sql_query):
        """Generate an explanation for the SQL query"""
        return self.explanation_chain.invoke({
            "user_query": user_query,
            "sql_query": sql_query
        })
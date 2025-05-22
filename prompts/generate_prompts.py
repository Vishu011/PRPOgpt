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
            2. Write a syntactically correct SQL query for the given user request.
            3. Use only the tables and columns listed below in the "Schema Information".
            4. Do NOT use any tables or columns not explicitly listed.
            5. Join tables only if there are matching column names between them.
            6. Format your query cleanly.
            7. Do not assume or invent table names like 'invoices', 'suppliers', etc.
            9. Use only the tables and columns provided — do not invent or assume any table or column also You MUST NOT use any table that is not explicitly listed in the "Tables to use" section.
            10. Make sure to handle joins correctly if multiple tables are used
            11. Add appropriate comments to explain complex parts of the query
            12. Format the query with proper indentation for readability
            13. Ensure the query is optimized for performance
            14. For subquery SQL reserved word 'AS' is not syntactically valid following '....DELIVERED_AMOUNT > 100 so do not use it.
            15.  *** Use this TABLE information below to generate the SQL query , Do not take columns which do exist in a table refer following.
            The tables with their colomns and datatype in the database are:
                PO_INVOICE_DATA_DUMMY
                        PO_NUMBER VARCHAR2(26),
                        INVOICE_AMOUNT NUMBER(38,2),
                        INVOICE_NUM VARCHAR2(128),
                        PAID_AMOUNT NUMBER(38,2),
                        PAYMENT_NUMBER NUMBER(38),
                        CURRENCY_CODE VARCHAR2(26),
                        RECEIVED_QUANTITY NUMBER(38,2),
                        GRN_AMOUNT NUMBER(38,4),
                        GRN_NUMBER NUMBER(38),
                        GRN_STATUS VARCHAR2(26)

                PO_LINE_TABLE_DUMMY
                        PO_NUM VARCHAR2(256),
                        ORDERED_AMOUNT NUMBER(38,13),
                        INVOCIE_NUM VARCHAR2(128),
                        INVOICED_AMOUNT NUMBER(38,2),
                        LINE_NUM NUMBER(38),
                        CURRENCY_CODE VARCHAR2(26),
                        LINE_STATUS VARCHAR2(26),
                        ITEM_DESCRIPTION VARCHAR2(1024)

                PO_NORM_TABLE_DUMMY
                        PO_NUM VARCHAR2(256),
                        PO_CREATION_DATE DATE,
                        ORDERED_AMOUNT NUMBER(38,13),
                        RECEIVED_AMOUNT NUMBER(38,14),
                        DELIVERED_AMOUNT NUMBER(38,14),
                        INVOICED_AMOUNT NUMBER(38,2),
                        REQUISITION_NUMBER VARCHAR2(26),
                        JF_NUMBER VARCHAR2(26),
                        CURRENCY_CODE VARCHAR2(26),
                        PO_STATUS VARCHAR2(26),
                        DESCRIPTION VARCHAR2(1024),
                        SUPPLIER_NAME VARCHAR2(128)

                PR_DATA_DUMMY
                        REQUISTION_NO NUMBER(38),
                        CREATION_DATE DATE,
                        CREATED_BY VARCHAR2(26),
                        REQUISITION_STATUS VARCHAR2(26),
                        DEPARTMENT VARCHAR2(128)*****
            Provide only the SQL query without any explanation:"""
        )
        
        # Updated prompt for generating concise explanation with JSON structure
        self.explanation_prompt = ChatPromptTemplate.from_template(
            """You are an expert at explaining SQL queries to non-technical users.
            
            User's natural language query: {user_query}
            
            SQL query generated:
            ```sql
            {sql_query}
            ```
            
            Selected columns:
            {columns_json}
            
            Provide a concise explanation (3-5 sentences maximum) that:
            1. Directly answers the user's question in plain language
            2. Highlights only the most important data points the query will return
            3. Avoids SQL terminology where possible
            
            Your explanation should be brief but complete, focusing on exactly what information the user will receive.
            
            Your explanation:"""
        )
        
        self.sql_chain = LLMChain(llm=self.llm, prompt=self.sql_generation_prompt)
        self.explanation_chain = LLMChain(llm=self.llm, prompt=self.explanation_prompt)
    
    def generate_sql_prompt(self, user_query, intent_data, tables_data, columns_data, sql_examples, schema_info=None):
        """
        Generate a prompt for the SQL query generation
        
        Args:
            user_query (str): The original user's natural language query
            intent_data (dict): The intent analysis from IntentAgent
            tables_data (dict): The tables selected by TableAgent
            columns_data (dict): The columns selected by ColumnPruneAgent
            sql_examples (list): Similar SQL examples for reference
            schema_info (dict, optional): Additional schema information for tables
            
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
            # Include schema information if available
            if schema_info and table in schema_info:
                schema_details = schema_info[table]
                if isinstance(schema_details, str):
                    table_schemas_formatted.append(f"{table} - {schema_details}")
                else:
                    # Assuming schema_details might be a more complex structure
                    table_schemas_formatted.append(f"{table} - {str(schema_details)}")
            else:
                # Use the columns from columns_data
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
    
    def generate_explanation(self, user_query, sql_query, columns_data=None):
        """
        Generate a concise explanation for the SQL query with JSON column data
        
        Args:
            user_query (str): The original user's natural language query
            sql_query (str): The generated SQL query
            columns_data (dict): The columns data object
            
        Returns:
            dict: Explanation text and columns in JSON format
        """
        columns_json = "No specific columns selected"
        if columns_data and "columns" in columns_data:
            columns_json = str(columns_data["columns"])
            
        explanation_response = self.explanation_chain.invoke({
            "user_query": user_query,
            "sql_query": sql_query,
            "columns_json": columns_json
        })
        
        # Return both the explanation text and the columns in a structured format
        if isinstance(explanation_response, dict) and "text" in explanation_response:
            explanation_text = explanation_response["text"]
        else:
            explanation_text = explanation_response
            
        return {
            "text": explanation_text,
            "columns": columns_data.get("columns", {}) if columns_data else {}
        }
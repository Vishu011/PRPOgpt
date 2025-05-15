from llm.llm_gateway import get_llm
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from metadata.schema_loader import load_schema

class ColumnPruneAgent:
    def __init__(self):
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_template(
            """You are an agent tasked with selecting the most relevant columns for a SQL query based on the user's intent.
            
            Table schemas:
            {table_schemas}
            
            User's query intent: {intent_summary}
            Operation type: {operation_type}
            Conditions mentioned in intent: {conditions}
            Aggregations mentioned in intent: {aggregations}
            
            For each table, determine which columns should be included in the SQL query.
            Consider:
            1. Columns needed in the SELECT clause
            2. Columns needed for JOIN conditions (if multiple tables)
            3. Columns needed for WHERE conditions
            4. Columns needed for GROUP BY, ORDER BY, etc.
            
            Return your answer in JSON format:
            {{
                "columns": {{
                    "table1": ["col1", "col2"],
                    "table2": ["col1", "col3"]
                }},
                "justification": "Explanation of why these columns were selected"
            }}"""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def prune_columns(self, intent_data, tables_data):
        """
        Select the most relevant columns from the identified tables based on the user's intent
        
        Args:
            intent_data (dict): The user's query intent as analyzed by the IntentAgent
            tables_data (dict): The relevant tables as identified by the TableAgent
            
        Returns:
            dict: Selected columns for each table and justification
        """
        # Load schema for each relevant table
        relevant_tables = tables_data.get("relevant_tables", [])
        table_schemas = "\n\n".join([f"{table}:\n{load_schema(table)}" for table in relevant_tables])
        
        # Extract relevant data from intent
        intent_summary = intent_data.get("intent_summary", "")
        operation_type = intent_data.get("operation_type", "SELECT")
        conditions = ", ".join(intent_data.get("conditions", ["None specifically mentioned"]))
        aggregations = ", ".join(intent_data.get("aggregations", ["None specifically mentioned"]))
        
        # Get column recommendations from LLM
        response = self.chain.invoke({
            "table_schemas": table_schemas,
            "intent_summary": intent_summary,
            "operation_type": operation_type,
            "conditions": conditions,
            "aggregations": aggregations
        })
        
        return response
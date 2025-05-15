from llm.llm_gateway import get_llm
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from metadata.schema_loader import load_schema
from config import TABLES

class TableAgent:
    def __init__(self):
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_template(
            """You are an agent tasked with identifying the most relevant tables for a SQL query based on a user's intent.
            
            Available tables in the database:
            {available_tables}
            
            User's query intent: {intent_summary}
            Possible tables mentioned in intent: {possible_tables}
            
            Based on the intent and the available tables, determine which tables should be used in the SQL query.
            Do not include tables that don't exist in the available tables list.
            
            Return your answer in JSON format:
            {{
                "relevant_tables": ["table1", "table2"],
                "justification": "Explanation of why these tables were selected"
            }}"""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def identify_tables(self, intent_data):
        """
        Identify the most relevant tables based on the user's intent
        
        Args:
            intent_data (dict): The user's query intent as analyzed by the IntentAgent
            
        Returns:
            dict: A list of relevant tables and justification
        """
        # Get list of available tables
        available_tables = "\n".join([f"- {table}: {load_schema(table).split('(')[0]}" for table in TABLES])
        
        # Extract relevant data from intent
        intent_summary = intent_data.get("intent_summary", "")
        possible_tables = intent_data.get("possible_tables", [])
        
        # Convert possible_tables to string for the prompt
        possible_tables_str = ", ".join(possible_tables) if possible_tables else "None specifically mentioned"
        
        # Get table recommendations from LLM
        response = self.chain.invoke({
            "available_tables": available_tables,
            "intent_summary": intent_summary,
            "possible_tables": possible_tables_str
        })
        
        return response
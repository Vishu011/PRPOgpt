from llm.llm_gateway import get_llm
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from retriever.sql_retriever import retrieve_similar_sql

class IntentAgent:
    def __init__(self):
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_template(
            """You are an agent tasked with understanding the intent of a natural language query
            related to database operations. Based on the user's query, identify:
            
            1. The likely operation type (SELECT, INSERT, UPDATE, DELETE, etc.)
            2. The main entities/tables that might be involved
            3. Any conditions or filters mentioned
            4. Any aggregation or grouping operations requested
            
            User Query: {query}
            
            Similar SQL examples for reference:
            {sql_examples}
            
            Provide your analysis in JSON format:
            {{
                "operation_type": "SELECT|INSERT|UPDATE|DELETE",
                "possible_tables": ["table1", "table2"],
                "conditions": ["condition1", "condition2"],
                "aggregations": ["aggregation1", "aggregation2"], 
                "intent_summary": "Brief summary of what the user wants to do"
            }}"""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def analyze_intent(self, user_query):
        """
        Analyze the user's natural language query to understand the intent
        
        Args:
            user_query (str): The natural language query from the user
            
        Returns:
            dict: A structured representation of the user's intent
        """
        # Retrieve similar SQL examples to help with intent recognition
        similar_sql = retrieve_similar_sql(user_query)
        sql_examples_text = "\n".join([f"Example {i+1}: {sql}" for i, sql in enumerate(similar_sql)])
        
        # Get intent analysis from LLM
        response = self.chain.invoke({"query": user_query, "sql_examples": sql_examples_text})
        
        # The response is expected to be in JSON format as per the prompt
        # In a production system, you'd want to add error handling here
        return response
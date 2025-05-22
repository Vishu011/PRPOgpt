from llm.llm_gateway import get_llm
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain

# Direct schema import for simplicity
SCHEMA_MAP = {
    "PO_INVOICE_DATA_DUMMY": """PO_INVOICE_DATA_DUMMY(
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
    )""",
    "PO_LINE_TABLE_DUMMY": """PO_LINE_TABLE_DUMMY(
        PO_NUM VARCHAR2(256),
        ORDERED_AMOUNT NUMBER(38,13),
        INVOCIE_NUM VARCHAR2(128),
        INVOICED_AMOUNT NUMBER(38,2),
        LINE_NUM NUMBER(38),
        CURRENCY_CODE VARCHAR2(26),
        LINE_STATUS VARCHAR2(26),
        ITEM_DESCRIPTION VARCHAR2(1024)
    )""",
    "PO_NORM_TABLE_DUMMY": """PO_NORM_TABLE_DUMMY(
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
    )""",
    "PR_DATA_DUMMY": """PR_DATA_DUMMY(
        REQUISTION_NO NUMBER(38),
        CREATION_DATE DATE,
        CREATED_BY VARCHAR2(26),
        REQUISITION_STATUS VARCHAR2(26),
        DEPARTMENT VARCHAR2(128)
    )"""
}

def load_schema(table_name: str) -> str:
    """Fetches the schema for the given table name."""
    return SCHEMA_MAP.get(table_name.upper(), f"No schema found for {table_name}")

class ColumnPruneAgent:
    def __init__(self):
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_template(
            """You are an intelligent assistant tasked with selecting the most relevant columns from database tables based on the user's query intent.

Table schemas:
{table_schemas}

User's query intent: {intent_summary}
Operation type: {operation_type}
Conditions mentioned in intent: {conditions}
Aggregations mentioned in intent: {aggregations}

Based on the intent, choose the relevant columns for:
1. SELECT clause
2. JOIN conditions
3. WHERE conditions
4. GROUP BY, ORDER BY, etc.
5. DO not assume any columns by yourself are not mentioned in the intent only use schema information.
6. use only the columns mentioned in the schema information.
Return output in the following JSON format:
{{
    "columns": {{
        "table_name1": ["column1", "column2"],
        "table_name2": ["column3"]
    }},
    "justification": "Brief explanation of selected columns"
}}"""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def prune_columns(self, intent_data: dict, tables_data: dict) -> dict:
        """
        Identify and return the most relevant columns based on user's query intent.

        Args:
            intent_data (dict): Contains keys like 'intent_summary', 'conditions', 'aggregations', etc.
            tables_data (dict): Should contain a list of relevant tables under 'relevant_tables'.

        Returns:
            dict: {
                'columns': { 'table1': [...], 'table2': [...] },
                'justification': '...'
            }
        """
        relevant_tables = tables_data.get("relevant_tables", [])
        table_schemas = "\n\n".join([
            f"{table}:\n{load_schema(table)}"
            for table in relevant_tables
        ])

        intent_summary = intent_data.get("intent_summary", "No intent provided")
        operation_type = intent_data.get("operation_type", "SELECT")
        conditions = ", ".join(intent_data.get("conditions", ["None"]))
        aggregations = ", ".join(intent_data.get("aggregations", ["None"]))

        response = self.chain.invoke({
            "table_schemas": table_schemas,
            "intent_summary": intent_summary,
            "operation_type": operation_type,
            "conditions": conditions,
            "aggregations": aggregations
        })

        return response

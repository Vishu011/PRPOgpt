📌 Project Overview: Oracle GenAI-Powered SQL Assistant
This project is an intelligent, Oracle-integrated SQL generation and question-answering system powered by Oracle Generative AI, LangChain, and AI Vector Search. It allows users to ask natural language questions about their Oracle database, and the system responds with:

An optimized Oracle SQL query tailored to the question

A plain English explanation of the SQL logic

The executed result from the database

It supports dynamic schema loading, multi-table joins, and flexible scaling to new tables by automatically using metadata and vector-based semantic understanding.

To run your QueryGPT API in Postman, you'll need to follow these steps:
Step 1: Start Your API Server
First, make sure your FastAPI server is running:

Install required dependencies if you haven't already:

bashpip install fastapi uvicorn oracledb langchain langchain-community pydantic

Run your FastAPI application:

bashpython app.py
By default, your server will start on http://localhost:8000
Step 2: Set Up Postman

Open Postman
Create a new request

Step 3: Test the Generate SQL Endpoint

Set the request method to POST
Enter the URL: http://localhost:8000/generate_sql
Go to the Headers tab and add:

Key: Content-Type
Value: application/json


Go to the Body tab:

Select raw
Choose JSON from the dropdown
Enter your request body:



json{
  "query": "Show me all purchase orders created in the last month with total amount greater than 10000",
  "debug": true
}

Click Send

You should receive a response like this:
json{
  "sql": "SELECT po.PO_NUM, po.PO_CREATION_DATE, po.ORDERED_AMOUNT, po.SUPPLIER_NAME\nFROM PO_NORM_TABLE_DUMMY po\nWHERE po.PO_CREATION_DATE >= ADD_MONTHS(TRUNC(SYSDATE), -1)\nAND po.ORDERED_AMOUNT > 10000",
  "explanation": "This SQL query retrieves purchase orders created in the last month with a total amount over $10,000. It selects the purchase order number, creation date, ordered amount, and supplier name from the PO_NORM_TABLE_DUMMY table. The query filters for records where the creation date is within the last month and where the ordered amount exceeds 10,000.",
  "debug_info": {
    "intent_analysis": {
      "operation_type": "SELECT",
      "possible_tables": ["PO_NORM_TABLE_DUMMY"],
      "conditions": ["created in the last month", "total amount > 10000"],
      "aggregations": [],
      "intent_summary": "Find purchase orders created in the last month with total amount greater than 10000"
    },
    "table_selection": {
      "relevant_tables": ["PO_NORM_TABLE_DUMMY"],
      "justification": "PO_NORM_TABLE_DUMMY contains purchase order information including creation date and ordered amount"
    },
    "column_selection": {
      "columns": {
        "PO_NORM_TABLE_DUMMY": ["PO_NUM", "PO_CREATION_DATE", "ORDERED_AMOUNT", "SUPPLIER_NAME"]
      },
      "justification": "Selected columns contain the key information about purchase orders"
    },
    "similar_sql": [
      "SELECT * FROM PO_NORM_TABLE_DUMMY WHERE PO_CREATION_DATE >= '2023-01-01' AND ORDERED_AMOUNT > 5000",
      "SELECT PO_NUM, ORDERED_AMOUNT FROM PO_NORM_TABLE_DUMMY WHERE ORDERED_AMOUNT > 10000",
      "SELECT * FROM PO_NORM_TABLE_DUMMY WHERE PO_CREATION_DATE BETWEEN SYSDATE-30 AND SYSDATE"
    ]
  }
}
Step 4: Test the Execute SQL Endpoint

Create another request in Postman
Set the request method to POST
Enter the URL: http://localhost:8000/execute_sql
Go to the Headers tab and add:

Key: Content-Type
Value: application/json


Go to the Body tab:

Select raw
Choose JSON from the dropdown
Enter your request body with the SQL you want to execute:



json{
  "sql": "SELECT PO_NUM, PO_CREATION_DATE, ORDERED_AMOUNT, SUPPLIER_NAME FROM PO_NORM_TABLE_DUMMY WHERE ROWNUM <= 5"
}

Click Send

You should receive a response containing the query results:
json{
  "results": [
    {
      "PO_NUM": "PO-12345",
      "PO_CREATION_DATE": "2023-04-15T00:00:00",
      "ORDERED_AMOUNT": 15000.50,
      "SUPPLIER_NAME": "Acme Corp"
    },
    {
      "PO_NUM": "PO-12346",
      "PO_CREATION_DATE": "2023-04-16T00:00:00",
      "ORDERED_AMOUNT": 8500.25,
      "SUPPLIER_NAME": "XYZ Suppliers"
    }
    // More results...
  ]
}
Step 5: View Available Tables

Create another request in Postman
Set the request method to GET
Enter the URL: http://localhost:8000/tables
Click Send

You should receive a response listing all available tables:
json{
  "tables": [
    "PO_INVOICE_DATA_DUMMY",
    "PO_LINE_TABLE_DUMMY",
    "PO_NORM_TABLE_DUMMY",
    "PR_DATA_DUMMY"
  ]
}

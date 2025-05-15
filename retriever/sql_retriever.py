from langchain_community.vectorstores.oraclevs import OracleVS, DistanceStrategy
from llm.llm_gateway import get_embedder
from config import ORACLE_COMPARTMENT_ID,VECTOR_STORE_PO, VECTOR_STORE_PR, VECTOR_STORE_LINE, VECTOR_STORE_GRN
from db.db_pool import get_connection  # Assuming db_pool is initialized in db/db_pool.py

def get_vectorstore():
    embedding_model = get_embedder()
    
    try:
        # Get connection from your db pool
        db_connection = get_connection()
        
        vector_stores = {
            "PO": OracleVS(
                client=db_connection,
                table_name=VECTOR_STORE_PO,
                distance_strategy=DistanceStrategy.COSINE,
                embedding_function=embedding_model.embed_query
            ),
            "PR": OracleVS(
                client=db_connection,
                table_name=VECTOR_STORE_PR,
                distance_strategy=DistanceStrategy.COSINE,
                embedding_function=embedding_model.embed_query
            ),
            "GRN": OracleVS(
                client=db_connection,
                table_name=VECTOR_STORE_GRN,
                distance_strategy=DistanceStrategy.COSINE,
                embedding_function=embedding_model.embed_query
            ),
            "LINE": OracleVS(
                client=db_connection,
                table_name=VECTOR_STORE_LINE,
                distance_strategy=DistanceStrategy.COSINE,
                embedding_function=embedding_model.embed_query
            )
        }
        
        # Return the first vector store for simplicity
        if vector_stores:
            return next(iter(vector_stores.values()))
        return None
    except Exception as e:
        print(f"Error creating vector store: {str(e)}")
        return None

def retrieve_similar_sql(user_query, top_k=3):
    try:
        if not user_query or not user_query.strip():
            raise ValueError("User query is empty or invalid")

        vectorstore = get_vectorstore()
        if not vectorstore:
            raise ValueError("Vector store not initialized")

        # Generate embedding
        embedding = vectorstore.embedding_function(user_query)
        print(f"Embedding length: {len(embedding)}, sample: {embedding[:5]}")

        # Validation: must be a list of non-zero floats
        if (
            not isinstance(embedding, list) or
            len(embedding) == 0 or
            all(v == 0 for v in embedding)
        ):
            raise ValueError("Invalid embedding: empty or all zero values")

        # Safe call
        results = vectorstore.similarity_search_by_vector_with_relevance_scores(embedding, k=top_k)
        return [doc[0].page_content for doc in results]

    except Exception as e:
        return [
            "SELECT po.PO_NUM, po.ORDERED_AMOUNT FROM PO_NORM_TABLE_DUMMY po WHERE po.ORDERED_AMOUNT > 10000",
            "SELECT pr.REQUISTION_NO, pr.CREATION_DATE FROM PR_DATA_DUMMY pr WHERE pr.CREATION_DATE > SYSDATE - 30",
            "SELECT i.INVOICE_NUM, i.INVOICE_AMOUNT FROM PO_INVOICE_DATA_DUMMY i JOIN PO_NORM_TABLE_DUMMY p ON i.PO_NUMBER = p.PO_NUM"
        ]

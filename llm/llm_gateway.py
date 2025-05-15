from langchain_community.chat_models.oci_generative_ai import ChatOCIGenAI
from langchain_community.embeddings.oci_generative_ai import OCIGenAIEmbeddings
from config import ENDPOINT, EMBEDDING_MODEL, GENERATE_MODEL, ORACLE_COMPARTMENT_ID

def get_llm():
    """
    Get the Language Model client with proper configuration
    """
    try:
        return ChatOCIGenAI(
            model_id=GENERATE_MODEL, 
            service_endpoint=ENDPOINT,
            compartment_id=ORACLE_COMPARTMENT_ID  # Added compartment_id
        )
    except Exception as e:
        print(f"Error initializing LLM: {str(e)}")
        # Return a dummy LLM for testing
        from langchain.llms.fake import FakeListLLM
        return FakeListLLM(responses=["This is a placeholder response as the LLM service is unavailable."])

def get_embedder():
    """
    Get the Embedding Model client with proper configuration
    """
    try:
        return OCIGenAIEmbeddings(
            model_id=EMBEDDING_MODEL, 
            service_endpoint=ENDPOINT,
            compartment_id=ORACLE_COMPARTMENT_ID  # Added compartment_id
        )
    except Exception as e:
        print(f"Error initializing embedder: {str(e)}")
        # Return a simple embedding function for testing
        class SimpleEmbedder:
            def embed_query(self, text):
                # Return a simple embedding vector (not for production use)
                return [0.1] * 384
        return SimpleEmbedder()
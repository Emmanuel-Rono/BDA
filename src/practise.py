
import os

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langsmith import trace

load_dotenv()

documents = [
    Document(
        page_content="This is the content of the first document.",
        metadata={"source": "document1.txt"},
    ),
    Document(
        page_content="This is the content of the second document.",
        metadata={"source": "document2.txt"},
    ),
]

if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError("GOOGLE_API_KEY is not set.")

with trace(
    "generate-embeddings",
    run_type="chain",
    tags=["gemini", "embeddings"],
    metadata={"integration": "langchain_google_genai"},
):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vector_1 = embeddings.embed_query(documents[0].page_content)
    vector_2 = embeddings.embed_query(documents[1].page_content)

assert len(vector_1) == len(vector_2)

print(f"Generated vectors of length {len(vector_1)}")
print(vector_1[:10])



# load_dotenv()
# gemini_key = os.getenv("gemini_key")


# with trace (
#     "generate_embeddings",
#     run_type= "chain",
#     tags="",
#     metadata= ""
# ):
#     embeddings = GoogleGenerativeAIEmbeddings(model="")
#     vector1= embeddings.embed_query(documents[0].page_content)


    
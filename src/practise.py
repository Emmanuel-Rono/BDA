import os

from langchain_core.documents import Document
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings


documents = [
    Document(
        page_content="This is the content of the first document.",
        metadata={"source": "document1.txt"}
    ),
    Document (
        page_content="This is the content of the second document.",
        metadata={"source": "document2.txt"}

    ),
]

load_dotenv()

google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    raise RuntimeError(
        "GOOGLE_API_KEY is not set. Add it to .env in the repo root or set it in the shell."
    )

embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

vector_1 = embeddings.embed_query(documents[0].page_content)
vector_2 = embeddings.embed_query(documents[1].page_content)

assert len(vector_1) == len(vector_2)

print(f"Generated vectors of length {len(vector_1)}\n")
print(vector_1[:10])
    




from xml.dom.minidom import Document

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.embeddings import OllamaEmbeddings
from langchain_chroma import Chroma
import os
import pandas as pd


df = pd.read_csv("src/reviews.csv")
embeddings = OllamaEmbeddings(model="nomic-embed-text")
#Location of chroma db

db_location = "./chroma_ollama_db"

#Check if db exists, if not create and add documents
add_documents =  not os.path.exists(db_location)


if add_documents:
    documents = []
    ids=[]

    for i, row in df.iterrows():
        documents =Document(
            page_content=row["Title"] + " " + row["Review"],
            metadata={"rating" : row["Rating"], "date": row["Date"] },
            id = str(i)
        )

        ids.append(str(i))
        documents.append(documents)
         
vector_Db = Chroma(
    collection_name = "restaurant_reviews",
    embedding_function=embeddings,
    persist_directory=db_location
)


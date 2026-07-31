from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate


#Declare model
model = ChatOllama(model="llama2",temperature=0)
prompt = ChatPromptTemplate.from_messages([

    ("system", "You are a recommendar for restaurants in Kenya, recommend based on available ratings"),
    ("user", "{input}")
])

chain = prompt| model

response = chain.invoke({"input": "List 5 best veg hotels in nairobi"})
print (response.content)



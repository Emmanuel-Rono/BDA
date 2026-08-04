from operator import itemgetter

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from ragpractise import retriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

#Declare model
model = ChatOllama(model="llama2",temperature=0)
""" prompt = ChatPromptTemplate.from_messages([

    ("system", "You are a recommendar for restaurants, recommend based on available ratings and context{context} "),
    ("user", "{input}")
])
 """


prompt= ChatPromptTemplate.from_messages([
    ("system", "You are an expert recommender for restaurantss, recommend based on the given context here {context}"),
    ("user", "{input}")
])


chain= (
    #itemgetter is used to get the inout from user and pass it to the retriever to get context by using cosimilarity search. 
    #RunnablePassthrough is used to pass the initial user input as is to next step of the chain.
    #Now context will have the retriver output and input will have the user input.
    #We proceed to pipe both to the prompt, then to the model and finally output parser to get the content of response as a string.
    #This is what is called a chain in langchain, we are chaining together multiple steps to get the final output.
    {"context": itemgetter("input") | retriever, "input": RunnablePassthrough()}
    #Actual flow of the chain
    #Prompt with retriever context and user input, then pass to model, then parse output
    | prompt
    | model
    | StrOutputParser()
)

while True:
    print("\n\n-------------")
    quiestion = input("Ask a question: ")
    print("-------------\n\n")
    if quiestion.lower() == "q":
        break

#This actually does the  work for passing user input to the model and then get us back the response.

    response = chain.invoke({"input": quiestion})
    print (response)



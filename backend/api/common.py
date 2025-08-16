# common.py
from langchain_groq import ChatGroq  
from langchain_mistralai import ChatMistralAI
from langchain.prompts import PromptTemplate 
from langchain.schema.output_parser import StrOutputParser 
from langchain.schema.runnable import RunnablePassthrough  
from config import config
import re

# llm = ChatGroq(
#     groq_api_key=config.GROQ_API_KEY,
#     model_name=config.MODEL_NAME,
#     temperature=0.1
# )

llm = ChatMistralAI(
    mistral_api_key=config.MISTRAL_API_KEY,
    model=config.MODEL_NAME,  # Use model name from config (e.g. "mistral-large-latest")
    temperature=0.1
)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def run_chain(prompt_template, inputs):
    chain = RunnablePassthrough() | prompt_template | llm | StrOutputParser()
    return chain.invoke(inputs)

def get_prompt_template(use_case: str) -> PromptTemplate:
    if use_case == "generation":
        return PromptTemplate(
            input_variables=["context", "question"],
            template="""
            [INST] You are an expert assistant for policy analysis and compliance. 
            Answer ONLY using the provided context. If information is missing, state so.
            
            Context:
            {context}
            
            Question:
            {question}

            Guidelines:
            1. Be precise and professional
            2. Use bullet points for complex answers
            3. Never hallucinate information
            4. Reference section numbers when available [/INST]
            """
        )
    raise ValueError("Invalid use case")
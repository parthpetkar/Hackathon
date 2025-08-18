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
    if use_case == "irrigation":
        return PromptTemplate(
            input_variables=["context", "question"],
            template="""
            [INST] You are an agronomy and irrigation advisor. Provide practical guidance on crop watering, soil moisture, irrigation systems, schedules, and weather impacts.
            Use ONLY the provided context. If context lacks details, say what else is needed.

            Context:
            {context}

            Farmer's question:
            {question}

            Guidelines:
            - Prefer concise steps and clear thresholds (e.g., moisture %, mm of water)
            - Reference any field data or rules found in the context
            - If safety or compliance is relevant, highlight it
            - Avoid speculation; ask for missing data if necessary [/INST]
            """
        )
    if use_case == "general":
        return PromptTemplate(
            input_variables=["context", "question"],
            template="""
            [INST] You are a helpful general assistant. If the context is empty or irrelevant, answer succinctly from general knowledge, and note when the context doesn't apply.

            Context (may be empty):
            {context}

            Question:
            {question}

            Guidelines:
            - Be concise and correct
            - If specialized domain knowledge is needed, say so
            - If no context is available, do not fabricate citations [/INST]
            """
        )
    raise ValueError("Invalid use case")
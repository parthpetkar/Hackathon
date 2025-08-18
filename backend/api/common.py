# common.py
from langchain_groq import ChatGroq  
from langchain_mistralai import ChatMistralAI
from langchain.prompts import PromptTemplate 
from langchain.schema.output_parser import StrOutputParser 
from langchain.schema.runnable import RunnablePassthrough  
from config import config

# llm = ChatGroq(
#     groq_api_key=config.GROQ_API_KEY,
#     model_name=config.MODEL_NAME,
#     temperature=0.1
# )

llm = ChatMistralAI(
    mistral_api_key=config.MISTRAL_API_KEY,
    model=config.MODEL_NAME,  # e.g. "mistral-large-latest"
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

    if use_case == "weather":
        return PromptTemplate(
            input_variables=["context", "question"],
            template="""
            [INST] You are a weather and agricultural fieldwork advisor. Provide localized, practical forecasts and guidance on rainfall, temperature trends, wind, and storms.
            Base answers strictly on provided context and forecast data.

            Context:
            {context}

            Farmer's weather question:
            {question}

            Guidelines:
            - Always mention units (°C, mm rain, km/h wind)
            - Translate forecasts into farm actions (e.g., delay irrigation, prepare drainage)
            - If uncertainty exists, highlight risk ranges
            - Do not speculate without context [/INST]
            """
        )

    if use_case == "soil":
        return PromptTemplate(
            input_variables=["context", "question"],
            template="""
            [INST] You are a soil and water management advisor. Answer questions on soil moisture, soil temperature, and irrigation scheduling based on soil and weather data.

            Context:
            {context}

            Farmer's soil question:
            {question}

            Guidelines:
            - Use measurable values (e.g., % moisture, °C soil temperature)
            - Give irrigation timing in days or mm based on soil data
            - Recommend adjustments for soil type (clay, loam, sandy)
            - Highlight when more field data is required [/INST]
            """
        )

    if use_case == "uv":
        return PromptTemplate(
            input_variables=["context", "question"],
            template="""
            [INST] You are a UV index and sun safety advisor. Provide advice on outdoor work planning, protection, and safe exposure based on UV index.

            Context:
            {context}

            User's question:
            {question}

            Guidelines:
            - Report UV index clearly (0-11+ scale)
            - Suggest protective measures (hat, sunscreen, avoid noon hours)
            - Link UV intensity to outdoor farm safety and crop work
            - If data missing, ask for location or time [/INST]
            """
        )

    if use_case == "mandi":
        return PromptTemplate(
            input_variables=["context", "question"],
            template="""
            [INST] You are a mandi and commodity price advisor. Provide current and historical market rates, trends, and district/state price comparisons.

            Context:
            {context}

            Farmer's market query:
            {question}

            Guidelines:
            - Show price ranges (min, max, modal)
            - Specify commodity, market, district, state if available
            - Suggest when and where selling might be optimal
            - Do not fabricate numbers if context lacks data [/INST]
            """
        )

    raise ValueError("Invalid use case")

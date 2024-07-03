from dotenv import load_dotenv

load_dotenv()

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_openai import ChatOpenAI

llm_t0 = ChatOpenAI(model="gpt-4o", temperature=0)
llm_t1 = ChatOpenAI(model="gpt-4o", temperature=0.7, max_tokens=2048)

# Question Routing
router_prompt = PromptTemplate(
    template="You are an expert at routing a user question to a knowledge base or refusal to answer. \n"
    "Use the knowledge base search for questions on gene, disease, pathways, and gene ontology related. \n"
    "You do not need to be stringent with the keywords in the question related to these topics. \n"
    "Just decide to route the question to knowledge base or not. Give a binary choice 'knowledge_base' or 'refusal' based on the question. \n"
    "Return the a JSON with a single key 'routing' and no premable or explanation. \n"
    "Question to route: {question}",
    input_variables=["question"],
)

question_router_chain = router_prompt | llm_t0 | JsonOutputParser()

### Entity Extraction
entities_extractor_prompt = PromptTemplate(
    template="You are an expert at extract entities from a user question for a knowledge base search. "
    "The knowledge base cover the interaction information between genes and between genes and diseases or pathways. "
    "The traversal direction of the knowledge base is 'disease --> gene --> gene (in gene ontology terms). "
    "The gene related question would be either a 'upstream' search task or 'downstream' according to the traversal direction. \n\n"
    "Your task is to extract all the entities from the user question for a following search job. "
    "One single entity should be a JSON with three keys 'name', 'type' and 'traversal'. "
    "The key 'name' should be the unique name or symbol code for either a gene or a disease, which must be a single word which is the most identifiable and unique to be used as a search keyword. "
    "The key 'type' should be either 'gene' or 'disease' depending on the entity type. "
    "The key 'traversal' should be either 'upstream' or 'downstream' depending on the traversal direction. "
    "If no entities can be extract return JSON key 'entities' with empty list. \n\n"
    "The output should be a JSON with one single key 'entities' for extracted entities, which is a list of JSONs with three keys 'name', 'type' and 'traversal'. \n\n"
    "EXAMPLE \n"
    "Question: What are the diseases affected by the gene GKLM? \n"
    "Output: {{'entities': [{{'name': 'GKLM', 'type':'gene', 'traversal': 'upstream'}}]}} \n"
    "END OF EXAMPLE \n"
    "EXAMPLE \n"
    "Question: What are the genes affected by the disease CAD? \n"
    "Output: {{'entities': [{{'name': 'CAD', 'type':'disease', 'traversal': 'downstream'}}]}} \n"
    "END OF EXAMPLE \n"
    "EXAMPLE \n"
    "Question: What is the impact of gene GKLM in the disease CAD? \n"
    "Output: {{'entities': [{{'name': 'GKLM', 'type':'gene', 'traversal': 'downstream'}}, {{'entity': 'CAD', 'type':'map', 'traversal': 'downstream'}}]}} \n"
    "END OF EXAMPLE \n"
    "\nQuestion: {question} \nOutput: ",
    input_variables=["question"],
)

entities_extractor_chain = entities_extractor_prompt | llm_t0 | JsonOutputParser()

# Query Rewriter
rewriter_template = PromptTemplate(
    template="Look at the input and try to reason about the underlying semantic intent / meaning. \n"
    "Here is the initial question: \n ------- \n{question} \n ------- \n"
    "Formulate an improved question: ",
    input_variables=["question"],
)
rewriter_chain = rewriter_template | llm_t1 | StrOutputParser()

# RAG generation
rag_template = PromptTemplate(
    template="You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. "
    "The given content is prepared for biological or medical research purpose. Include all the relevant names or terms in the answer especially the ones od genes or diseases. "
    "It is fine to give potential effects or impacts for further research or investigation, but MUST state clearly for any hypothesis. "
    "If you don't know the answer, just say that you don't know. \n\n"
    "Question: {question} \n"
    "Context: {context} \n"
    "Answer: ",
    input_variables=["question", "context"],
)
rag_chain = rag_template | llm_t1 | StrOutputParser()

# Grounding Check
grounding_checker_template = PromptTemplate(
    template="You are an expert grader assessing whether an answer is grounded in supported by a set of facts. "
    "Give a binary 'yes' or 'no' score to indicate whether the answer is grounded in / supported by a set of facts. "
    "Provide the binary score as a JSON with a single key 'score' and no preamble or explanation. \n\n"
    "Here are the facts: \n ------- \n"
    "{context} \n ------- \n"
    "Here is the answer: {generation}",
    input_variables=["generation", "context"],
)
grounding_checker_chain = grounding_checker_template | llm_t0 | JsonOutputParser()

# Summarise
summarise_template = PromptTemplate(
    template="You are an expert for synthesizing information from multiple agents who have collected data on the same query from different sources. "
    "The query is for biological or medical research purpose. The final answer MUST include all the relevant names or terms especially the ones od genes or diseases. "
    "It is fine to give potential effects or impacts for further research or investigation, but MUST state clearly for any hypothesis. "
    "The finding from each agent may be partially useful for the query, and you aim to address the query based on the collection of findings which is delimited by '\n---\n'. "
    "Your goal is to create a comprehensive, coherent, and concise summary of their findings. \n\n"
    "Query: {question} \n"
    "Collection of findings: \n{findings}\n\n"
    "Instructions: \n"
    "1. Carefully review all the information provided by the agents. \n"
    "2. Identify the key genes or diseases with identifiable names or symbols. \n"
    "3. Synthesize the information into a cohesive summary. \n\n"
    "Please provide a well-structured summary that addresses the original query, incorporating insights from all agents."
    "Summary: ",
    input_variables=["question", "findings"],
)
summarise_chain = summarise_template | llm_t0 | StrOutputParser()

# Answer Relevance
answer_grader_template = PromptTemplate(
    template="You are a grader assessing whether an answer is useful to address the given question. "
    "Give a binary score 'yes' or 'no' to indicate whether the answer is useful to resolve a question. "
    "Provide the binary score as a JSON with a single key 'score' and no preamble or explanation. "
    "Here is the answer:\n ------- \n{generation}\n ------- \n"
    "Here is the question: {question} ",
    input_variables=["generation", "question"],
)
answer_grader_chain = answer_grader_template | llm_t0 | JsonOutputParser()

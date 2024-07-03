from typing import Annotated, List, TypedDict
from utils.chains import (
    question_router_chain,
    entities_extractor_chain,
    rewriter_chain,
    rag_chain,
    grounding_checker_chain,
    summarise_chain,
    answer_grader_chain,
)
from utils.knowledge_base import graph_search


### State
class AgentState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
    """

    question: str
    rewrite_flag: str
    extracted_entities: List[dict]
    context_list: List[str]
    findings: List[str]
    generation: str


### Node
def refuse_query(state):
    """
    Output Refusal due to irrelevant question received

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Appended refusal output to generation
    """

    print("---REFUSAL OUTPUT---")
    question = state.get("question")
    output = (
        "Sorry that I can not help with the given query below. "
        "The query may be irrelevant or the knowledge base does not contain sufficient information for related entities. "
        f"\n\nQuery: {question}"
    )
    rewrite_flag = state.get("rewrite_flag")
    if not rewrite_flag:
        rewrite_flag = "no"
    return {"generation": output, "question": question, "rewrite_flag": rewrite_flag}


### Node
def extract_entities(state):
    """
    Extract relevant entities from the question

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Appended extracted entities to state
    """
    print("---EXTRACT ENTITIES---")
    question = state.get("question")

    # extract entities
    extracted_entities = entities_extractor_chain.invoke(question)
    return {"extracted_entities": extracted_entities.get("entities")}


### Node
def search_knowledge_base(state):
    """
    Search the knowledge base for relevant information

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Appended context list to state
    """
    print("---SEARCH KNOWLEDGE BASE---")
    extracted_entities = state.get("extracted_entities")
    # search knowledge base
    context_list = []
    if extracted_entities:
        for entity in extracted_entities:
            # search knowledge base
            context = graph_search(entity["name"], entity["type"], entity["traversal"])
            if context:
                context_list.append(context)
    return {"context_list": context_list}


### Node
def generate(state):
    """
    Generate an answer based on the retrieved context

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Appended generated findings to state
    """
    print("---GENERATE ANSWER---")
    context_list = state.get("context_list")
    question = state.get("question")
    findings = []
    for context in context_list:
        # invoke RAG model
        findings.append(rag_chain.invoke({"question": question, "context": context}))
    return {"question": question, "findings": findings}


### Node
def grounding_check(state):
    """
    Check if the question is relevant to the given context

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Appended grounding check flag to state
    """
    print("---GROUNDING CHECK---")
    context_list = state.get("context_list")
    findings = state.get("findings")
    filtered_findings = []
    filtered_context = []
    for finding, context in zip(findings, context_list):
        # invoke grounding checker
        score = grounding_checker_chain.invoke(
            {"generation": finding, "context": context}
        )
        grade = score["score"]
        if grade == "yes":
            print("---GENERATION IS GROUNDED IN CONTEXT---")
            filtered_findings.append(finding)
            filtered_context.append(context)
        else:
            print("---GENERATION IS NOT GROUNDED IN CONTEXT---")
    print("---FINDINGS HAVE BEEN FILTERED---")
    return {"findings": filtered_findings, "context_list": filtered_context}


### Node
def summarise(state):
    """
    Summarise the findings

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Appended summary to state
    """
    print("---SUMMARISE FINDINGS---")
    question = state.get("question")
    findings = "\n---\n".join(state.get("findings"))
    summary = summarise_chain.invoke({"question": question, "findings": findings})
    extracted_entities = state.get("extracted_entities")
    context_list = state.get("context_list")
    return {
        "question": question,
        "generation": summary,
        "context_list": context_list,
        "extracted_entities": extracted_entities,
    }


### Node
def rewrite(state):
    """
    Rewrite the query

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Appended rewrite flag to state
    """
    print("---REWRITE QUERY---")
    question = state.get("question")
    # rewrite query
    question = rewriter_chain.invoke(question)
    rewrite_flag = "yes"
    return {"question": question, "rewrite_flag": rewrite_flag}


### Conditional edge
def route_question(state):
    """
    Route question to knowledge base or refusal.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """

    print("---ROUTE QUESTION---")
    question = state.get("question")
    print(question)
    decision = question_router_chain.invoke({"question": question})
    print(decision)
    if decision["routing"] == "refusal":
        print("---ROUTE QUESTION TO REFUSAL---")
        return "refusal"
    elif decision["routing"] == "knowledge_base":
        print("---ROUTE QUESTION TO KNOWLEDGE BASE---")
        return "knowledge_base"


### Conditional edge
def decide_to_generate(state):
    """
    Determines whether to generate an answer, or rewrite, or refuse.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """

    print("---ASSESS RETRIEVED CONTEXT---")

    if state.get("context_list"):
        # We have relevant documents, so generate answer
        print("---DECISION: GENERATE BASED ON CONTEXT---")
        return "generate"

    elif state.get("rewrite_flag") == "yes":
        # No context found with re-written query again
        print("---DECISION: REFUSAL---")
        return "refusal"

    else:
        # No related information found from knowledge base
        # We will re-write a new query
        print("---DECISION: NO CONTEXT FOUND FROM KB, REWRITE QUERY---")
        return "rewrite"


### Conditional edge
def decide_to_summarise(state):
    """
    Determines whether to summarise findings, or refuse, or rewrite.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """

    print("---ASSESS FILTERED FINDINGS---")

    if state.get("findings"):
        # We have grounding findings, then summarise
        print("---DECISION: SUMMARISE FINDINGS---")
        return "summarise"

    elif state.get("rewrite_flag") == "yes":
        # No solid findings with re-written query again
        print("---DECISION: REFUSAL---")
        return "refusal"

    else:
        # No solid finding generated based on context
        # We will re-write a new query
        print("---DECISION: NO SOLID FINDINGS, REWRITE QUERY---")
        return "rewrite"


### Conditional edge
def decide_to_output(state):
    """
    Determines whether to output answer or refuse or rewrite.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """
    print("---CHECK ANSWER RELEVANCE---")
    question = state.get("question")
    generation = state.get("generation")
    score = answer_grader_chain.invoke({"question": question, "generation": generation})
    grade = score["score"]
    if grade == "yes":
        print("---DECISION: OUTPUT ANSWER---")
        return "output"
    elif state.get("rewrite_flag") == "yes":
        print("---DECISION: REFUSAL---")
        return "refusal"
    else:
        print("---DECISION: REWRITE QUERY---")
        return "rewrite"


from langgraph.graph import START, END, StateGraph

workflow = StateGraph(AgentState)

# Define the nodes
workflow.add_node("node_refuse_query", refuse_query)
workflow.add_node("node_extract_entities", extract_entities)
workflow.add_node("node_search_knowledge_base", search_knowledge_base)
workflow.add_node("node_generate", generate)
workflow.add_node("node_grounding_check", grounding_check)
workflow.add_node("node_summarise", summarise)
workflow.add_node("node_rewrite", rewrite)

# Build Agent
workflow.add_conditional_edges(
    START,
    route_question,
    {
        "refusal": "node_refuse_query",  # Output Refusal due to irrelevant question received
        "knowledge_base": "node_extract_entities",  # Extract relevant entities from the question
    },
)
workflow.add_edge("node_extract_entities", "node_search_knowledge_base")
workflow.add_conditional_edges(
    "node_search_knowledge_base",
    decide_to_generate,
    {
        "generate": "node_generate",  # Generate based on retrieved context
        "refusal": "node_refuse_query",  # Output Refusal due to no context found
        "rewrite": "node_rewrite",  # Rewrite the query
    },
)
workflow.add_edge("node_rewrite", "node_extract_entities")
workflow.add_edge("node_generate", "node_grounding_check")
workflow.add_conditional_edges(
    "node_grounding_check",
    decide_to_summarise,
    {
        "summarise": "node_summarise",  # Summarise findings
        "refusal": "node_refuse_query",  # Output Refusal due to no solid findings
        "rewrite": "node_rewrite",  # Rewrite the query
    },
)
workflow.add_conditional_edges(
    "node_summarise",
    decide_to_output,
    {
        "output": END,  # Output the generated answer
        "refusal": "node_refuse_query",  # Output Refusal due to no answer found
        "rewrite": "node_rewrite",  # Rewrite the query
    },
)
workflow.add_edge("node_refuse_query", END)

agent = workflow.compile()

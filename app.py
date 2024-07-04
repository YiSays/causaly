from utils.agents import agent
import streamlit as st

st.title("PATHWAY AND DISEASE HYPOTHESIS GENERATION")
st.caption("developed by Xiaodong Yi 03-Jul-2024")

if "query" not in st.session_state:
    st.session_state.query = ""
if "output" not in st.session_state:
    st.session_state.output = {}


def clear():
    st.session_state.query = ""
    st.session_state.output = {}


input_option = st.radio(
    "Choose input option",
    ["Custom Query", "Query Examples"],
    horizontal=True,
    on_change=clear,
)
query_form = st.form("query form", clear_on_submit=True)
output_container = st.container()

with query_form:
    if input_option == "Custom Query":
        # Text input for custom query
        query = st.text_input("Enter your query here", key="query")
    else:
        examples = [
            "How does the mutation of the TP53 gene contribute to the development of multiple cancer types?",
            "What is the impact of the APOE ε4 allele on Alzheimer's disease progression?",
            "In which cellular pathways is the KRAS gene involved, and how do its mutations lead to cancer?",
            "Which neurological disorders are linked to mutations in the MECP2 gene?",
            "How to bake a cake?",
        ]
        query = st.selectbox("Select a pre-existing example", examples)
    submitted = st.form_submit_button("Query")
    if submitted:
        if query:
            with output_container:
                with st.status("Generating output..."):
                    for output in agent.stream({"question": query}):
                        for key, value in output.items():
                            st.info(f"Finished running: {key}")
            st.session_state.output = value
            st.session_state.generation = value.get("generation")

with output_container:
    if st.session_state.output:
        st.markdown(f"**Query:** {query}")
        st.markdown("**AGENT GENERATION:**")
        st.markdown(st.session_state.output.get("generation"))
        st.button("Clear", on_click=clear)
        if st.toggle("agent state"):
            st.json(st.session_state.output)

import os
import networkx as nx
import pandas as pd
import json
from typing import List
import xml.etree.ElementTree as ET
import requests
import gzip
import shutil

def download_goa_human_gaf(
        path:str='GO_data/Gene Ontology Human Annotations.gaf',
        url:str="https://current.geneontology.org/annotations/goa_human.gaf.gz"
):
    """
    Download the GOA Human GAF file from the Gene Ontology website.
    :param path: str path to save the file
    """
    # Download the gzip file
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        # Save the gzip file to a temporary location
        with open('temp.gz', 'wb') as f:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, f)
        
        # Unpack the gzip file
        with gzip.open('temp.gz', 'rb') as f_in:
            with open(path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        print(f"File successfully downloaded and unpacked to {path}")
        
        # Remove the temporary file
        os.remove('temp.gz')
    else:
        print(f"Failed to download file. Status code: {response.status_code}")

def load_goa_gaf(
    path:str='GO_data/Gene Ontology Human Annotations.gaf',
    target_columns:List[str]=['DB_Object_Symbol', 'DB_Object_Name', 'Qualifier', 'GO_ID', 'Aspect']
) -> pd.DataFrame:
    """
    Load GOA GAF file into a pandas dataframe
    :param path: str path to the GAF file
    :param target_columns: list(str) list of columns to load
    :return: pd.DataFrame
    """
    if not os.path.exists(path):
        download_goa_human_gaf(path)
    goa_df = pd.read_csv(path, sep="\t", comment='!', header=None)
    goa_df.columns = [
        "DB", "DB_Object_ID", "DB_Object_Symbol", "Qualifier",
        "GO_ID", "DB_Reference", "Evidence_Code", "With_From",
        "Aspect", "DB_Object_Name", "DB_Object_Synonym",
        "DB_Object_Type", "Taxon", "Date", "Assigned_By",
        "Annotation_Extension", "Gene_Product_Form_ID"
    ]
    goa_df = goa_df[target_columns]
    return goa_df

def load_goa_symbol_name_mapper(path:str='GO_data/goa_symbol_name_mapper.json') -> dict:
    '''
    Extract the symbol to name mapper from the GOA GAF file.
    When symbols have multiple names, select the one with the most counts.
    :param path: str path to the mapper file
    :return: dict
    '''
    if not os.path.exists(path):
        goa_df = load_goa_gaf()
        # Get the symbol to name by the most count
        goa_symbol_name_mapper = goa_df.groupby('DB_Object_Symbol')['DB_Object_Name'].apply(lambda x: x.value_counts().idxmax())
        # Save the mapper in JSON
        goa_symbol_name_mapper.to_json(path)
    with open(path, 'r') as f:
        goa_symbol_name_mapper = json.load(f)
    return goa_symbol_name_mapper

def prepare_graph_knowledge_base(path:str='graph.gml'):
    """
    Prepare the graph knowledge base by loading the GOA GAF file and KEGG KGML files,
    and creating a structured and directed graph representation of the knowledge base.
    :param path: str path to save the graph
    :return: networkx.DiGraph
    """
    symbol_name_mapper = load_goa_symbol_name_mapper()
    goa_df = load_goa_gaf().drop('DB_Object_Name', axis=1).drop_duplicates()
    goa_df['Aspect'] = goa_df['Aspect'].map(
        {'P': 'biological process',
        'C': 'cellular component',
        'F': 'molecular function'}
        )
    
    # get the list of paths of KEGG KGML xml files
    KEGG_file_list = []
    for dir, _, filename in os.walk('KEGG_data/KGML'):
        for file in filename:
            if file.endswith('.xml'):
                KEGG_file_list.append(os.path.join(dir, file))
    
    # Create a directed graph
    G = nx.DiGraph()

    for file_path in KEGG_file_list:
        tree = ET.parse(file_path)
        root = tree.getroot()
        # Add pathway information
        pathway_id = root.get('name')
        pathway_name = root.get('title')
        G.add_node(pathway_id, name=pathway_name, type='disease')

        entry_mapper = {}
        # Extract nodes
        for entry in root.findall('entry'):
            entry_id = entry.get('id')
            entry_name = entry.get('name') # e.g. hsa:5313
            entry_type = entry.get('type') # 3.g. gene
            graphics = entry.find('graphics')
            entry_symbol = graphics.get('name')
            if entry_type == 'gene':
                entry_symbol = entry_symbol.split(", ")[0] # e.g. PKLR
            if entry_symbol in symbol_name_mapper:
                if not G.has_node(entry_name):
                    G.add_node(entry_name, symbol=entry_symbol, name=symbol_name_mapper[entry_symbol], type=entry_type)
                for _, row in goa_df.loc[goa_df['DB_Object_Symbol'] == entry_symbol].iterrows():
                    if not G.has_node(row['GO_ID']):
                        G.add_node(row['GO_ID'], type='GO term', aspect=row['Aspect'])
                    if not G.has_edge(entry_name, row['GO_ID']):
                        G.add_edge(entry_name, row['GO_ID'], relation=row['Qualifier'])
            else:
                if not G.has_node(entry_name):
                    G.add_node(entry_name, symbol=entry_symbol, type=entry_type)
            G.add_edge(pathway_id, entry_name, relation='contains')
            entry_mapper[entry_id] = entry_name

        # Extract edges
        for relation in root.findall('relation'):
            entry1 = entry_mapper.get(relation.get('entry1'))
            entry2 = entry_mapper.get(relation.get('entry2'))
            relation_type = relation.get('type')
            # Extract subtypes if available
            sub_type = relation.find('subtype')
            if sub_type:
                relation_type += f' ({sub_type.get("name")})'
            if not G.has_edge(entry1, entry2):
                G.add_edge(entry1, entry2, relation=relation_type)
    
    # Save graph as a knowledge base
    nx.write_gml(G, path, stringizer=str)

def load_graph_knowledge_base(path:str='graph.gml') -> nx.DiGraph:
    """
    Load the graph knowledge base from a GML file.
    If the gml graph does not exist, execute prepare_graph_knowledge_base function to create.
    :param path: str path to the GML file
    :return: networkx.DiGraph
    """
    if not os.path.exists(path):
        prepare_graph_knowledge_base(path)
    graph = nx.read_gml(path, destringizer=str)
    return graph

# Graph Search
def graph_search(entity:str, type:str="gene", traversal:str="downstream") -> str:
    """
    Search knowledge based with a given entity and return a string with the context entities and relations
    :param entity: str
    :param type: str
    :param traversal: str
    :return: str
    """
    graph = load_graph_knowledge_base()
    # get clean keyword
    entity = entity.strip().strip("'s")
    # get all related nodes by string match
    entities = set(n[0] for n in graph.nodes(data=True) if entity in str(n) and n[1].get('type')==type)
    if not entities:
        return ""
    if traversal=="upstream":
        graph = graph.reverse()
    context_entities = set()
    context_relations = set()
    for entity in entities:
        for edge in nx.dfs_edges(graph, entity, 1):
            context_entities.add(f'{edge[0]}\t{graph.nodes[edge[0]]}')
            context_entities.add(f'{edge[1]}\t{graph.nodes[edge[1]]}')
            if not traversal=="upstream":
                context_relations.add(f'{edge[0]} --> |{graph.edges[edge].get('relation')}|> {edge[1]}')
            else:
                context_relations.add(f'{edge[1]} --> |{graph.edges[edge].get('relation')}|> {edge[0]}')
    
    return f'\nEntitties: \n'+'\n'.join(context_entities)+'\n\nRelations: \n'+'\n'.join(context_relations)

if __name__ == '__main__':
    download_goa_human_gaf()
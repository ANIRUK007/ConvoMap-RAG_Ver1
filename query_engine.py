import time
import json
import re
from dotenv import load_dotenv
import os
load_dotenv() # Loads the .env file

# --- Core LangChain Imports ---
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# --- Component Imports ---
from langchain_ollama import ChatOllama
from langchain_community.graphs import Neo4jGraph
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# --- Database Client (for direct fetching) ---
import chromadb

# --- CONFIGURATION ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD") # Your password from run_layer_2.py

# --- PART 1: CONNECT TO OUR 3 SERVICES ---

def get_llm(model_name="llama3"):
    """Connects to the local Ollama LLM."""
    print(f"Connecting to local LLM ({model_name})...")
    # Using 'mistral' as it's better for complex RAG
    return ChatOllama(model=model_name) 

def get_graph():
    """Connects to the Neo4j knowledge graph."""
    print("Connecting to Neo4j graph...")
    return Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD
    )

def get_vector_store():
    """Connects to the existing ChromaDB vector store."""
    print("Connecting to ChromaDB vector store...")
    # We need the original embedding model to create the retriever
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Connect to the persistent ChromaDB client
    vector_store = Chroma(
        persist_directory="./chroma_db_store",
        embedding_function=embeddings,
        collection_name="conversations"
    )
    return vector_store

def get_document_collection():
    """Gets the raw ChromaDB collection for direct ID-based fetching."""
    client = chromadb.PersistentClient(path="./chroma_db_store")
    return client.get_collection(name="conversations")

# --- PART 2: THE HYBRID RETRIEVAL LOGIC ---

def format_docs(docs):
    """Prepares the retrieved documents for the LLM prompt."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

def get_graph_context(query, graph, doc_collection, llm):
    """
    Step 1: Get context from the Knowledge Graph.
    - Uses the LLM to extract entities.
    - Queries Neo4j for *relationships* between those entities.
    - Fetches the raw documents for chunk_ids found on those relationships.
    """
    print("-> Retrieving graph context...")
    
    # 1. Entity Extraction Chain
    entity_prompt = ChatPromptTemplate.from_template(
        "You are an entity extractor. Extract up to 2 key entities (people, places, topics) "
        "from the following query. Format your response as a comma-separated list.\n\n"
        "Query: {query}\n"
        "Entities:"
    )
    entity_chain = entity_prompt | llm | StrOutputParser()
    
    try:
        entities_str = entity_chain.invoke(query)
        entities = [e.strip() for e in entities_str.split(",") if e.strip() and len(e) > 2] # simple filter
        
        if not entities:
            print("  > No key entities found by LLM.")
            return "" # No entities, no graph context
        
        print(f"  > Found entities: {entities}")

        # 2. Query Neo4j for relationships and chunk_ids
        
        # This is our new, smarter query.
        # It finds paths between the first two entities.
        if len(entities) == 1:
            # If only one entity, find chunks related to it
            graph_query = """
            MATCH (a:Entity)
            WHERE a.name CONTAINS $entity1
            // Find relationships *connected* to this entity
            MATCH (a)-[r]-() 
            RETURN r.chunk_id AS chunk_id
            """
            params = {"entity1": entities[0]}
        else:
            # If two or more entities, find paths *between* them
            graph_query = """
            MATCH (a:Entity), (b:Entity)
            WHERE a.name CONTAINS $entity1 AND b.name CONTAINS $entity2
            // Find the shortest path (up to 2 hops) between them
            MATCH p = allShortestPaths((a)-[*..2]-(b))
            // Unwind all relationships in that path
            UNWIND relationships(p) AS rel
            RETURN rel.chunk_id AS chunk_id
            """
            params = {"entity1": entities[0], "entity2": entities[1]}

        result = graph.query(graph_query, params)
        chunk_ids = list(set([r['chunk_id'] for r in result if r['chunk_id']])) # Use set for unique IDs
        
        if not chunk_ids:
            print("  > No matching chunks found in graph for that relationship.")
            return ""

        print(f"  > Found {len(chunk_ids)} related chunks in graph.")

        # 3. Fetch documents from Chroma by ID
        docs = doc_collection.get(ids=chunk_ids, include=["documents"])
        
        # Format for context
        return "\n\n---\n\n".join(docs['documents'])
        
    except Exception as e:
        print(f"  > Error in graph retrieval: {e}")
        return ""
    
def get_vector_context(query, vector_store):
    """
    Step 2: Get context from the Vector Store.
    - Performs a pure semantic search for the query.
    """
    print("-> Retrieving vector context...")
    # Create a retriever (k=3 fetches top 3 semantic matches)
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    
    # Invoke the retriever
    docs = retriever.invoke(query)
    
    # Format for context
    return format_docs(docs)

# --- PART 3: THE FINAL RAG CHAIN & INTERACTIVE LOOP ---

if __name__ == "__main__":
    try:
        # 1. Initialize all our components
        llm = get_llm(model_name="mistral")
        graph = get_graph()
        vector_store = get_vector_store()
        doc_collection = get_document_collection()
        print("\n✅ All systems connected. Query engine is ready.")
    except Exception as e:
        print(f"\n🔥 Failed to initialize components: {e}")
        print("Please ensure Ollama, Neo4j, and ChromaDB are all running.")
        exit()

    # 2. Define the final RAG prompt
    # This prompt takes the combined context and the query
    template = """
    You are a helpful assistant. Answer the user's question based *only* on the
    following context, which is composed of relevant chat messages.
    
    If the context is empty or does not contain the answer, just say
    "I'm sorry, I don't have enough information from your chats to answer that."

    CONTEXT:
    {context}

    QUERY:
    {query}

    ANSWER:
    """
    prompt = ChatPromptTemplate.from_template(template)

    # 3. Create the final synthesis chain
    final_chain = (
        {"context": RunnablePassthrough(), "query": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # 4. Start the interactive query loop
    print("\n--- ConvoMap Query Engine ---")
    print("Type 'exit' to quit.")
    while True:
        try:
            query = input("\nAsk your question: ")
            if query.lower() == 'exit':
                break
            if not query:
                continue

            start_time = time.time()
            
            # 5. RUN THE HYBRID RETRIEVAL
            print("Thinking...")
            
            # Step 1: Get Graph Context
            graph_context = get_graph_context(query, graph, doc_collection, llm)
            
            # Step 2: Get Vector Context
            vector_context = get_vector_context(query, vector_store)
            
            # Step 3: Combine contexts
            combined_context = f"--- GRAPH-BASED CONTEXT ---\n{graph_context}\n\n" \
                               f"--- SEMANTIC-BASED CONTEXT ---\n{vector_context}"
            
            # 6. RUN THE SYNTHESIS
            print("Synthesizing answer...")
            answer = final_chain.invoke({
                "context": combined_context,
                "query": query
            })
            
            end_time = time.time()
            
            print(f"\nANSWER:\n{answer}")
            print(f"(Retrieved and answered in {end_time - start_time:.2f} seconds)")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")

    print("Goodbye!")
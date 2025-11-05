import time
import ollama
from neo4j import GraphDatabase
import json
import re # We'll use this for parsing now
from dotenv import load_dotenv
import os
load_dotenv() # Loads the .env file

# --- PART 1: Neo4j Connection ---
# (This part is unchanged and works)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

class Neo4jManager:
    def __init__(self, uri, user, password):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            print("✅ Successfully connected to Neo4j.")
        except Exception as e:
            print(f"🔥 Error connecting to Neo4j. Is it running? {e}")
            exit()

    def close(self):
        self.driver.close()

    def add_triples_to_graph(self, chunk_id, triples):
        query = """
        UNWIND $triples as triple
        MERGE (s:Entity {name: triple[0]})
        ON CREATE SET s.chunk_id = $chunk_id
        
        MERGE (o:Entity {name: triple[2]})
        ON CREATE SET o.chunk_id = $chunk_id
        
        WITH s, o, triple
        CALL apoc.merge.relationship(s, triple[1], {}, {chunk_id: $chunk_id}, o)
        YIELD rel
        RETURN count(rel)
        """
        try:
            with self.driver.session() as session:
                session.run(query, triples=triples, chunk_id=chunk_id)
        except Exception as e:
            if "Unknown procedure" in str(e) and "apoc.merge.relationship" in str(e):
                print("\n" + "="*50)
                print("🔥 APOC PLUGIN ERROR! 🔥")
                print("Please check that the APOC plugin is installed and the database is restarted.")
                print("="*50 + "\n") 
                return False
            else:
                print(f"🔥 Error adding triples to Neo4j: {e}")
                return False
        return True

# --- PART 2: LLM Relation Extraction (NEW & IMPROVED) ---

# A simpler, more direct prompt
SYSTEM_PROMPT = """
You are an expert entity and relation extractor.
Extract (Subject, Predicate, Object) triples from the user's text.
The predicate must be a single verb in ALL_CAPS.
Output *only* a valid JSON list of lists. Do not add any other text, explanation, or markdown.
If no triples are found, output an empty list [].
"""

# --- THIS FUNCTION IS REWRITTEN ---
def extract_triples(text, ollama_client):
    """
    Calls the local Ollama model and *parses* the raw text response.
    """
    try:
        response = ollama_client.chat(
            model='mistral',
            # format='json',  <-- We removed this. We'll parse the text ourselves.
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': text}
            ]
        )
        
        # 1. Get the raw text content from the model
        raw_text = response['message']['content']
        
        # 2. Find the JSON list inside the raw text
        # The model might add '```json' or other text, so we'll find the list.
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        
        if not match:
            # The model didn't output a list. It might be empty or just text.
            if "[]" in raw_text:
                return [] # It explicitly found no triples
            print(f"  > 🟡 Warning: LLM returned no JSON list. Raw: {raw_text}")
            return []

        raw_json = match.group(0)
        
        # 3. Parse the JSON
        triples = json.loads(raw_json)
        
        # 4. Data validation (same as before)
        valid_triples = []
        if isinstance(triples, list):
            for item in triples:
                if isinstance(item, list) and len(item) == 3:
                    predicate = str(item[1]).upper().replace(" ", "_").replace("-", "_")
                    valid_triples.append([str(item[0]), predicate, str(item[2])])
        
        return valid_triples

    except json.JSONDecodeError:
        print(f"  > 🟡 Warning: LLM returned invalid JSON. Skipping chunk.")
        print(f"  > Raw output: {raw_json}")
        return []
    except Exception as e:
        print(f"  > 🔥 Error calling local LLM: {e}")
        return []

# --- PART 3: Main Execution (Unchanged) ---

if __name__ == "__main__":
    
    # 1. Connect to Neo4j
    graph_db = Neo4jManager(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    # 2. Connect to local Ollama server
    try:
        ollama_client = ollama.Client()
        ollama_client.list()
        print("✅ Successfully connected to local Ollama server.")
    except Exception as e:
        print("="*50)
        print("🔥 ERROR: Could not connect to Ollama.")
        print("Please make sure Ollama is installed and running.")
        print("="*50)
        exit()

    # 3. Load all conversation chunks
    try:
        with open('all_chunks.json', 'r', encoding='utf-8') as f:
            chunks = json.load(f)
    except FileNotFoundError:
        print("🔥 Error: all_chunks.json not found. Run parser.py first.")
        exit()

    print(f"Starting Layer 2 processing with local LLM...")
    print(f"Found {len(chunks)} chunks to process.")
    
    total_triples_found = 0
    BATCH_SIZE = 50 
    
    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i:i + BATCH_SIZE]
        
        print("\n" + "="*50)
        print(f"Processing Batch {i//BATCH_SIZE + 1}/~{len(chunks)//BATCH_SIZE} (Chunks {i+1} to {i+len(batch_chunks)})")
        print("="*50)

        for j, chunk in enumerate(batch_chunks):
            current_chunk_index = i + j + 1
            print(f"\n--- Processing Chunk {current_chunk_index}/{len(chunks)} (ID: {chunk['chunk_id']}) ---")
            
            text = chunk['raw_text']
            triples = extract_triples(text, ollama_client) 
            
            if not triples:
                print("  > No triples found by LLM.")
                continue
                
            print(f"  > 🟢 Extracted {len(triples)} triples:")
            for t in triples:
                print(f"    - ({t[0]}, {t[1]}, {t[2]})")
            
            total_triples_found += len(triples)
            
            if not graph_db.add_triples_to_graph(chunk['chunk_id'], triples):
                print("Stopping script due to Neo4j error.")
                break
        
        print(f"\n✅ Batch {i//BATCH_SIZE + 1} complete. Moving to next...")
            
    print("\n" + "="*50)
    print("✅ Layer 2 Processing Complete!")
    print(f"Total triples extracted: {total_triples_found}")
    print("="*50)
    
    graph_db.close()
    print("Neo4j connection closed.")
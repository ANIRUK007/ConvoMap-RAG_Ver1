import json
import chromadb
from sentence_transformers import SentenceTransformer

# 1. Load the pre-trained SBERT model
# This will download the model the first time you run it.
print("Loading SBERT model (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully.")

# 2. Set up the ChromaDB client and collection
# This will create a new folder 'chroma_db_store' to save the database
client = chromadb.PersistentClient(path="./chroma_db_store")

# Get or create a collection. This is like a "table" in SQL.
collection = client.get_or_create_collection(name="conversations")

# 3. Load your prepared data
print("Loading conversation chunks from all_chunks.json...")
try:
    with open('all_chunks.json', 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    print(f"Found {len(chunks)} chunks to process.")
except FileNotFoundError:
    print("Error: all_chunks.json not found.")
    print("Please make sure you ran the parser.py script first.")
    exit()

# 4. Process and ingest the data in batches
# This is much faster than adding them one by one.
batch_size = 100 
batches = [chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)]

print(f"Starting ingestion in {len(batches)} batches...")
total_processed = 0

for batch in batches:
    # Prepare the data for ChromaDB
    ids = []
    documents = []
    metadatas = []
    
    for chunk in batch:
        ids.append(chunk['chunk_id'])
        documents.append(chunk['raw_text'])
        
        # This metadata is CRITICAL for your Hybrid Search (Layer 3)
        # It allows you to filter by participants, dates, etc.
        metadatas.append({
            'source_file': chunk['source_file'],
            'participants': ", ".join(chunk['participants']), # ChromaDB prefers simple values
            'start_timestamp': chunk['start_timestamp'],
            'end_timestamp': chunk['end_timestamp']
        })

    # --- This is the key step ---
    # 1. Get the vector embeddings for the raw_text batch
    embeddings = model.encode(documents)
    
    # 2. Add the batch to the ChromaDB collection
    collection.add(
        embeddings=embeddings.tolist(), # The 768-dim vectors
        documents=documents,             # The raw_text
        metadatas=metadatas,             # The filterable data
        ids=ids                          # The unique chunk_id
    )
    
    total_processed += len(ids)
    print(f"Processed batch. Total chunks ingested: {total_processed}/{len(chunks)}")

print("\n--- Ingestion Complete ---")
print(f"✅ Successfully created and populated the vector database.")
print(f"Total chunks added: {collection.count()}")
print(f"Database is stored in the './chroma_db_store' directory.")
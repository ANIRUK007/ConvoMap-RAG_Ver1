import chromadb
import json

# 1. Connect to the existing persistent database
print("Connecting to existing database in './chroma_db_store'...")
client = chromadb.PersistentClient(path="./chroma_db_store")

# 2. Get the collection
try:
    collection = client.get_collection(name="conversations")
    print("Successfully connected to 'conversations' collection.")
except Exception as e:
    print(f"Error connecting to collection: {e}")
    print("Please make sure you have run 'embedder.py' first.")
    exit()

# 3. Get the total count
print(f"Total items in collection: {collection.count()}")

# 4. Retrieve a small sample of the data (e.g., the first 5 items)
print("\n--- Fetching first 5 items ---")
data = collection.get(
    limit=5,
    include=["metadatas", "documents"]  # Ask for metadata and the text
)

# 5. Pretty-print the data
if data:
    for i in range(len(data['ids'])):
        print("\n" + "="*30)
        print(f"CHUNK ID: {data['ids'][i]}")
        print("\nMETADATA:")
        # Use json.dumps for nice formatting of the metadata dictionary
        print(json.dumps(data['metadatas'][i], indent=2))
        print("\nDOCUMENT (raw_text):")
        print(data['documents'][i])
        print("="*30)
else:
    print("No data found in the collection.")
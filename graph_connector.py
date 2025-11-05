from neo4j import GraphDatabase

# --- CONFIGURATION ---
# Default Neo4j connection URI
NEO4J_URI = "bolt://localhost:7687" 
# The password you set when you created the "convo-graph" instance
NEO4J_PASSWORD = "Anirudh@123"
# Default user is always 'neo4j'
NEO4J_USER = "neo4j"

# A class to manage our graph connection
class Neo4jManager:
    def __init__(self, uri, user, password):
        # Connect to the database
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Attempting to connect to Neo4j...")

    def close(self):
        # Always close the connection when done
        self.driver.close()

    def test_connection(self):
        # A simple query to verify the connection is live
        with self.driver.session() as session:
            try:
                result = session.run("RETURN 'Connection Successful!' AS message")
                print(f"Neo4j Result: {result.single()['message']}")
                return True
            except Exception as e:
                print(f"Connection failed. Error: {e}")
                print("Please check your NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD.")
                return False

    def setup_index(self):
        # This is CRITICAL for your "Vector-Graph Linkage"
        # It creates an index on the 'chunk_id' property for all nodes
        # that have the label "Entity".
        print("Setting up 'chunk_id' index on :Entity label...")
        
        # --- THIS IS THE CORRECTED QUERY ---
        query = "CREATE INDEX chunk_id_index IF NOT EXISTS FOR (n:Entity) ON (n.chunk_id)"
        
        with self.driver.session() as session:
            try:
                session.run(query)
                print("Index 'chunk_id_index' is ready.")
            except Exception as e:
                print(f"Error creating index: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # IMPORTANT: Update this with your real password
    if NEO4J_PASSWORD == "YOUR_PASSWORD_HERE":
        print("="*50)
        print("ERROR: Please update the NEO4J_PASSWORD variable in the script.")
        print("="*50)
    else:
        # Create the manager and test the connection
        graph_db = Neo4jManager(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        
        if graph_db.test_connection():
            # If connection works, set up the index
            graph_db.setup_index()
            
        graph_db.close()
        print("Connection closed.")
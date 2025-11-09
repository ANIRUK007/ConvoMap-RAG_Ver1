## 🗺️ ConvoMap: A Hybrid RAG Knowledge Engine

This project is an advanced, hybrid Retrieval-Augmented Generation (RAG) system designed to turn messy, unstructured chat logs (like WhatsApp `.txt` exports) into a queryable, intelligent knowledge base.

It combines the power of semantic vector search with the precision of a structured knowledge graph, allowing you to ask complex questions about your personal conversations and get synthesized, context-aware answers.

---

## 🏛️ Core Architecture

This system is built on a "dual-store" architecture, managed by three distinct layers.



* **Layer 1: Ingestion & Embedding Pipeline**
    * **Input:** Raw `.txt` chat files.
    * **Process:** Parses, cleans, and segments conversations into coherent "chunks" based on time gaps.
    * **Output:** Generates SBERT vector embeddings for each chunk and stores them in a **ChromaDB** vector database.

* **Layer 2: Knowledge Graph Construction**
    * **Input:** The text chunks from Layer 1.
    * **Process:** An asynchronous script feeds each chunk's text to a local, open-source LLM (via **Ollama**) to perform relation extraction.
    * **Output:** Extracts `(Subject, Predicate, Object)` triples (e.g., `('Divyansi', 'DISCUSSED', 'IEEE Project')`) and populates a **Neo4j** graph database.
    * **The "Magic":** Every node and relationship in the graph is tagged with the `chunk_id` it came from, creating the critical link between the graph and vector stores.

* **Layer 3: Hybrid Retrieval & Synthesis**
    * **Input:** A user's natural language query (e.g., "What did Divyansi and I discuss about IEEE?").
    * **Process:** A **LangChain** orchestrator queries the Neo4j graph *first* to find the "hot" `chunk_ids` related to "Divyansi" and "IEEE." It then performs a semantic search in ChromaDB *only* within that pre-filtered set.
    * **Output:** The final, relevant context is fed to a local LLM, which synthesizes a human-readable answer.

---

## 🛠️ Tech Stack

* **Orchestration:** LangChain
* **LLM (Local):** Ollama (running `mistral` or `llama3`)
* **Vector Database:** ChromaDB (file-based)
* **Graph Database:** Neo4j (with APOC plugin)
* **Embeddings:** `sentence-transformers` (`all-MiniLM-L6-v2`)
* **Core Toolkit:** `neo4j`, `ollama`, `langchain-community`, `langchain-core`, `python-dotenv`

---

## 🚀 How to Run This Project

### 1. Setup & Installation

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/YourUsername/ConvoMap-RAG.git](https://github.com/YourUsername/ConvoMap-RAG.git)
    cd ConvoMap-RAG
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

3.  **Install Local Services (Mandatory):**
    * **Ollama:** Install from [ollama.com](https://ollama.com/).
        * Run `ollama run mistral` to download the model.
    * **Neo4j Desktop:** Install from [neo4j.com/download](https://neo4j.com/download/).
        * Create a new local database (e.g., `convo-graph`).
        * Set a password (you'll need this in a moment).
        * Start the database, go to the "Plugins" tab, and **install the APOC plugin**.
        * **Restart** the database after installing the plugin.

4.  **Install Python Dependencies:**
    * First, create a `requirements.txt` file by running this in your terminal:
        ```powershell
        pip freeze > requirements.txt
        ```
    * (In the future, a new user would just run: `pip install -r requirements.txt`)

5.  **Set Up Secret Variables:**
    * Create a file named `.env` in the root folder.
    * Add your Neo4j password to it. The `.gitignore` file will prevent this from ever being uploaded.
    ```env
    # .env file
    NEO4J_PASSWORD="Your-Neo4j-Password-Here"
    ```

### 2. Running the Data Pipeline

You must run these scripts **in order**.

1.  **Place Your Data:**
    * Put all your exported WhatsApp `.txt` files into the `Raw Chat Data WA/` folder.

2.  **Run Layer 1 (Parsing & Embedding):**
    * **Parse & Segment:**
        ```powershell
        python parser.py
        ```
        * **Output:** Creates `all_chunks.json`.
    * **Embed & Store in ChromaDB:**
        ```powershell
        python embedder.py
        ```
        * **Output:** Creates the `chroma_db_store/` folder.

3.  **Run Layer 2 (Graph Construction):**
    * **Extract & Store in Neo4j:**
        ```powershell
        python run_layer_2.py
        ```
        * **Output:** Populates your Neo4j database. This will take time as it processes all chunks with your local GPU.

### 3. Running the Query Engine

Once the pipeline has been run, you can query your data at any time.

1.  **Start the Engine:**
    ```powershell
    python query_engine.py
    ```
2.  **Ask Questions:**
    * It will connect to all services and give you a prompt.
    * `Ask your question: What did Divyansi say about the IEEE project?`

---

## 🗺️ V2 Roadmap (Future Work)

This V1 prototype proves the hybrid architecture works. The next steps for a production-grade system would be:

* **Layer 1.5 (Translation):** The current system struggles with "Hinglish" or "Telugish" as the LLMs are English-first. A new layer would be added to translate all non-English chunks *before* they are sent for embedding and extraction.
* **Multi-Modal Support:** Expand the `parser.py` to connect to vision models (to describe images) or speech-to-text models (to transcribe audio), turning media into searchable text.
* **Smarter Entity Extraction:** The current LLM prompt is good, but a fine-tuned local model would provide far more accurate and consistent (Subject, Predicate, Object) triples.**

import os
import time
import click
from datetime import datetime, timedelta
from typing import List, Dict, TypedDict
from apscheduler.schedulers.blocking import BlockingScheduler

# LangChain / LangGraph Imports
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_text_splitters import CharacterTextSplitter
from langgraph.graph import StateGraph, END

# --- CONFIGURATION ---
# We point to the internal docker hostname 'ollama_service'
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama_service:11434")
MODEL_NAME = "llama3.2"

print(f"Initializing Guardian with Local Model: {MODEL_NAME} at {OLLAMA_BASE_URL}")

# --- 1. DATA ABSTRACTION LAYER (Unchanged) ---
class TransactionAdapter:
    def get_pending_transactions(self) -> List[Dict]:
        return [
            {
                "id": "INV-2024-001",
                "vendor": "Tech Solutions Ltd",
                "date": "2024-11-01",
                "items": "Senior Engineering Services (10 days)",
                "amount": 12000.00,
                "currency": "USD",
                "status": "Pending",
                "meta": "Weekend work included: No"
            },
            {
                "id": "INV-2024-002",
                "vendor": "Tech Solutions Ltd",
                "items": "Travel Expenses",
                "amount": 850.00, 
                "status": "Pending",
                "meta": "No pre-approval attached"
            }
        ]

# --- 2. LOCAL KNOWLEDGE BASE ---
def setup_vector_store():
    """Ingests contract data using Local Embeddings."""
    # Wait for Ollama to be ready (naive check)
    print("Waiting for Ollama to wake up...")
    time.sleep(5) 

    if not os.path.exists("contracts_mock.md"):
        text = "Standard rate $100. Net 30."
    else:
        with open("contracts_mock.md", "r") as f:
            text = f.read()

    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=0)
    docs = text_splitter.create_documents([text])
    
    # Switch to Ollama Embeddings (Runs locally on CPU)
    embeddings = OllamaEmbeddings(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL
    )
    
    # Initialize ChromaDB
    db = Chroma.from_documents(docs, embeddings, collection_name="contracts_local")
    return db

# --- 3. AGENT DEFINITIONS ---

class AgentState(TypedDict):
    transaction: Dict
    contract_clauses: List[str]
    analysis_report: str
    email_draft: str

class CommercialGuardianAgent:
    def __init__(self):
        # Switch to ChatOllama
        self.llm = ChatOllama(
            model=MODEL_NAME,
            temperature=0,
            base_url=OLLAMA_BASE_URL
        )
        self.vector_store = setup_vector_store()
    
    def retrieve_contract_terms(self, state: AgentState):
        tx = state["transaction"]
        query = f"Payment terms, rates, and expenses for {tx['vendor']}"
        results = self.vector_store.similarity_search(query, k=3)
        return {"contract_clauses": [doc.page_content for doc in results]}

    def analyze_compliance(self, state: AgentState):
        tx = state["transaction"]
        clauses = "\n\n".join(state["contract_clauses"])
        
        # Simpler prompt for smaller models to ensure they follow instructions
        prompt = f"""
        ACT AS: Commercial Auditor.
        TASK: Check if the INVOICE violates the CONTRACT.
        
        CONTRACT:
        {clauses}
        
        INVOICE:
        Vendor: {tx['vendor']}
        Item: {tx['items']}
        Amount: {tx['amount']}
        Meta: {tx['meta']}
        
        OUTPUT format:
        - Status: [COMPLIANT or NON-COMPLIANT]
        - Issue: [Explain discrepancy if any]
        - Action: [Approve or Dispute]
        """
        
        response = self.llm.invoke(prompt)
        return {"analysis_report": response.content}

    def draft_communications(self, state: AgentState):
        report = state["analysis_report"]
        tx = state["transaction"]
        
        prompt = f"""
        Draft a short email to vendor {tx['vendor']} regarding Invoice {tx['id']}.
        Use this audit result:
        {report}
        """
        
        response = self.llm.invoke(prompt)
        return {"email_draft": response.content}

    def build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("retrieve", self.retrieve_contract_terms)
        workflow.add_node("audit", self.analyze_compliance)
        workflow.add_node("draft", self.draft_communications)
        
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "audit")
        workflow.add_edge("audit", "draft")
        workflow.add_edge("draft", END)
        
        return workflow.compile()

# --- 4. RUNNER ---
def batch_process():
    print(f"--- Starting Local Audit Cycle {datetime.now()} ---")
    adapter = TransactionAdapter()
    transactions = adapter.get_pending_transactions()
    
    agent = CommercialGuardianAgent()
    app = agent.build_graph()
    
    for tx in transactions:
        print(f"\nProcessing: {tx['id']}")
        res = app.invoke({
            "transaction": tx, 
            "contract_clauses": [], 
            "analysis_report": "", 
            "email_draft": ""
        })
        print(f"RESULT: {res['analysis_report']}")
        print(f"EMAIL: {res['email_draft']}")

@click.group()
def cli(): pass

@cli.command()
def run_now():
    batch_process()

if __name__ == "__main__":
    cli()
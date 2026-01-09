import os
import time
import pandas as pd
import io
import click

# --- MODERN IMPORTS ---
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import CharacterTextSplitter
from langchain_core.documents import Document

# --- CONFIG ---
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama_service:11434")
MODEL_NAME = "llama3.2"

class DataLoader:
    @staticmethod
    def load_contracts():
        documents = []
        paths = ["/app/data/contracts", "/app/data/Contracts"]
        contract_path = next((p for p in paths if os.path.exists(p)), None)
        
        if not contract_path:
            return []
            
        for filename in os.listdir(contract_path):
            if filename.endswith(".md"):
                path = os.path.join(contract_path, filename)
                with open(path, "r") as f:
                    text = f.read()
                    documents.append(Document(page_content=text, metadata={"source": filename}))
        return documents

    @staticmethod
    def load_invoices():
        possible_paths = [
            "/app/data/transactions/invoices.csv",
            "/app/data/transactions/Transactions.csv",
            "/app/data/Transactions/Transactions.csv"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8-sig') as f:
                        lines = f.readlines()
                    
                    cleaned_lines = []
                    for line in lines:
                        line = line.strip()
                        if line.startswith('"') and line.endswith('"') and "," in line:
                             line = line[1:-1].replace('""', '"')
                        cleaned_lines.append(line)
                    
                    data_str = "\n".join(cleaned_lines)
                    df = pd.read_csv(io.StringIO(data_str), sep=',')
                    
                    df.columns = df.columns.str.strip().str.lower().str.replace('"', '').str.replace('\ufeff', '')
                    
                    raw_records = df.to_dict('records')
                    clean_records = []
                    for row in raw_records:
                        clean_row = {k.strip().lower(): v for k, v in row.items()}
                        clean_records.append(clean_row)
                        
                    return clean_records
                except Exception as e:
                    print(f"{RED}Error reading CSV: {e}{RESET}")
        return []

class CommercialGuardianAgent:
    def __init__(self):
        print(f"{YELLOW}Initializing Neural Engine ({MODEL_NAME})...{RESET}")
        self.llm = ChatOllama(model=MODEL_NAME, temperature=0, base_url=OLLAMA_BASE_URL)
        
        docs = DataLoader.load_contracts()
        if docs:
            splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            splits = splitter.split_documents(docs)
            embeddings = OllamaEmbeddings(model=MODEL_NAME, base_url=OLLAMA_BASE_URL)
            self.vector_store = Chroma.from_documents(
                documents=splits, 
                embedding=embeddings, 
                collection_name="demo_contracts_cli_final"
            )
            print(f"{GREEN}Knowledge Base: {len(docs)} Contracts Ingested.{RESET}")
        else:
            print(f"{RED}Warning: No contracts found.{RESET}")

    def audit_transaction(self, tx):
        inv_id = tx.get('invoice_id') or tx.get('invoice id') or "UNKNOWN"
        vendor = tx.get('vendor') or "Unknown Vendor"
        
        if inv_id == "UNKNOWN" and vendor == "Unknown Vendor":
            return

        line_items = str(tx.get('line_items') or tx.get('line items') or tx.get('item') or '')
        amount = str(tx.get('total_amount') or tx.get('total amount') or tx.get('amount') or '0')
        date = str(tx.get('date') or 'Unknown Date')
        
        # 1. PYTHON HEADER (100% Accurate)
        print(f"\n{CYAN}========================================{RESET}")
        print(f"{YELLOW}AUDIT REPORT: {inv_id}{RESET}")
        print(f"{CYAN}========================================{RESET}")
        print(f"Vendor:  {vendor}")
        print(f"Date:    {date}")
        print(f"Item:    {line_items}")
        print(f"Amount:  ${amount}")
        print(f"{CYAN}----------------------------------------{RESET}")
        
        # 2. RAG SEARCH
        query = f"Pricing for {line_items}"
        results = self.vector_store.similarity_search(query, k=2)
        context = "\n".join([doc.page_content for doc in results])
        
        # 3. AI ANALYSIS (Focused Prompt)
        prompt = f"""
        ACT AS: Commercial Assurance Auditor.
        TASK: Compare the INVOICE against the CONTRACT terms.
        
        CONTRACT TERMS: 
        {context}
        
        INVOICE DATA: 
        Item: {line_items}
        Total Amount: {amount}
        
        INSTRUCTIONS:
        - Check if the price charged matches the contract rate.
        - Check for volume discounts or shipping errors.
        - Be brief and direct.
        
        OUTPUT FORMAT:
        [STATUS]: PASS or FAIL
        [REASON]: (1 sentence explanation)
        [ACTION]: Approve or Dispute
        """
        
        try:
            print("Analyzing...", end="\r")
            response = self.llm.invoke(prompt)
            # Clean up response slightly
            clean_response = response.content.replace("**", "").strip()
            print(f"{clean_response}\n")
        except Exception as e:
            print(f"{RED}AI Error: {e}{RESET}")

@click.command()
def run():
    agent = CommercialGuardianAgent()
    transactions = DataLoader.load_invoices()
    
    if not transactions:
        print(f"{RED}No transactions found.{RESET}")
        return

    print(f"Processing {len(transactions)} transactions...")
    for tx in transactions:
        agent.audit_transaction(tx)
        time.sleep(0.5)

if __name__ == "__main__":
    run()
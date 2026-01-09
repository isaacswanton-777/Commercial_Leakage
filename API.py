import os
import json
import asyncio
import pandas as pd
import io
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# --- IMPORTS ---
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import CharacterTextSplitter
from langchain_core.documents import Document

app = FastAPI()

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama_service:11434")
MODEL_NAME = "llama3.2"

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse('static/index.html')

def load_data():
    docs = []
    paths = ["/app/data/contracts", "/app/data/Contracts"]
    contract_path = next((p for p in paths if os.path.exists(p)), None)
    
    if contract_path:
        for f in os.listdir(contract_path):
            if f.endswith(".md"):
                with open(os.path.join(contract_path, f), "r") as file:
                    docs.append(Document(page_content=file.read(), metadata={"source": f}))
    
    invoices = []
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
                    # Handle CSV quotes roughly if needed, usually pandas handles it well
                    # but cleaning empty lines helps
                    if line:
                        cleaned_lines.append(line)
                
                data_str = "\n".join(cleaned_lines)
                df = pd.read_csv(io.StringIO(data_str), sep=',')
                # Normalize headers
                df.columns = df.columns.str.strip().str.lower().str.replace('"', '').str.replace('\ufeff', '')
                
                raw_records = df.to_dict('records')
                for row in raw_records:
                    # Normalize keys
                    clean_row = {k.strip().lower(): v for k, v in row.items()}
                    invoices.append(clean_row)
                break
            except Exception as e:
                print(f"Error loading CSV: {e}")
            
    return docs, invoices

class AsyncGuardian:
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.llm = ChatOllama(model=MODEL_NAME, temperature=0, base_url=OLLAMA_BASE_URL)
        docs, _ = load_data()
        
        if docs:
            embeddings = OllamaEmbeddings(model=MODEL_NAME, base_url=OLLAMA_BASE_URL)
            splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            splits = splitter.split_documents(docs)
            self.vector_store = Chroma.from_documents(
                documents=splits, 
                embedding=embeddings, 
                collection_name="visual_demo_v5" # New collection name to ensure clean slate
            )
        else:
            self.vector_store = None

    async def log(self, msg, type="info", active_node=None):
        await self.ws.send_text(json.dumps({"log": msg, "type": type, "active_node": active_node}))
        await asyncio.sleep(0.5)

    async def run_audit(self, tx):
        # Normalize fields
        inv_id = str(tx.get('invoice_id') or tx.get('invoice id') or "UNKNOWN")
        vendor = str(tx.get('vendor') or "Unknown")
        amount = str(tx.get('total_amount') or tx.get('amount') or '0')
        line_items = str(tx.get('line_items') or tx.get('item') or 'General Services')

        # 1. Send Invoice Data to UI
        await self.ws.send_text(json.dumps({
            "invoice": {
                "invoice_id": inv_id,
                "vendor": vendor,
                "total_amount": amount
            },
            "active_node": "1"
        }))

        await self.log(f"Ingesting Invoice {inv_id}...", "info", "1")
        await self.log(f"Fetching Contracts for {vendor}...", "info", "2")
        
        # 2. RAG Search
        context = "No contract found."
        if self.vector_store:
            try:
                # Search for both vendor name and line items
                query = f"{vendor} pricing {line_items}"
                results = self.vector_store.similarity_search(query, k=2)
                context = "\n".join([doc.page_content for doc in results])
                await self.log(f"Found {len(results)} contract clauses.", "success", "2")
            except Exception as e:
                await self.log(f"RAG Error: {e}", "error")
        
        await self.log("AI Auditor Analyzing...", "info", "3")
        
        # 3. LLM Analysis
        prompt = f"""
        ACT AS: Commercial Auditor.
        TASK: Audit Invoice.
        
        CONTRACT TERMS:
        {context}
        
        INVOICE DATA:
        ID: {inv_id}
        Vendor: {vendor}
        Items: {line_items}
        Amount: {amount}
        
        INSTRUCTIONS:
        Compare the Invoice against the Contract. 
        - If the amount matches or is valid according to terms, PASS.
        - If the amount is too high, wrong vendor, or missing items, FAIL.
        
        RETURN JSON ONLY: {{ "status": "PASS" or "FAIL", "reason": "Short explanation (max 10 words)", "action": "APPROVE" or "DISPUTE" }}
        """
        
        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            # Clean up potential markdown code blocks
            if "```" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            
            # Find JSON object
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1:
                result = json.loads(content[start:end])
            else:
                result = {"status": "FAIL", "reason": "AI Output Error", "action": "DISPUTE"}
        except Exception as e:
            print(e)
            result = {"status": "FAIL", "reason": "Processing Error", "action": "DISPUTE"}

        # 4. Routing
        await self.log(f"Result: {result.get('status', 'UNKNOWN')}", "info")
        
        if result.get('action') == "APPROVE":
             await self.log(f"Approving: {result.get('reason')}", "success", "4")
        else:
             await self.log(f"DISPUTING: {result.get('reason')}", "error", "5")
        
        await self.log("Audit Cycle Complete.", "info", "6")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WS CONNECTED")
    guardian = AsyncGuardian(websocket)
    
    # Initialize index to 0
    current_index = 0
    
    try:
        while True:
            data = await websocket.receive_text()
            if data == "run":
                _, invoices = load_data()
                if not invoices:
                    await guardian.log("No CSV data found!", "error")
                    continue
                
                # Cycle through invoices using modulus operator
                target = invoices[current_index % len(invoices)]
                current_index += 1
                
                await guardian.run_audit(target)
    except WebSocketDisconnect:
        print("WS DISCONNECTED")
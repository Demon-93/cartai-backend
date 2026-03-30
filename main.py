from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List

app = FastAPI()

# In-memory storage for conversation sessions
sessions: Dict[str, List[dict]] = {}


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    global sessions
    
    # Get or create session for this user
    user_id = request.user_id
    if user_id not in sessions:
        sessions[user_id] = []
    
    # Add user message to history
    sessions[user_id].append({
        "role": "user", 
        "content": request.message
    })
    
    # Create reply
    reply = "Hello from cart.ai"
    
    # Add assistant reply to history
    sessions[user_id].append({
        "role": "assistant",
        "content": reply
    })
    
    return {
        "reply": reply,
        "history": sessions[user_id]
    }

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List
import google.generativeai as genai
import os

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
    
    # Initialize Gemini
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Get or create session for this user
    user_id = request.user_id
    if user_id not in sessions:
        sessions[user_id] = []
    
    # Add user message to history
    sessions[user_id].append({
        "role": "user", 
        "content": request.message
    })
    
    # Get conversation history for this user
    history = sessions[user_id]
    
    # Build prompt as a single string
    system_prompt = "You are cart.ai, a buying decision engine. Your job is to find the best product for the user across Flipkart and Amazon. You operate in two modes. CLARIFY MODE: When the user tells you what they want but you do not have enough information to search effectively, ask one smart, relevant question at a time. Ask only what is necessary for this specific product. Use your judgment. Do not ask more than 5 questions total. SEARCH MODE: When you have enough context, respond with ONLY this JSON and nothing else: {\"mode\": \"search\", \"query\": \"your optimised search query\", \"platform\": [\"flipkart\", \"amazon\"]}. Always be concise. Sound like a smart friend helping someone shop."
    
    prompt = system_prompt + "\n\n"
    
    for msg in history:
        if msg["role"] == "user":
            prompt += f"User: {msg['content']}\n"
        else:
            prompt += f"Assistant: {msg['content']}\n"
    
    # Get response from Gemini
    response = model.generate_content(prompt)
    
    # Check if response contains search mode JSON
    import json
    try:
        # Try to parse as JSON
        result = json.loads(response.text)
        if isinstance(result, dict) and result.get("mode") == "search":
            search_ready = True
        else:
            search_ready = False
    except json.JSONDecodeError:
        search_ready = False
    
    # Add assistant reply to history
    sessions[user_id].append({
        "role": "assistant",
        "content": response.text
    })
    
    return {
        "reply": response.text,
        "search_ready": search_ready,
        "history": sessions[user_id]
    }

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List
import google.generativeai as genai
import os
from scraper import search_products
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    model = genai.GenerativeModel('gemini-2.5-flash')
    
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
    
    # If search is ready, fetch products and get recommendation
    if search_ready:
        try:
            # Extract query from Gemini's JSON
            query = result.get("query", "")
            
            if query:
                # Call scraper to get products
                products = search_products(query)
                
                # Build recommendation prompt
                recommendation_prompt = f"Here are the search results: {products}. Now compare them and recommend the single best product. Explain in 3-4 sentences why it is the best choice."
                
                # Add recommendation prompt to history
                sessions[user_id].append({
                    "role": "user",
                    "content": recommendation_prompt
                })
                
                # Build full prompt for Gemini recommendation
                full_prompt = system_prompt + "\n\n"
                for msg in sessions[user_id]:
                    if msg["role"] == "user":
                        full_prompt += f"User: {msg['content']}\n"
                    else:
                        full_prompt += f"Assistant: {msg['content']}\n"
                
                # Get recommendation from Gemini
                recommendation_response = model.generate_content(full_prompt)
                
                # Add recommendation to history
                sessions[user_id].append({
                    "role": "assistant",
                    "content": recommendation_response.text
                })
                
                return {
                    "reply": recommendation_response.text,
                    "search_ready": False,
                    "history": sessions[user_id]
                }
        except Exception as e:
            # If scraper fails, return original response with search_ready still true
            print(f"Error in recommendation phase: {e}")
            return {
                "reply": response.text,
                "search_ready": True,
                "history": sessions[user_id]
            }
    
    return {
        "reply": response.text,
        "search_ready": search_ready,
        "history": sessions[user_id]
    }

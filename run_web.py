"""
Start the web-based chatbot interface.
"""
import uvicorn
import sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(BASE_DIR, "src")

# Add src/ to Python path
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Correct imports
from web.app import web_app
from models.llm_config import LLMConfig

if __name__ == "__main__":
    # Initialize LLM
    LLMConfig.get_llm()
    
    print("="*60)
    print("Starting JIRA Agent Chatbot Web Interface")
    print("="*60)
    print("\n🌐 Server starting at: http://localhost:8000")
    print("📝 Open your browser and navigate to the URL above")
    print("🔐 Register a new user or login to start chatting")
    print("="*60)
    print()
    
    uvicorn.run(
        web_app,
        host="127.0.0.1",   # You can use 0.0.0.0 also
        port=8000,
        reload=False,        
        log_level="info"
    )

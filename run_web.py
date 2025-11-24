"""
Start the web-based chatbot interface.
"""
import uvicorn
from src.web.app import web_app
from src.models.llm_config import LLMConfig

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
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


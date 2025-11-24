"""
Web-based chatbot interface with authentication for JIRA agent.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import json

from graphs.jira_agent_graph import app as langgraph_app
from langchain_core.messages import HumanMessage, AIMessage
from approval.approval_manager import approval_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
web_app = FastAPI(title="JIRA Agent Chatbot")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Templates - handle both development and production paths
template_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(template_dir):
    # Fallback for different project structures
    template_dir = "src/web/templates"
templates = Jinja2Templates(directory=template_dir)

# In-memory user storage (replace with database in production)
users_db: Dict[str, Dict] = {}
active_sessions: Dict[str, Dict] = {}  # session_id -> user_data
user_conversations: Dict[str, list] = {}  # username -> conversation state


# ==================== MODELS ====================

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


# ==================== AUTHENTICATION ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str) -> Optional[Dict]:
    """Get current user from token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return users_db.get(username)
    except JWTError:
        return None


# ==================== ROUTES ====================

@web_app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main chat interface."""
    return templates.TemplateResponse("chat.html", {"request": request})


@web_app.post("/api/auth/register")
async def register(user_data: UserRegister):
    """Register a new user."""
    if user_data.username in users_db:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = get_password_hash(user_data.password)
    users_db[user_data.username] = {
        "username": user_data.username,
        "hashed_password": hashed_password,
        "email": user_data.email,
        "created_at": datetime.utcnow().isoformat()
    }
    
    logger.info(f"User registered: {user_data.username}")
    return {"message": "User registered successfully", "username": user_data.username}


@web_app.post("/api/auth/login")
async def login(user_data: UserLogin):
    """Login and get access token."""
    user = users_db.get(user_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_data.username}, expires_delta=access_token_expires
    )
    
    # Create session
    session_id = secrets.token_urlsafe(32)
    active_sessions[session_id] = {
        "username": user_data.username,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Initialize conversation state
    if user_data.username not in user_conversations:
        user_conversations[user_data.username] = {
            "messages": [],
            "state": {
                "greeted": False,
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        }
    
    logger.info(f"User logged in: {user_data.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "session_id": session_id,
        "username": user_data.username
    }


@web_app.post("/api/auth/logout")
async def logout(session_id: str):
    """Logout and invalidate session."""
    if session_id in active_sessions:
        username = active_sessions[session_id]["username"]
        del active_sessions[session_id]
        logger.info(f"User logged out: {username}")
        return {"message": "Logged out successfully"}
    return {"message": "Session not found"}


@web_app.post("/api/chat")
async def chat(message: ChatMessage):
    """Handle chat messages."""
    if not message.session_id or message.session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    session = active_sessions[message.session_id]
    username = session["username"]
    
    # Get conversation state
    conversation = user_conversations.get(username, {
        "messages": [],
        "state": {
            "greeted": False,
            "status_filter": None,
            "ticket_to_summarize": None,
            "pending_approval_id": None,
            "operation_type": None
        }
    })
    
    try:
        # Prepare input state for LangGraph
        input_state = {
            **conversation["state"],
            "messages": [HumanMessage(content=message.message)]
        }
        
        # Invoke LangGraph workflow
        result = langgraph_app.invoke(input_state)
        
        # Extract AI responses
        ai_responses = []
        for msg in result.get("messages", []):
            if isinstance(msg, AIMessage):
                ai_responses.append(msg.content)
        
        # Update conversation state
        conversation["state"] = {
            "greeted": result.get("greeted", False),
            "status_filter": result.get("status_filter"),
            "ticket_to_summarize": result.get("ticket_to_summarize"),
            "pending_approval_id": result.get("pending_approval_id"),
            "operation_type": result.get("operation_type")
        }
        
        # Store messages
        conversation["messages"].append({
            "role": "user",
            "content": message.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        for response in ai_responses:
            conversation["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        user_conversations[username] = conversation
        
        # Check for pending approvals
        pending_approvals = approval_manager.get_pending_approvals()
        approval_info = None
        if pending_approvals:
            latest_approval = pending_approvals[-1]
            approval_info = {
                "request_id": latest_approval.request_id,
                "operation_type": latest_approval.operation_type,
                "ticket_key": latest_approval.ticket_key,
                "preview": latest_approval.preview
            }
        
        return {
            "response": "\n".join(ai_responses) if ai_responses else "No response generated",
            "pending_approval": approval_info,
            "session_id": message.session_id
        }
    
    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@web_app.get("/api/approvals/pending")
async def get_pending_approvals(session_id: str):
    """Get pending approval requests for the user."""
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    pending = approval_manager.get_pending_approvals()
    return {
        "approvals": [
            {
                "request_id": a.request_id,
                "operation_type": a.operation_type,
                "ticket_key": a.ticket_key,
                "description": a.description,
                "preview": a.preview,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in pending
        ]
    }


@web_app.post("/api/approvals/{request_id}/approve")
async def approve_request(request_id: str, session_id: str):
    """Approve a pending request."""
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    username = active_sessions[session_id]["username"]
    
    if approval_manager.approve(request_id, approved_by=username):
        return {"message": "Request approved successfully", "request_id": request_id}
    else:
        raise HTTPException(status_code=404, detail="Approval request not found")


@web_app.post("/api/approvals/{request_id}/reject")
async def reject_request(request_id: str, reason: str = "", session_id: str = ""):
    """Reject a pending request."""
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    username = active_sessions[session_id]["username"]
    
    if approval_manager.reject(request_id, reason=reason, rejected_by=username):
        return {"message": "Request rejected successfully", "request_id": request_id}
    else:
        raise HTTPException(status_code=404, detail="Approval request not found")


@web_app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8000)


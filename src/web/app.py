"""
Web-based chatbot interface with authentication for JIRA agent.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import csv

from graphs.jira_agent_graph import app as langgraph_app
from langchain_core.messages import HumanMessage, AIMessage
from approval.approval_manager import approval_manager

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------
web_app = FastAPI(title="JIRA Agent Chatbot")

# ---------------------------------------------------------
# Security / JWT
# ---------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------
# Templates
# ---------------------------------------------------------
template_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(template_dir):
    template_dir = "src/web/templates"
templates = Jinja2Templates(directory=template_dir)

# ---------------------------------------------------------
# User Storage
# ---------------------------------------------------------
users_db: Dict[str, Dict] = {}
active_sessions: Dict[str, Dict] = {}
user_conversations: Dict[str, dict] = {}

USERS_CSV_PATH = os.path.join(os.path.dirname(__file__), "users.csv")


# ---------------------------------------------------------
# CSV User Persistence
# ---------------------------------------------------------
def load_users_from_csv():
    """Load users into users_db from CSV."""
    if not os.path.exists(USERS_CSV_PATH):
        return

    with open(USERS_CSV_PATH, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            users_db[row["username"]] = {
                "username": row["username"],
                "hashed_password": row["hashed_password"],
                "email": row.get("email"),
                "created_at": row.get("created_at"),
            }


def save_user_to_csv(user: dict):
    """Append a new user to CSV."""
    file_exists = os.path.exists(USERS_CSV_PATH)

    with open(USERS_CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        fieldnames = ["username", "hashed_password", "email", "created_at"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(user)


# Load users on startup
load_users_from_csv()


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Auth Helpers
# ---------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=15)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@web_app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@web_app.post("/api/auth/register")
async def register(user_data: UserRegister):
    if user_data.username in users_db:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed = get_password_hash(user_data.password)

    user_record = {
        "username": user_data.username,
        "hashed_password": hashed,
        "email": user_data.email,
        "created_at": datetime.utcnow().isoformat(),
    }

    users_db[user_data.username] = user_record
    save_user_to_csv(user_record)

    return {"message": "User registered successfully", "username": user_data.username}


@web_app.post("/api/auth/login")
async def login(user_data: UserLogin):
    user = users_db.get(user_data.username)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(
        data={"sub": user_data.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    session_id = secrets.token_urlsafe(32)
    active_sessions[session_id] = {
        "username": user_data.username,
        "created_at": datetime.utcnow().isoformat(),
    }

    if user_data.username not in user_conversations:
        user_conversations[user_data.username] = {
            "messages": [],
            "state": {
                "greeted": False,
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None,
                "target_ticket_key": None,
                "target_status": None,
                "assignee": None,
                "comment_body": None,
            },
        }

    return {
        "access_token": access_token,
        "session_id": session_id,
        "username": user_data.username,
    }


@web_app.post("/api/auth/logout")
async def logout(session_id: str):
    if session_id in active_sessions:
        del active_sessions[session_id]
        return {"message": "Logged out successfully"}
    return {"message": "Session not found"}


# ---------------------------------------------------------
# Chat Route (Stateful LangGraph)
# ---------------------------------------------------------
@web_app.post("/api/chat")
async def chat(message: ChatMessage):
    if not message.session_id or message.session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    username = active_sessions[message.session_id]["username"]
    conversation = user_conversations[username]

    # Prepare state
    input_state = {**conversation["state"], "messages": [HumanMessage(content=message.message)]}

    # Invoke graph
    result = langgraph_app.invoke(input_state)

    # Extract AI responses
    ai_responses = [
        msg.content for msg in result.get("messages", []) if isinstance(msg, AIMessage)
    ]

    # 🔥 Preserve entire state except messages
    conversation["state"] = {k: v for k, v in result.items() if k != "messages"}

    # Store history
    conversation["messages"].append(
        {"role": "user", "content": message.message, "timestamp": datetime.utcnow().isoformat()}
    )
    for resp in ai_responses:
        conversation["messages"].append(
            {"role": "assistant", "content": resp, "timestamp": datetime.utcnow().isoformat()}
        )

    user_conversations[username] = conversation

    # Pending approval info
    pending_approvals = approval_manager.get_pending_approvals()
    approval_info = None
    if pending_approvals:
        latest = pending_approvals[-1]
        approval_info = {
            "request_id": latest.request_id,
            "operation_type": latest.operation_type,
            "ticket_key": latest.ticket_key,
            "preview": latest.preview,
        }

    return {
        "response": "\n".join(ai_responses) if ai_responses else "No response generated",
        "pending_approval": approval_info,
        "session_id": message.session_id,
    }


# ---------------------------------------------------------
# Approvals
# ---------------------------------------------------------
@web_app.get("/api/approvals/pending")
async def get_pending_approvals(session_id: str):
    if session_id not in active_sessions:
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
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in pending
        ]
    }


@web_app.post("/api/approvals/{request_id}/approve")
async def approve_request(request_id: str, session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    username = active_sessions[session_id]["username"]
    if approval_manager.approve(request_id, approved_by=username):
        return {"message": "Request approved successfully", "request_id": request_id}

    raise HTTPException(status_code=404, detail="Approval request not found")


@web_app.post("/api/approvals/{request_id}/reject")
async def reject_request(request_id: str, session_id: str, reason: str = ""):
    if session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    username = active_sessions[session_id]["username"]
    if approval_manager.reject(request_id, reason=reason, rejected_by=username):
        return {"message": "Request rejected successfully", "request_id": request_id}

    raise HTTPException(status_code=404, detail="Approval request not found")


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------
@web_app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(web_app, host="0.0.0.0", port=8000)


"""
LangGraph workflow for JIRA agent with human approval required.
Every write operation requires human message and approval before execution.
This is the main workflow - all operations go through approval.
"""
import logging
import operator
from typing import TypedDict, Annotated
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph
from models.llm_config import LLMConfig
from tools.jira_tool import fetch_and_summarize_ticket, fetch_statuses, fetch_tickets_by_status
from tools.jira_operations_approved import (
    create_ticket_with_approval,
    update_ticket_with_approval,
    transition_ticket_with_approval,
    assign_ticket_with_approval,
    add_comment_with_approval,
    execute_create_ticket,
    execute_update_ticket,
    execute_transition_ticket,
    execute_assign_ticket,
    execute_add_comment
)
from approval.approval_manager import approval_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize LLM
llm = LLMConfig.get_llm()
logger.info("Initialized LLM for Jira agent with approval workflow")

# State
class AgentState(TypedDict):
    """State schema for the Jira agent workflow with approvals."""
    messages: Annotated[list, operator.add]
    greeted: bool
    status_filter: str | None
    ticket_to_summarize: str | None
    pending_approval_id: str | None
    operation_type: str | None  # create, update, transition, assign, comment


def agent_node(state: AgentState):
    """Process user input and determine the next action. Requires human message."""
    logger.info("Executing agent_node")
    try:
        messages = state["messages"]
        
        # STRICT: Must have human message to proceed
        human_messages = [m for m in messages if isinstance(m, HumanMessage) and m.content.strip()]
        if not human_messages:
            logger.warning("No human message found - cannot proceed without human input")
            return {
                "messages": [AIMessage(content="I need a human message to proceed. Please provide instructions.")],
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        
        last_msg = messages[-1].content.lower() if messages else ""
        logger.debug("Last message: %s", last_msg)
        
        # Handle approval commands
        if "approve" in last_msg:
            parts = last_msg.split()
            approval_id = None
            for i, part in enumerate(parts):
                if part == "approve" and i + 1 < len(parts):
                    approval_id = parts[i + 1]
                    break
            
            if approval_id:
                if approval_manager.approve(approval_id):
                    approval = approval_manager.get_approval(approval_id) or \
                              next((a for a in approval_manager.approval_history if a.request_id == approval_id), None)
                    if approval:
                        return {
                            "messages": [AIMessage(content=f"✅ Approval granted for {approval.operation_type}. Executing operation...")],
                            "pending_approval_id": approval_id,
                            "operation_type": approval.operation_type,
                            "greeted": state.get("greeted", False),
                            "status_filter": None,
                            "ticket_to_summarize": None
                        }
                else:
                    return {
                        "messages": [AIMessage(content=f"❌ Approval request {approval_id} not found or already processed.")],
                        "greeted": state.get("greeted", False),
                        "status_filter": None,
                        "ticket_to_summarize": None,
                        "pending_approval_id": None,
                        "operation_type": None
                    }
        
        if "reject" in last_msg:
            parts = last_msg.split()
            approval_id = None
            reason = ""
            for i, part in enumerate(parts):
                if part == "reject" and i + 1 < len(parts):
                    approval_id = parts[i + 1]
                    if i + 2 < len(parts):
                        reason = " ".join(parts[i + 2:])
                    break
            
            if approval_id:
                approval_manager.reject(approval_id, reason)
                return {
                    "messages": [AIMessage(content=f"❌ Operation rejected. Approval request {approval_id} has been cancelled.")],
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "ticket_to_summarize": None,
                    "pending_approval_id": None,
                    "operation_type": None
                }
        
        # Check for operation commands
        statuses = [s.lower() for s in fetch_statuses()]
        requested_status = None
        for s in statuses:
            if s in last_msg:
                requested_status = s
                break
        
        if "show me my tickets" in last_msg:
            logger.info("Detected 'show me my tickets' command")
            return {
                "messages": [AIMessage(content="Hi! Fetching your tickets...")],
                "greeted": True,
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        
        elif requested_status:
            logger.info("Detected status filter: %s", requested_status)
            return {
                "messages": [AIMessage(content=f"Fetching tickets with status '{requested_status}'...")],
                "greeted": True,
                "status_filter": requested_status,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        
        elif "summarize ticket" in last_msg:
            parts = last_msg.split()
            ticket_key = next((p for p in parts if "-" in p), None)
            if ticket_key:
                logger.info("Detected summarize ticket command for: %s", ticket_key)
                return {
                    "messages": [AIMessage(content=f"Summarizing ticket {ticket_key}...")],
                    "ticket_to_summarize": ticket_key,
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "pending_approval_id": None,
                    "operation_type": None
                }
        
        # Parse write operations (require approval)
        elif "create ticket" in last_msg or "new ticket" in last_msg:
            # Extract ticket details from message (simplified - would use LLM for better parsing)
            return {
                "messages": [AIMessage(content="To create a ticket, please provide: project key, summary, and description. I will show you a preview for approval.")],
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": "create"
            }
        
        elif "update ticket" in last_msg or "modify ticket" in last_msg:
            parts = last_msg.split()
            ticket_key = next((p for p in parts if "-" in p), None)
            if ticket_key:
                return {
                    "messages": [AIMessage(content=f"To update ticket {ticket_key}, please specify what to change. I will show you a preview for approval.")],
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "ticket_to_summarize": None,
                    "pending_approval_id": None,
                    "operation_type": "update"
                }
        
        # Default LLM fallback
        logger.debug("Invoking LLM for default response")
        response = llm.invoke(human_messages)
        logger.info("LLM response generated")
        return {
            "messages": [response],
            "greeted": state.get("greeted", False),
            "status_filter": None,
            "ticket_to_summarize": None,
            "pending_approval_id": None,
            "operation_type": None
        }
    except Exception as e:
        logger.error("Error in agent_node: %s", e)
        raise


def tool_node(state: AgentState):
    """Fetch tickets based on the status filter if greeted. Read-only, no approval needed."""
    logger.info("Executing tool_node")
    try:
        if state.get("greeted", False):
            logger.debug("Fetching tickets with status filter: %s", state.get("status_filter"))
            tickets = fetch_tickets_by_status(state.get("status_filter"))
            logger.info("Tickets fetched successfully")
            return {
                "messages": [AIMessage(content=tickets)],
                "greeted": False,
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        logger.debug("No action required in tool_node")
        return state
    except Exception as e:
        logger.error("Error in tool_node: %s", e)
        raise


def summarize_ticket_node(state: AgentState):
    """Summarize a specific ticket. Read-only, no approval needed."""
    logger.info("Executing summarize_ticket_node")
    try:
        ticket_key = state.get("ticket_to_summarize")
        if ticket_key:
            logger.debug("Summarizing ticket: %s", ticket_key)
            summary = fetch_and_summarize_ticket(ticket_key)
            logger.info("Ticket %s summarized successfully", ticket_key)
            return {
                "messages": [AIMessage(content=summary)],
                "ticket_to_summarize": None,
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        logger.debug("No ticket to summarize")
        return state
    except Exception as e:
        logger.error("Error in summarize_ticket_node: %s", e)
        raise


def approval_node(state: AgentState):
    """Show approval request and wait for human approval."""
    logger.info("Executing approval_node")
    try:
        operation_type = state.get("operation_type")
        messages = state["messages"]
        last_msg = messages[-1].content if messages else ""
        
        # This would parse the operation details from the message
        # For now, simplified example
        if operation_type == "create":
            # In real implementation, parse ticket details from message
            approval = create_ticket_with_approval(
                project_key="PROJ",  # Would parse from message
                summary="Example Ticket",  # Would parse from message
                description="Example description",  # Would parse from message
                issue_type="Task"
            )
            
            approval_msg = approval_manager.format_approval_message(approval)
            return {
                "messages": [AIMessage(content=approval_msg)],
                "pending_approval_id": approval.request_id,
                "operation_type": operation_type,
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None
            }
        
        return state
    except Exception as e:
        logger.error("Error in approval_node: %s", e)
        raise


def execute_node(state: AgentState):
    """Execute approved operation."""
    logger.info("Executing execute_node")
    try:
        approval_id = state.get("pending_approval_id")
        operation_type = state.get("operation_type")
        
        if not approval_id or not operation_type:
            return {
                "messages": [AIMessage(content="No pending operation to execute.")],
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        
        try:
            if operation_type == "create_ticket":
                ticket_key = execute_create_ticket(approval_id)
                return {
                    "messages": [AIMessage(content=f"✅ Ticket created successfully: {ticket_key}")],
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "ticket_to_summarize": None,
                    "pending_approval_id": None,
                    "operation_type": None
                }
            elif operation_type == "update_ticket":
                success = execute_update_ticket(approval_id)
                if success:
                    return {
                        "messages": [AIMessage(content="✅ Ticket updated successfully.")],
                        "greeted": state.get("greeted", False),
                        "status_filter": None,
                        "ticket_to_summarize": None,
                        "pending_approval_id": None,
                        "operation_type": None
                    }
            # Add other operation types...
        except Exception as e:
            return {
                "messages": [AIMessage(content=f"❌ Error executing operation: {str(e)}")],
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }
        
        return state
    except Exception as e:
        logger.error("Error in execute_node: %s", e)
        raise


# Graph
logger.info("Setting up workflow graph with approval workflow")
workflow = StateGraph(state_schema=AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.add_node("summarizer", summarize_ticket_node)
workflow.add_node("approval", approval_node)
workflow.add_node("execute", execute_node)
workflow.set_entry_point("agent")

# Conditional routing
def route_after_agent(state: AgentState):
    """Route after agent node based on state."""
    if state.get("pending_approval_id") and state.get("operation_type"):
        # Check if already approved
        if approval_manager.is_approved(state.get("pending_approval_id")):
            return "execute"
        else:
            return "approval"
    elif state.get("greeted", False):
        return "tools"
    elif state.get("ticket_to_summarize"):
        return "summarizer"
    else:
        return END

workflow.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "tools": "tools",
        "summarizer": "summarizer",
        "approval": "approval",
        "execute": "execute",
        END: END
    }
)

workflow.add_edge("tools", END)
workflow.add_edge("summarizer", END)
workflow.add_edge("approval", END)  # Approval waits for human input, then goes back to agent
workflow.add_edge("execute", END)

# Compile Graph
logger.info("Compiling workflow graph with approval workflow")
app = workflow.compile()
logger.info("Workflow graph compiled successfully")


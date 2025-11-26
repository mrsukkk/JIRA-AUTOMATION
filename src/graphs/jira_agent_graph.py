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

    # 🔹 extra fields used by agent_node/approval_node
    target_ticket_key: str | None
    target_status: str | None
    assignee: str | None
    comment_body: str | None


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
        
        # ============================================================
        # 1️⃣ Handle approval commands FIRST
        # ============================================================
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
        

        # ============================================================
        # 2️⃣ WRITE OPERATIONS MUST COME BEFORE STATUS FILTER
        # ============================================================

        # --- Write operation detection and mapping ---
        import re
        # Extract ticket key (e.g., ESD-242)
        ticket_key_match = re.search(r"([A-Z][A-Z0-9]+-\d+)", last_msg, re.I)
        ticket_key = ticket_key_match.group(1).upper() if ticket_key_match else None

        # Robust status transition detection (e.g., 'update ticket status ESD-242 to resume development')
        transition_patterns = [
            r"update ticket status ([A-Z][A-Z0-9]+-\d+) to ([\w\s]+)",
            r"change status of ([A-Z][A-Z0-9]+-\d+) to ([\w\s]+)",
            r"transition ticket ([A-Z][A-Z0-9]+-\d+) to ([\w\s]+)",
            r"move ticket ([A-Z][A-Z0-9]+-\d+) to ([\w\s]+)",
            r"set status of ([A-Z][A-Z0-9]+-\d+) to ([\w\s]+)",
        ]
        for pat in transition_patterns:
            m = re.search(pat, last_msg)
            if m:
                tkey = m.group(1).upper()
                tstatus = m.group(2).strip()
                return {
                    "messages": [AIMessage(content=f"To transition ticket {tkey} to '{tstatus}', I will show you a preview for approval.")],
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "ticket_to_summarize": None,
                    "pending_approval_id": None,
                    "operation_type": "transition_ticket",
                    "target_ticket_key": tkey,
                    "target_status": tstatus
                }

        # Also handle 'resume development' or 'change status to ...' after a previous update/transition intent
        if ("change status" in last_msg or "resume development" in last_msg) and ticket_key:
            # Try to extract the status after 'to' or 'resume'
            m = re.search(r"(?:to|resume) ([\w\s]+)", last_msg)
            tstatus = m.group(1).strip() if m else None
            if tstatus:
                return {
                    "messages": [AIMessage(content=f"To transition ticket {ticket_key} to '{tstatus}', I will show you a preview for approval.")],
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "ticket_to_summarize": None,
                    "pending_approval_id": None,
                    "operation_type": "transition_ticket",
                    "target_ticket_key": ticket_key,
                    "target_status": tstatus
                }

        # Create
        if "create ticket" in last_msg or "new ticket" in last_msg:
            return {
                "messages": [AIMessage(content="To create a ticket, please provide: project key, summary, and description. I will show you a preview for approval.")],
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": "create_ticket"
            }
        # Update
        if ("update ticket" in last_msg or "modify ticket" in last_msg) and ticket_key:
            return {
                "messages": [AIMessage(content=f"To update ticket {ticket_key}, please specify what to change. I will show you a preview for approval.")],
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": "update_ticket",
                "target_ticket_key": ticket_key
            }
        # Transition (fallback for generic phrases)
        if ("transition ticket" in last_msg or "move ticket" in last_msg or "change status" in last_msg) and ticket_key:
            # Try to extract target status after 'to'
            m = re.search(r"to ([\w\s]+)", last_msg)
            target_status = m.group(1).strip() if m else None
            return {
                "messages": [AIMessage(content=f"To transition ticket {ticket_key}, please specify the target status. I will show you a preview for approval.")],
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": "transition_ticket",
                "target_ticket_key": ticket_key,
                "target_status": target_status
            }
        # Assign
        if "assign ticket" in last_msg or "reassign ticket" in last_msg:
            if ticket_key:
                # Try to extract assignee
                assignee = parts[-1] if len(parts) > 2 else None
                return {
                    "messages": [AIMessage(content=f"To assign ticket {ticket_key}, please specify the assignee. I will show you a preview for approval.")],
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "ticket_to_summarize": None,
                    "pending_approval_id": None,
                    "operation_type": "assign_ticket",
                    "target_ticket_key": ticket_key,
                    "assignee": assignee
                }
        # Add comment
        if "add comment" in last_msg or "comment on ticket" in last_msg:
            if ticket_key:
                # Try to extract comment body (naive)
                comment_body = last_msg.split("add comment")[-1].strip() if "add comment" in last_msg else ""
                return {
                    "messages": [AIMessage(content=f"To add a comment to ticket {ticket_key}, please provide the comment text. I will show you a preview for approval.")],
                    "greeted": state.get("greeted", False),
                    "status_filter": None,
                    "ticket_to_summarize": None,
                    "pending_approval_id": None,
                    "operation_type": "add_comment",
                    "target_ticket_key": ticket_key,
                    "comment_body": comment_body
                }


        # ============================================================
        # 3️⃣ Summarization
        # ============================================================
        if "summarize ticket" in last_msg:
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


        # ============================================================
        # 4️⃣ STATUS FILTER (moved DOWN so it doesn’t block updates)
        # ============================================================
        statuses = [s.lower() for s in fetch_statuses()]
        requested_status = None
        for s in statuses:
            if s in last_msg:
                requested_status = s
                break
        
        if requested_status:
            logger.info("Detected status filter: %s", requested_status)
            return {
                "messages": [AIMessage(content=f"Fetching tickets with status '{requested_status}'...")],
                "greeted": True,
                "status_filter": requested_status,
                "ticket_to_summarize": None,
                "pending_approval_id": None,
                "operation_type": None
            }


        # ============================================================
        # 5️⃣ Normal "show me my tickets"
        # ============================================================
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


        # ============================================================
        # 6️⃣ DEFAULT LLM FALLBACK
        # ============================================================
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
        
        # Route to correct approval function based on operation_type
        if operation_type == "create_ticket":
            # TODO: Parse real values from state/messages
            approval = create_ticket_with_approval(
                project_key="PROJ", summary="Example Ticket", description="Example description", issue_type="Task"
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
        elif operation_type == "update_ticket":
            ticket_key = state.get("target_ticket_key")
            approval = update_ticket_with_approval(ticket_key)
            approval_msg = approval_manager.format_approval_message(approval)
            return {
                "messages": [AIMessage(content=approval_msg)],
                "pending_approval_id": approval.request_id,
                "operation_type": operation_type,
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None
            }
        elif operation_type == "transition_ticket":
            ticket_key = state.get("target_ticket_key")
            target_status = state.get("target_status")
            approval = transition_ticket_with_approval(ticket_key, target_status)
            approval_msg = approval_manager.format_approval_message(approval)
            return {
                "messages": [AIMessage(content=approval_msg)],
                "pending_approval_id": approval.request_id,
                "operation_type": operation_type,
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None
            }
        elif operation_type == "assign_ticket":
            ticket_key = state.get("target_ticket_key")
            assignee = state.get("assignee")
            approval = assign_ticket_with_approval(ticket_key, assignee)
            approval_msg = approval_manager.format_approval_message(approval)
            return {
                "messages": [AIMessage(content=approval_msg)],
                "pending_approval_id": approval.request_id,
                "operation_type": operation_type,
                "greeted": state.get("greeted", False),
                "status_filter": None,
                "ticket_to_summarize": None
            }
        elif operation_type == "add_comment":
            ticket_key = state.get("target_ticket_key")
            comment_body = state.get("comment_body")
            approval = add_comment_with_approval(ticket_key, comment_body)
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
            elif operation_type == "transition_ticket":
                success = execute_transition_ticket(approval_id)
                if success:
                    return {
                        "messages": [AIMessage(content="✅ Ticket transitioned successfully.")],
                        "greeted": state.get("greeted", False),
                        "status_filter": None,
                        "ticket_to_summarize": None,
                        "pending_approval_id": None,
                        "operation_type": None
                    }
            elif operation_type == "assign_ticket":
                success = execute_assign_ticket(approval_id)
                if success:
                    return {
                        "messages": [AIMessage(content="✅ Ticket assigned successfully.")],
                        "greeted": state.get("greeted", False),
                        "status_filter": None,
                        "ticket_to_summarize": None,
                        "pending_approval_id": None,
                        "operation_type": None
                    }
            elif operation_type == "add_comment":
                success = execute_add_comment(approval_id)
                if success:
                    return {
                        "messages": [AIMessage(content="✅ Comment added successfully.")],
                        "greeted": state.get("greeted", False),
                        "status_filter": None,
                        "ticket_to_summarize": None,
                        "pending_approval_id": None,
                        "operation_type": None
                    }
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
    approval_id = state.get("pending_approval_id")
    op_type = state.get("operation_type")

    # 1) We detected a write operation but haven't created an approval yet
    #    → go to approval_node to build the preview.
    if op_type and not approval_id:
        return "approval"

    # 2) We have an approval id + operation type
    #    If approved → execute, otherwise just end this turn and wait
    #    for a human "approve <id>" (or UI approve button).
    if approval_id and op_type:
        if approval_manager.is_approved(approval_id):
            return "execute"
        else:
            # Approval exists but still pending: we've already shown the preview.
            # Wait for explicit approve/reject command.
            return END

    # 3) Read-only paths
    if state.get("greeted", False):
        return "tools"
    if state.get("ticket_to_summarize"):
        return "summarizer"

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


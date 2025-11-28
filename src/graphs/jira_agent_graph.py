import logging
import operator
import re
from typing import TypedDict, Annotated

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from models.llm_config import LLMConfig
from tools.jira_tool import fetch_and_summarize_ticket, fetch_tickets_by_status
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
    execute_add_comment,
)
from approval.approval_manager import approval_manager

# ---------------------------------------------------------
# Logging / LLM
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

llm = LLMConfig.get_llm()
logger.info("Initialized LLM for Jira agent with approval workflow")

# ---------------------------------------------------------
# Canonical command patterns
# ---------------------------------------------------------
# These are the ONLY patterns we use for routing.
# All are case-insensitive and must match the whole message.

PATTERNS = {
    # READ
    "show_my_tickets": re.compile(r'^show my tickets$', re.IGNORECASE),
    "show_tickets_status": re.compile(r'^show tickets with status (.+)$', re.IGNORECASE),
    "summarize_ticket": re.compile(r'^summarize ticket ([A-Z][A-Z0-9]+-\d+)$', re.IGNORECASE),

    # WRITE (approval required)
    # create ticket in ESD summary "Title" description "Body"
    "create_ticket": re.compile(
        r'^create ticket in ([A-Z][A-Z0-9]+) summary "(.+?)" description "(.+?)"$',
        re.IGNORECASE,
    ),
    # update ticket ESD-1 set summary "New summary"
    "update_ticket": re.compile(
        r'^update ticket ([A-Z][A-Z0-9]+-\d+) set (\w+) "(.+?)"$',
        re.IGNORECASE,
    ),
    # transition ticket ESD-1 to "In Progress"
    "transition_ticket": re.compile(
        r'^transition ticket ([A-Z][A-Z0-9]+-\d+) to "(.+?)"$',
        re.IGNORECASE,
    ),
    # assign ticket ESD-1 to "john.doe"
    "assign_ticket": re.compile(
        r'^assign ticket ([A-Z][A-Z0-9]+-\d+) to "(.+?)"$',
        re.IGNORECASE,
    ),
    # comment on ticket ESD-1 "this is a comment"
    "add_comment": re.compile(
        r'^comment on ticket ([A-Z][A-Z0-9]+-\d+) "(.+?)"$',
        re.IGNORECASE,
    ),

    # APPROVAL COMMANDS
    "approve": re.compile(r'^approve ([0-9a-f-]+)$', re.IGNORECASE),
    "reject": re.compile(r'^reject ([0-9a-f-]+)$', re.IGNORECASE),
}


# ---------------------------------------------------------
# State
# ---------------------------------------------------------
class AgentState(TypedDict):
    """State schema for the Jira agent workflow with approvals."""
    messages: Annotated[list, operator.add]

    greeted: bool
    status_filter: str | None
    ticket_to_summarize: str | None

    pending_approval_id: str | None
    operation_type: str | None  # create_ticket, update_ticket, transition_ticket, assign_ticket, add_comment

    # extra fields used by approval_node
    target_ticket_key: str | None
    target_status: str | None
    assignee: str | None
    comment_body: str | None
    project_key: str | None
    summary: str | None
    description: str | None
    update_field: str | None
    update_value: str | None


# ---------------------------------------------------------
# Agent node: parse canonical commands
# ---------------------------------------------------------
def agent_node(state: AgentState):
    """
    Process user input and determine the next action.
    Uses STRICT, regex-based matching on canonical commands.
    """
    logger.info("Executing agent_node")

    messages = state["messages"]
    human_messages = [m for m in messages if isinstance(m, HumanMessage) and str(m.content).strip()]

    if not human_messages:
        logger.warning("No human message found - cannot proceed without human input")
        return {
            "messages": [AIMessage(content="I need a human message to proceed. Please provide instructions.")],
            "greeted": state.get("greeted", False),
            "status_filter": None,
            "ticket_to_summarize": None,
            "pending_approval_id": None,
            "operation_type": None,
        }

    last_msg_raw = str(messages[-1].content or "").strip()
    logger.info("Last user message: %s", last_msg_raw)

    # Helper to build a clean base state for this turn
    def base_state(extra: dict):
        base = {
            "greeted": state.get("greeted", False),
            "status_filter": None,
            "ticket_to_summarize": None,
            "pending_approval_id": None,
            "operation_type": None,
            "target_ticket_key": None,
            "target_status": None,
            "assignee": None,
            "comment_body": None,
            "project_key": None,
            "summary": None,
            "description": None,
            "update_field": None,
            "update_value": None,
        }
        base.update(extra)
        return base

    # --------------------------------------------------
    # 1) APPROVAL COMMANDS
    # --------------------------------------------------
    m = PATTERNS["approve"].fullmatch(last_msg_raw)
    if m:
        request_id = m.group(1)
        logger.info("Detected approve command for request_id=%s", request_id)

        # Mark request as approved
        if not approval_manager.approve(request_id, approved_by="user"):
            logger.warning("Approval request %s not found", request_id)
            return base_state({
                "messages": [AIMessage(content=f"❌ Approval request {request_id} not found or already processed.")],
            })

        # Find which operation this request corresponds to
        approval = approval_manager.get_approval(request_id) or next(
            (a for a in approval_manager.approval_history if a.request_id == request_id),
            None,
        )
        op_type = approval.operation_type if approval else None

        return base_state({
            "messages": [AIMessage(content=f"✅ Request {request_id} approved. Executing operation...")],
            "pending_approval_id": request_id,
            "operation_type": op_type,
        })

    m = PATTERNS["reject"].fullmatch(last_msg_raw)
    if m:
        request_id = m.group(1)
        logger.info("Detected reject command for request_id=%s", request_id)

        if approval_manager.reject(request_id, reason="Rejected from chat", rejected_by="user"):
            return base_state({
                "messages": [AIMessage(content=f"❌ Operation cancelled. Approval request {request_id} has been rejected.")],
            })
        else:
            return base_state({
                "messages": [AIMessage(content=f"❌ Approval request {request_id} not found or already processed.")],
            })

    # --------------------------------------------------
    # 2) READ OPERATIONS (no approval)
    # --------------------------------------------------
    if PATTERNS["show_my_tickets"].fullmatch(last_msg_raw):
        logger.info("Matched: show my tickets")
        return base_state({
            "messages": [AIMessage(content="Fetching all tickets assigned to or reported by you...")],
            "greeted": True,
        })

    m = PATTERNS["show_tickets_status"].fullmatch(last_msg_raw)
    if m:
        status = m.group(1).strip()
        logger.info("Matched: show tickets with status '%s'", status)
        return base_state({
            "messages": [AIMessage(content=f"Fetching your tickets with status '{status}'...")],
            "greeted": True,
            "status_filter": status,
        })

    m = PATTERNS["summarize_ticket"].fullmatch(last_msg_raw)
    if m:
        ticket_key = m.group(1).upper()
        logger.info("Matched: summarize ticket %s", ticket_key)
        return base_state({
            "messages": [AIMessage(content=f"Summarizing ticket {ticket_key}...")],
            "ticket_to_summarize": ticket_key,
        })

    # --------------------------------------------------
    # 3) WRITE OPERATIONS (approval required)
    # --------------------------------------------------
    m = PATTERNS["create_ticket"].fullmatch(last_msg_raw)
    if m:
        project_key, summary, description = m.groups()
        project_key = project_key.upper()
        logger.info("Matched: create ticket in %s", project_key)
        return base_state({
            "messages": [AIMessage(
                content=f"Preparing to create a ticket in project {project_key} "
                        f"with summary '{summary}'. I will show you a preview for approval."
            )],
            "operation_type": "create_ticket",
            "project_key": project_key,
            "summary": summary,
            "description": description,
        })

    m = PATTERNS["update_ticket"].fullmatch(last_msg_raw)
    if m:
        ticket_key, field, value = m.groups()
        ticket_key = ticket_key.upper()
        field = field.lower()
        logger.info("Matched: update ticket %s set %s", ticket_key, field)
        return base_state({
            "messages": [AIMessage(
                content=f"Preparing to update ticket {ticket_key}: set {field} to '{value}'. "
                        f"I will show you a preview for approval."
            )],
            "operation_type": "update_ticket",
            "target_ticket_key": ticket_key,
            "update_field": field,
            "update_value": value,
        })

    m = PATTERNS["transition_ticket"].fullmatch(last_msg_raw)
    if m:
        ticket_key, status = m.groups()
        ticket_key = ticket_key.upper()
        status = status.strip()
        logger.info("Matched: transition ticket %s to '%s'", ticket_key, status)
        return base_state({
            "messages": [AIMessage(
                content=f"Preparing to transition ticket {ticket_key} to '{status}'. "
                        f"I will show you a preview for approval."
            )],
            "operation_type": "transition_ticket",
            "target_ticket_key": ticket_key,
            "target_status": status,
        })

    m = PATTERNS["assign_ticket"].fullmatch(last_msg_raw)
    if m:
        ticket_key, assignee = m.groups()
        ticket_key = ticket_key.upper()
        assignee = assignee.strip()
        logger.info("Matched: assign ticket %s to '%s'", ticket_key, assignee)
        return base_state({
            "messages": [AIMessage(
                content=f"Preparing to assign ticket {ticket_key} to '{assignee}'. "
                        f"I will show you a preview for approval."
            )],
            "operation_type": "assign_ticket",
            "target_ticket_key": ticket_key,
            "assignee": assignee,
        })

    m = PATTERNS["add_comment"].fullmatch(last_msg_raw)
    if m:
        ticket_key, comment_body = m.groups()
        ticket_key = ticket_key.upper()
        logger.info("Matched: add comment to ticket %s", ticket_key)
        return base_state({
            "messages": [AIMessage(
                content=f"Preparing to add a comment to ticket {ticket_key}. "
                        f"I will show you a preview for approval."
            )],
            "operation_type": "add_comment",
            "target_ticket_key": ticket_key,
            "comment_body": comment_body,
        })

    # --------------------------------------------------
    # 4) FALLBACK TO LLM (general Q&A, etc.)
    # --------------------------------------------------
    logger.info("No canonical command matched. Falling back to LLM.")
    response = llm.invoke(human_messages)
    return base_state({
        "messages": [response],
    })


# ---------------------------------------------------------
# Read-only tool node
# ---------------------------------------------------------
def tool_node(state: AgentState):
    """Fetch tickets based on the status filter (read-only)."""
    logger.info("Executing tool_node")
    status = state.get("status_filter")

    tickets_text = fetch_tickets_by_status(status)
    return {
        "messages": [AIMessage(content=tickets_text)],
        "greeted": False,
        "status_filter": None,
        "ticket_to_summarize": None,
        "pending_approval_id": state.get("pending_approval_id"),
        "operation_type": state.get("operation_type"),
    }


# ---------------------------------------------------------
# Summarize ticket
# ---------------------------------------------------------
def summarize_ticket_node(state: AgentState):
    """Summarize a specific ticket (read-only)."""
    logger.info("Executing summarize_ticket_node")
    ticket_key = state.get("ticket_to_summarize")
    if not ticket_key:
        return state

    summary = fetch_and_summarize_ticket(ticket_key)
    return {
        "messages": [AIMessage(content=summary)],
        "greeted": state.get("greeted", False),
        "status_filter": None,
        "ticket_to_summarize": None,
        "pending_approval_id": state.get("pending_approval_id"),
        "operation_type": state.get("operation_type"),
    }


# ---------------------------------------------------------
# Approval node: create preview & approval request
# ---------------------------------------------------------
def approval_node(state: AgentState):
    """Create approval request and show preview."""
    logger.info("Executing approval_node")
    op_type = state.get("operation_type")

    if not op_type:
        return state

    if op_type == "create_ticket":
        project_key = state.get("project_key")
        summary = state.get("summary")
        description = state.get("description") or ""
        approval = create_ticket_with_approval(
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type="Task",
        )

    elif op_type == "update_ticket":
        ticket_key = state.get("target_ticket_key")
        field = state.get("update_field")
        value = state.get("update_value")

        kwargs = {}
        if field == "summary":
            kwargs["summary"] = value
        elif field == "description":
            kwargs["description"] = value
        elif field == "assignee":
            kwargs["assignee"] = value
        elif field == "priority":
            kwargs["priority"] = value
        elif field == "labels":
            # labels "a,b,c"
            kwargs["labels"] = [v.strip() for v in value.split(",") if v.strip()]

        approval = update_ticket_with_approval(ticket_key, **kwargs)

    elif op_type == "transition_ticket":
        ticket_key = state.get("target_ticket_key")
        target_status = state.get("target_status")
        approval = transition_ticket_with_approval(ticket_key, target_status)

    elif op_type == "assign_ticket":
        ticket_key = state.get("target_ticket_key")
        assignee = state.get("assignee")
        approval = assign_ticket_with_approval(ticket_key, assignee)

    elif op_type == "add_comment":
        ticket_key = state.get("target_ticket_key")
        comment_body = state.get("comment_body") or ""
        approval = add_comment_with_approval(ticket_key, comment_body)

    else:
        return state

    approval_msg = approval_manager.format_approval_message(approval)
    return {
        "messages": [AIMessage(content=approval_msg)],
        "greeted": state.get("greeted", False),
        "status_filter": None,
        "ticket_to_summarize": None,
        "pending_approval_id": approval.request_id,
        "operation_type": op_type,
    }


# ---------------------------------------------------------
# Execute node: run approved operation
# ---------------------------------------------------------
def execute_node(state: AgentState):
    """Execute approved operation."""
    logger.info("Executing execute_node")
    approval_id = state.get("pending_approval_id")
    op_type = state.get("operation_type")

    if not approval_id or not op_type:
        return {
            "messages": [AIMessage(content="No pending operation to execute.")],
            "greeted": state.get("greeted", False),
            "status_filter": None,
            "ticket_to_summarize": None,
            "pending_approval_id": None,
            "operation_type": None,
        }

    try:
        if op_type == "create_ticket":
            ticket_key = execute_create_ticket(approval_id)
            msg = f"✅ Ticket created successfully: {ticket_key}"
        elif op_type == "update_ticket":
            execute_update_ticket(approval_id)
            msg = "✅ Ticket updated successfully."
        elif op_type == "transition_ticket":
            execute_transition_ticket(approval_id)
            msg = "✅ Ticket transitioned successfully."
        elif op_type == "assign_ticket":
            execute_assign_ticket(approval_id)
            msg = "✅ Ticket assigned successfully."
        elif op_type == "add_comment":
            execute_add_comment(approval_id)
            msg = "✅ Comment added successfully."
        else:
            msg = "Unknown operation type; nothing executed."

        return {
            "messages": [AIMessage(content=msg)],
            "greeted": state.get("greeted", False),
            "status_filter": None,
            "ticket_to_summarize": None,
            "pending_approval_id": None,
            "operation_type": None,
        }
    except Exception as e:
        logger.exception("Error executing operation for approval_id=%s", approval_id)
        return {
            "messages": [AIMessage(content=f"❌ Error executing operation: {str(e)}")],
            "greeted": state.get("greeted", False),
            "status_filter": None,
            "ticket_to_summarize": None,
            "pending_approval_id": None,
            "operation_type": None,
        }


# ---------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------
logger.info("Setting up workflow graph with approval workflow")
workflow = StateGraph(state_schema=AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.add_node("summarizer", summarize_ticket_node)
workflow.add_node("approval", approval_node)
workflow.add_node("execute", execute_node)
workflow.set_entry_point("agent")


def route_after_agent(state: AgentState):
    """Route after agent node based on state."""
    approval_id = state.get("pending_approval_id")
    op_type = state.get("operation_type")

    # Write: have op_type but no approval yet → create preview
    if op_type and not approval_id:
        return "approval"

    # Have approval id + op type:
    # if approved → execute, otherwise wait
    if approval_id and op_type:
        if approval_manager.is_approved(approval_id):
            return "execute"
        return END

    # Read-only paths
    if state.get("status_filter") is not None or state.get("greeted", False):
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
        END: END,
    },
)

workflow.add_edge("tools", END)
workflow.add_edge("summarizer", END)
workflow.add_edge("approval", END)
workflow.add_edge("execute", END)

logger.info("Compiling workflow graph with approval workflow")
app = workflow.compile()
logger.info("Workflow graph compiled successfully")

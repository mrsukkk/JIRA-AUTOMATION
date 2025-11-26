"""
JIRA operations with human approval required.
All write operations must be approved before execution.
"""
import logging
from typing import Optional, Dict, List, Any
from tools.jira_operations import (
    create_ticket as _create_ticket,
    update_ticket as _update_ticket,
    transition_ticket as _transition_ticket,
    add_comment as _add_comment,
    assign_ticket as _assign_ticket,
    bulk_update_tickets as _bulk_update_tickets,
    get_ticket_details
)
from approval.approval_manager import approval_manager, ApprovalRequest

logger = logging.getLogger(__name__)


def create_ticket_with_approval(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Task",
    assignee: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None) -> ApprovalRequest:
    """
    Create a ticket approval request. Returns approval request, does NOT create ticket.
    User must approve before ticket is created.
    """
    logger.info("create_ticket_with_approval called for project_key=%s, summary=%s", project_key, summary)

    preview = {
        "project": project_key,
        "summary": summary,
        "description": description,
        "issue_type": issue_type,
        "assignee": assignee or "Unassigned",
        "priority": priority or "Medium",
        "labels": labels or []
    }
    
    description_text = f"Create new {issue_type} ticket in project {project_key}"
    
    approval = approval_manager.create_approval_request(
        operation_type="create_ticket",
        preview=preview,
        description=description_text,
        ticket_key=None
    )
    
    logger.info("Created approval request for ticket creation: %s", approval.request_id)
    logger.info("create_ticket_with_approval completed for request_id=%s", approval.request_id)
    return approval


def execute_create_ticket(approval_request_id: str) -> str:
    logger.info("execute_create_ticket called for approval_request_id=%s", approval_request_id)
    """
    Execute ticket creation after approval.
    
    Returns:
        Ticket key if successful
    """
    if not approval_manager.is_approved(approval_request_id):
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    approval = approval_manager.get_approval(approval_request_id)
    if not approval:
        # Check history
        for hist_approval in approval_manager.approval_history:
            if hist_approval.request_id == approval_request_id:
                approval = hist_approval
                break
    
    if not approval or approval.status.value != "approved":
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    preview = approval.preview
    
    ticket_key = _create_ticket(
        project_key=preview["project"],
        summary=preview["summary"],
        description=preview["description"],
        issue_type=preview.get("issue_type", "Task"),
        assignee=preview.get("assignee") if preview.get("assignee") != "Unassigned" else None,
        priority=preview.get("priority"),
        labels=preview.get("labels"),
        custom_fields=preview.get("custom_fields")
    )
    
    logger.info("Ticket created after approval: %s", ticket_key)
    logger.info("execute_create_ticket completed for ticket_key=%s", ticket_key)
    return ticket_key


def update_ticket_with_approval(
    ticket_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None
) -> ApprovalRequest:
    """
    Create an update approval request. Returns approval request, does NOT update ticket.
    """
    logger.info("update_ticket_with_approval called for ticket_key=%s", ticket_key)

    # Get current ticket details for comparison
    try:
        current = get_ticket_details(ticket_key)
    except Exception as e:
        logger.warning("Could not fetch current ticket details: %s", e)
        current = {}
    
    preview = {
        "ticket_key": ticket_key,
        "current_summary": current.get("summary"),
        "new_summary": summary,
        "current_description": current.get("description", "")[:100] + "..." if current.get("description") else None,
        "new_description": description[:100] + "..." if description else None,
        "current_assignee": current.get("assignee"),
        "new_assignee": assignee,
        "current_status": current.get("status"),
        "new_status": status,
        "current_priority": current.get("priority"),
        "new_priority": priority,
        "current_labels": current.get("labels", []),
        "new_labels": labels
    }
    
    changes = []
    if summary and summary != current.get("summary"):
        changes.append(f"Summary: '{current.get('summary')}' → '{summary}'")
    if assignee and assignee != current.get("assignee"):
        changes.append(f"Assignee: '{current.get('assignee')}' → '{assignee}'")
    if status and status != current.get("status"):
        changes.append(f"Status: '{current.get('status')}' → '{status}'")
    if priority and priority != current.get("priority"):
        changes.append(f"Priority: '{current.get('priority')}' → '{priority}'")
    
    description_text = f"Update ticket {ticket_key}\nChanges:\n" + "\n".join(f"  - {c}" for c in changes)
    
    approval = approval_manager.create_approval_request(
        operation_type="update_ticket",
        preview=preview,
        description=description_text,
        ticket_key=ticket_key
    )
    
    logger.info("Created approval request for ticket update: %s", approval.request_id)
    logger.info("update_ticket_with_approval completed for request_id=%s", approval.request_id)
    return approval


def execute_update_ticket(approval_request_id: str) -> bool:
    logger.info("execute_update_ticket called for approval_request_id=%s", approval_request_id)
    """Execute ticket update after approval."""
    if not approval_manager.is_approved(approval_request_id):
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    approval = approval_manager.get_approval(approval_request_id)
    if not approval:
        for hist_approval in approval_manager.approval_history:
            if hist_approval.request_id == approval_request_id:
                approval = hist_approval
                break
    
    if not approval or approval.status.value != "approved":
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    preview = approval.preview
    ticket_key = preview["ticket_key"]
    
    success = _update_ticket(
        ticket_key=ticket_key,
        summary=preview.get("new_summary"),
        description=preview.get("new_description"),
        assignee=preview.get("new_assignee"),
        status=preview.get("new_status"),
        priority=preview.get("new_priority"),
        labels=preview.get("new_labels"),
        custom_fields=preview.get("custom_fields")
    )
    
    logger.info("Ticket updated after approval: %s", ticket_key)
    logger.info("execute_update_ticket completed for ticket_key=%s", ticket_key)
    return success


def transition_ticket_with_approval(
    ticket_key: str,
    target_status: str,
    comment: Optional[str] = None
) -> ApprovalRequest:
    """Create a transition approval request."""
    logger.info("transition_ticket_with_approval called for ticket_key=%s, target_status=%s", ticket_key, target_status)

    try:
        current = get_ticket_details(ticket_key)
    except Exception as e:
        logger.warning("Could not fetch current ticket details: %s", e)
        current = {}
    
    preview = {
        "ticket_key": ticket_key,
        "current_status": current.get("status"),
        "target_status": target_status,
        "comment": comment
    }
    
    description_text = f"Transition ticket {ticket_key} from '{current.get('status')}' to '{target_status}'"
    if comment:
        description_text += f"\nComment: {comment}"
    
    approval = approval_manager.create_approval_request(
        operation_type="transition_ticket",
        preview=preview,
        description=description_text,
        ticket_key=ticket_key
    )
    
    logger.info("Created approval request for ticket transition: %s", approval.request_id)
    logger.info("transition_ticket_with_approval completed for request_id=%s", approval.request_id)
    return approval


def execute_transition_ticket(approval_request_id: str) -> bool:
    logger.info("execute_transition_ticket called for approval_request_id=%s", approval_request_id)
    """Execute ticket transition after approval."""
    if not approval_manager.is_approved(approval_request_id):
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    approval = approval_manager.get_approval(approval_request_id)
    if not approval:
        for hist_approval in approval_manager.approval_history:
            if hist_approval.request_id == approval_request_id:
                approval = hist_approval
                break
    
    if not approval or approval.status.value != "approved":
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    preview = approval.preview
    
    success = _transition_ticket(
        ticket_key=preview["ticket_key"],
        target_status=preview["target_status"],
        comment=preview.get("comment")
    )
    
    logger.info("Ticket transitioned after approval: %s", preview["ticket_key"])
    logger.info("execute_transition_ticket completed for ticket_key=%s", preview["ticket_key"])
    return success


def assign_ticket_with_approval(ticket_key: str, assignee: str) -> ApprovalRequest:
    logger.info("assign_ticket_with_approval called for ticket_key=%s, assignee=%s", ticket_key, assignee)
    """Create an assignment approval request."""
    try:
        current = get_ticket_details(ticket_key)
    except Exception as e:
        logger.warning("Could not fetch current ticket details: %s", e)
        current = {}
    
    preview = {
        "ticket_key": ticket_key,
        "current_assignee": current.get("assignee", "Unassigned"),
        "new_assignee": assignee
    }
    
    description_text = f"Assign ticket {ticket_key} to {assignee}"
    if current.get("assignee"):
        description_text += f" (currently assigned to {current.get('assignee')})"
    
    approval = approval_manager.create_approval_request(
        operation_type="assign_ticket",
        preview=preview,
        description=description_text,
        ticket_key=ticket_key
    )
    
    logger.info("Created approval request for ticket assignment: %s", approval.request_id)
    logger.info("assign_ticket_with_approval completed for request_id=%s", approval.request_id)
    return approval


def execute_assign_ticket(approval_request_id: str) -> bool:
    logger.info("execute_assign_ticket called for approval_request_id=%s", approval_request_id)
    """Execute ticket assignment after approval."""
    if not approval_manager.is_approved(approval_request_id):
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    approval = approval_manager.get_approval(approval_request_id)
    if not approval:
        for hist_approval in approval_manager.approval_history:
            if hist_approval.request_id == approval_request_id:
                approval = hist_approval
                break
    
    if not approval or approval.status.value != "approved":
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    preview = approval.preview
    
    success = _assign_ticket(
        ticket_key=preview["ticket_key"],
        assignee=preview["new_assignee"]
    )
    
    logger.info("Ticket assigned after approval: %s", preview["ticket_key"])
    logger.info("execute_assign_ticket completed for ticket_key=%s", preview["ticket_key"])
    return success


def add_comment_with_approval(ticket_key: str, comment_body: str, visibility: Optional[str] = None) -> ApprovalRequest:
    logger.info("add_comment_with_approval called for ticket_key=%s", ticket_key)
    """Create a comment approval request."""
    preview = {
        "ticket_key": ticket_key,
        "comment": comment_body,
        "visibility": visibility
    }
    
    description_text = f"Add comment to ticket {ticket_key}"
    
    approval = approval_manager.create_approval_request(
        operation_type="add_comment",
        preview=preview,
        description=description_text,
        ticket_key=ticket_key
    )
    
    logger.info("Created approval request for comment: %s", approval.request_id)
    logger.info("add_comment_with_approval completed for request_id=%s", approval.request_id)
    return approval


def execute_add_comment(approval_request_id: str) -> bool:
    logger.info("execute_add_comment called for approval_request_id=%s", approval_request_id)
    """Execute comment addition after approval."""
    if not approval_manager.is_approved(approval_request_id):
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    approval = approval_manager.get_approval(approval_request_id)
    if not approval:
        for hist_approval in approval_manager.approval_history:
            if hist_approval.request_id == approval_request_id:
                approval = hist_approval
                break
    
    if not approval or approval.status.value != "approved":
        raise ValueError(f"Approval request {approval_request_id} not approved")
    
    preview = approval.preview
    
    success = _add_comment(
        ticket_key=preview["ticket_key"],
        comment_body=preview["comment"],
        visibility=preview.get("visibility")
    )
    
    logger.info("Comment added after approval to ticket: %s", preview["ticket_key"])
    logger.info("execute_add_comment completed for ticket_key=%s", preview["ticket_key"])
    return success


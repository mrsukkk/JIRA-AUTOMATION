"""
Minimal JIRA operations used by the agent + approval workflow.
"""

import logging
from typing import Optional, Dict, List, Any
from jira import JIRA
from jira.exceptions import JIRAError
from tools.jira_tool import get_jira_client

logger = logging.getLogger(__name__)


# =====================================================
# ===============  TICKET CREATION  ===================
# =====================================================

def create_ticket(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Task",
    assignee: Optional[str] = None,
) -> str:
    """
    Create a new JIRA ticket.
    """
    logger.info("Creating ticket %s: %s", project_key, summary)

    try:
        jira = get_jira_client()

        issue_dict = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description or "",
            "issuetype": {"name": issue_type},
        }

        if assignee:
            issue_dict["assignee"] = {"name": assignee}

        issue = jira.create_issue(fields=issue_dict)
        logger.info("Created ticket: %s", issue.key)
        return issue.key

    except JIRAError as e:
        logger.error("Failed to create ticket: %s", e)
        raise


# =====================================================
# ===============  COMMENT OPERATIONS  ================
# =====================================================

def add_comment(ticket_key: str, comment_body: str) -> bool:
    """
    Add comment to a ticket.
    """
    logger.info("Adding comment to %s", ticket_key)

    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        jira.add_comment(issue, comment_body)

        logger.info("Comment added to %s", ticket_key)
        return True

    except JIRAError as e:
        logger.error("Failed to add comment: %s", e)
        raise


# =====================================================
# ============  TRANSITION A TICKET  ==================
# =====================================================

def transition_ticket(ticket_key: str, target_status: str) -> bool:
    """
    Transition a ticket to another status.
    """
    logger.info("Transitioning %s to %s", ticket_key, target_status)

    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)

        transitions = jira.transitions(issue)
        transition_id = None

        for t in transitions:
            if t["to"]["name"].lower() == target_status.lower():
                transition_id = t["id"]
                break

        if not transition_id:
            logger.warning("No direct match found for status=%s", target_status)
            if transitions:
                transition_id = transitions[0]["id"]
            else:
                raise ValueError(f"No transitions available for {ticket_key}")

        jira.transition_issue(issue, transition_id)
        logger.info("Transition successful: %s → %s", ticket_key, target_status)
        return True

    except Exception as e:
        logger.error("Transition failed: %s", e)
        raise


# =====================================================
# ================== ASSIGNMENT =======================
# =====================================================

def assign_ticket(ticket_key: str, assignee: str) -> bool:
    """
    Assign a ticket to a user.
    """
    logger.info("Assigning %s to %s", ticket_key, assignee)

    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        issue.update(fields={"assignee": {"name": assignee}})

        logger.info("Assigned %s → %s", ticket_key, assignee)
        return True

    except JIRAError as e:
        logger.error("Failed to assign ticket: %s", e)
        raise


# =====================================================
# ================ UPDATE SUMMARY =====================
# =====================================================

def update_ticket(ticket_key: str, summary: Optional[str] = None) -> bool:
    """
    Update ticket summary (used by approval workflow).
    """
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)

        update_payload = {}
        if summary:
            update_payload["summary"] = summary

        if update_payload:
            issue.update(fields=update_payload)
            logger.info("Updated summary for %s", ticket_key)

        return True

    except JIRAError as e:
        logger.error("Failed to update ticket: %s", e)
        raise


# =====================================================
# =============== BASIC READ OPERATIONS ===============
# =====================================================

def search_tickets(jql: str, max_results: int = 50) -> List[Any]:
    """
    Search tickets using JQL.
    """
    logger.info("Searching: %s", jql)

    try:
        jira = get_jira_client()
        return jira.search_issues(jql, maxResults=max_results)

    except JIRAError as e:
        logger.error("JQL search failed: %s", e)
        raise


def get_ticket_details(ticket_key: str) -> Dict[str, Any]:
    """
    Return basic ticket details used by summarization and UI.
    """
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)

        return {
            "key": issue.key,
            "summary": issue.fields.summary,
            "description": issue.fields.description,
            "status": issue.fields.status.name,
            "assignee": issue.fields.assignee.displayName if issue.fields.assignee else None,
            "reporter": issue.fields.reporter.displayName if issue.fields.reporter else None,
            "comments": [c.body for c in issue.fields.comment.comments] if issue.fields.comment else []
        }

    except JIRAError as e:
        logger.error("Failed to fetch ticket details: %s", e)
        raise

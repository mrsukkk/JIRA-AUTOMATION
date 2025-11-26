"""
Comprehensive JIRA operations for fully autonomous ticket management.
Based on JIRA REST API v3: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
"""
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from jira import JIRA
from jira.exceptions import JIRAError
from config.settings import settings
from tools.jira_tool import get_jira_client

logger = logging.getLogger(__name__)


# ==================== TICKET CREATION ====================

def create_ticket(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Task",
    assignee: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a new JIRA ticket.
    
    Args:
        project_key: Project key (e.g., "PROJ")
        summary: Ticket summary/title
        description: Ticket description
        issue_type: Type of issue (Task, Bug, Story, etc.)
        assignee: Username or account ID to assign to
        priority: Priority level (Highest, High, Medium, Low, Lowest)
        labels: List of labels to add
        custom_fields: Dict of custom field IDs and values
        
    Returns:
        Ticket key (e.g., "PROJ-123")
    """
    logger.info("create_ticket called for project_key=%s, summary=%s", project_key, summary)

    logger.info("Creating ticket in project %s: %s", project_key, summary)
    try:
        jira = get_jira_client()
        
        issue_dict = {
            'project': {'key': project_key},
            'summary': summary,
            'description': description or '',
            'issuetype': {'name': issue_type}
        }
        
        if assignee:
            issue_dict['assignee'] = {'name': assignee}
        if priority:
            issue_dict['priority'] = {'name': priority}
        if labels:
            issue_dict['labels'] = labels
        if custom_fields:
            issue_dict.update(custom_fields)
        
        new_issue = jira.create_issue(fields=issue_dict)
        logger.info("Created ticket: %s", new_issue.key)
        logger.info("create_ticket completed for ticket_key=%s", new_issue.key)
        return new_issue.key
    except JIRAError as e:
        logger.error("Failed to create ticket: %s", e)
        raise


def create_ticket_from_template(
    project_key: str,
    template_name: str,
    template_data: Dict[str, Any]
) -> str:
    """Create a ticket from a predefined template."""
    
    logger.info("Creating ticket from template %s", template_name)
    # This would use LLM to generate ticket details from template
    # For now, basic implementation
    summary = template_data.get('summary', '')
    description = template_data.get('description', '')
    result = create_ticket(project_key, summary, description, **template_data)
    logger.info("create_ticket_from_template completed for project_key=%s, template_name=%s", project_key, template_name)
    return result


# ==================== TICKET UPDATES ====================

def update_ticket(
    ticket_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Update a JIRA ticket.
    
    Returns:
        True if successful
    """
    logger.info("Updating ticket: %s", ticket_key)
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        
        update_dict = {}
        if summary:
            update_dict['summary'] = summary
        if description is not None:
            update_dict['description'] = description
        if assignee:
            update_dict['assignee'] = {'name': assignee}
        if priority:
            update_dict['priority'] = {'name': priority}
        if labels:
            update_dict['labels'] = labels
        if custom_fields:
            update_dict.update(custom_fields)
        
        if update_dict:
            issue.update(fields=update_dict)
            logger.info("Updated ticket: %s", ticket_key)
        
        # Handle status transition separately
        if status:
            transition_ticket(ticket_key, status)
        
        logger.info("update_ticket completed for ticket_key=%s", ticket_key)
        return True
    except JIRAError as e:
        logger.error("Failed to update ticket %s: %s", ticket_key, e)
        raise


def transition_ticket(ticket_key: str, target_status: str, comment: Optional[str] = None) -> bool:
    logger.info("transition_ticket called for ticket_key=%s, target_status=%s", ticket_key, target_status)
    """
    Transition a ticket to a new status.
    
    Args:
        ticket_key: Ticket to transition
        target_status: Target status name
        comment: Optional comment to add during transition
        
    Returns:
        True if successful
    """
    logger.info("Transitioning ticket %s to status: %s", ticket_key, target_status)
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        
        # Get available transitions
        transitions = jira.transitions(issue)
        transition_id = None
        
        for transition in transitions:
            if transition['to']['name'].lower() == target_status.lower():
                transition_id = transition['id']
                break
        
        if not transition_id:
            # Try to find by status ID or use first available
            logger.warning("Exact status match not found, attempting transition")
            if transitions:
                transition_id = transitions[0]['id']
            else:
                raise ValueError(f"No transitions available for ticket {ticket_key}")
        
        # Perform transition
        jira.transition_issue(issue, transition_id, comment=comment)
        logger.info("Successfully transitioned ticket %s to %s", ticket_key, target_status)
        logger.info("transition_ticket completed for ticket_key=%s, target_status=%s", ticket_key, target_status)
        return True
    except JIRAError as e:
        logger.error("Failed to transition ticket %s: %s", ticket_key, e)
        raise


# ==================== COMMENTS ====================

def add_comment(ticket_key: str, comment_body: str, visibility: Optional[str] = None) -> bool:
    logger.info("add_comment called for ticket_key=%s", ticket_key)
    """
    Add a comment to a ticket.
    
    Args:
        ticket_key: Ticket to comment on
        comment_body: Comment text
        visibility: Optional visibility (e.g., "role", "group")
        
    Returns:
        True if successful
    """
    logger.info("Adding comment to ticket: %s", ticket_key)
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        
        comment_data = {'body': comment_body}
        if visibility:
            comment_data['visibility'] = visibility
        
        jira.add_comment(issue, comment_body)
        logger.info("Comment added to ticket: %s", ticket_key)
        logger.info("add_comment completed for ticket_key=%s", ticket_key)
        return True
    except JIRAError as e:
        logger.error("Failed to add comment to ticket %s: %s", ticket_key, e)
        raise


# ==================== BULK OPERATIONS ====================

def bulk_update_tickets(
    ticket_keys: List[str],
    updates: Dict[str, Any],
    comment: Optional[str] = None
) -> Dict[str, bool]:
    """
    Bulk update multiple tickets.
    
    Returns:
        Dict mapping ticket keys to success status
    """
    logger.info("Bulk updating %d tickets", len(ticket_keys))
    results = {}
    
    for ticket_key in ticket_keys:
        try:
            update_ticket(ticket_key, **updates)
            if comment:
                add_comment(ticket_key, comment)
            results[ticket_key] = True
        except Exception as e:
            logger.error("Failed to update ticket %s: %s", ticket_key, e)
            results[ticket_key] = False
    
    logger.info("Bulk update completed: %d successful, %d failed", 
                sum(results.values()), len(results) - sum(results.values()))
    logger.info("bulk_update_tickets completed: %d successful, %d failed", sum(results.values()), len(results) - sum(results.values()))
    return results


def bulk_transition_tickets(
    ticket_keys: List[str],
    target_status: str,
    comment: Optional[str] = None
) -> Dict[str, bool]:
    """Bulk transition multiple tickets to a status."""
    logger.info("Bulk transitioning %d tickets to %s", len(ticket_keys), target_status)
    results = {}
    
    for ticket_key in ticket_keys:
        try:
            transition_ticket(ticket_key, target_status, comment)
            results[ticket_key] = True
        except Exception as e:
            logger.error("Failed to transition ticket %s: %s", ticket_key, e)
            results[ticket_key] = False
    
    logger.info("bulk_transition_tickets completed for %d tickets to %s", len(ticket_keys), target_status)
    return results


# ==================== SEARCH & QUERY ====================

def search_tickets(jql: str, max_results: int = 50, fields: Optional[List[str]] = None) -> List[Any]:
    logger.info("search_tickets called with JQL: %s", jql)
    """
    Search tickets using JQL (JIRA Query Language).
    
    Args:
        jql: JQL query string
        max_results: Maximum number of results
        fields: Optional list of fields to return
        
    Returns:
        List of issue objects
    """
    logger.info("Searching tickets with JQL: %s", jql)
    try:
        jira = get_jira_client()
        issues = jira.search_issues(jql, maxResults=max_results, fields=fields)
        logger.info("Found %d tickets", len(issues))
        logger.info("search_tickets completed with %d tickets", len(issues))
        return issues
    except JIRAError as e:
        logger.error("Failed to search tickets: %s", e)
        raise


def get_ticket_details(ticket_key: str, expand: Optional[List[str]] = None) -> Dict[str, Any]:
    logger.info("get_ticket_details called for ticket_key=%s", ticket_key)
    """
    Get detailed information about a ticket.
    
    Args:
        ticket_key: Ticket to retrieve
        expand: Optional list of fields to expand
        
    Returns:
        Dict with ticket details
    """
    logger.info("Fetching details for ticket: %s", ticket_key)
    try:
        jira = get_jira_client()
        expand_str = ','.join(expand) if expand else None
        issue = jira.issue(ticket_key, expand=expand_str)
        
        result = {
            'key': issue.key,
            'summary': issue.fields.summary,
            'description': issue.fields.description,
            'status': issue.fields.status.name,
            'assignee': issue.fields.assignee.displayName if issue.fields.assignee else None,
            'reporter': issue.fields.reporter.displayName if issue.fields.reporter else None,
            'priority': issue.fields.priority.name if issue.fields.priority else None,
            'created': issue.fields.created,
            'updated': issue.fields.updated,
            'labels': issue.fields.labels,
            'comments': [c.body for c in (issue.fields.comment.comments if issue.fields.comment else [])]
        }
        logger.info("get_ticket_details completed for ticket_key=%s", ticket_key)
        return result
    except JIRAError as e:
        logger.error("Failed to get ticket details for %s: %s", ticket_key, e)
        raise


# ==================== ASSIGNMENT & ROUTING ====================

def assign_ticket(ticket_key: str, assignee: str) -> bool:
    logger.info("assign_ticket called for ticket_key=%s, assignee=%s", ticket_key, assignee)
    """Assign a ticket to a user."""
    logger.info("Assigning ticket %s to %s", ticket_key, assignee)
    result = update_ticket(ticket_key, assignee=assignee)
    logger.info("assign_ticket completed for ticket_key=%s, assignee=%s", ticket_key, assignee)
    return result


def auto_assign_ticket(ticket_key: str, assignment_rules: Dict[str, Any]) -> Optional[str]:
    logger.info("auto_assign_ticket called for ticket_key=%s", ticket_key)
    """
    Automatically assign a ticket based on rules.
    
    Args:
        ticket_key: Ticket to assign
        assignment_rules: Rules for assignment (project, component, labels, etc.)
        
    Returns:
        Username of assigned user, or None if no assignment made
    """
    logger.info("Auto-assigning ticket: %s", ticket_key)
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        
        # Get project components and potential assignees
        project = jira.project(issue.fields.project.key)
        
        # Simple rule: assign based on component
        if issue.fields.components:
            component = issue.fields.components[0]
            # Get component lead if available
            if hasattr(component, 'lead') and component.lead:
                assignee = component.lead.name
                assign_ticket(ticket_key, assignee)
                logger.info("Auto-assigned ticket %s to %s (component lead)", ticket_key, assignee)
                logger.info("auto_assign_ticket completed for ticket_key=%s, assignee=%s", ticket_key, assignee)
                return assignee
        
        # Fallback: round-robin or workload-based assignment
        # This would require additional logic to track workload
        logger.warning("No auto-assignment rule matched for ticket %s", ticket_key)
        logger.info("auto_assign_ticket completed for ticket_key=%s, no assignment", ticket_key)
        return None
    except Exception as e:
        logger.error("Failed to auto-assign ticket %s: %s", ticket_key, e)
        return None


# ==================== SLA MONITORING ====================

def check_sla_status(ticket_key: str, sla_hours: int = 24) -> Dict[str, Any]:
    logger.info("check_sla_status called for ticket_key=%s", ticket_key)
    """
    Check if a ticket is within SLA.
    
    Args:
        ticket_key: Ticket to check
        sla_hours: SLA threshold in hours
        
    Returns:
        Dict with SLA status information
    """
    logger.info("Checking SLA for ticket: %s", ticket_key)
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        
        created = datetime.strptime(issue.fields.created, '%Y-%m-%dT%H:%M:%S.%f%z')
        now = datetime.now(created.tzinfo)
        age_hours = (now - created).total_seconds() / 3600
        
        within_sla = age_hours < sla_hours
        hours_remaining = max(0, sla_hours - age_hours) if within_sla else 0
        hours_overdue = max(0, age_hours - sla_hours) if not within_sla else 0
        
        result = {
            'ticket_key': ticket_key,
            'status': issue.fields.status.name,
            'age_hours': age_hours,
            'within_sla': within_sla,
            'hours_remaining': hours_remaining,
            'hours_overdue': hours_overdue,
            'sla_threshold_hours': sla_hours
        }
        logger.info("check_sla_status completed for ticket_key=%s", ticket_key)
        return result
    except Exception as e:
        logger.error("Failed to check SLA for ticket %s: %s", ticket_key, e)
        raise


def find_overdue_tickets(sla_hours: int = 24, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    logger.info("find_overdue_tickets called with SLA: %d hours", sla_hours)
    """
    Find tickets that are overdue based on SLA.
    
    Returns:
        List of overdue ticket information
    """
    logger.info("Finding overdue tickets (SLA: %d hours)", sla_hours)
    try:
        # Build JQL query
        jql = f"status != Closed AND status != Resolved"
        if status_filter:
            jql += f" AND status = '{status_filter}'"
        jql += " ORDER BY created ASC"
        
        issues = search_tickets(jql, max_results=100)
        overdue = []
        
        for issue in issues:
            sla_info = check_sla_status(issue.key, sla_hours)
            if not sla_info['within_sla']:
                overdue.append(sla_info)
        
        logger.info("Found %d overdue tickets", len(overdue))
        logger.info("find_overdue_tickets completed: %d overdue tickets", len(overdue))
        return overdue
    except Exception as e:
        logger.error("Failed to find overdue tickets: %s", e)
        raise


# ==================== DUPLICATE DETECTION ====================

def find_duplicate_tickets(ticket_key: str, similarity_threshold: float = 0.8) -> List[str]:
    logger.info("find_duplicate_tickets called for ticket_key=%s", ticket_key)
    """
    Find potentially duplicate tickets using similarity matching.
    
    Args:
        ticket_key: Ticket to check for duplicates
        similarity_threshold: Similarity score threshold (0-1)
        
    Returns:
        List of potentially duplicate ticket keys
    """
    logger.info("Finding duplicates for ticket: %s", ticket_key)
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)
        
        # Search for tickets with similar summary
        summary_words = issue.fields.summary.lower().split()
        if len(summary_words) < 2:
            return []
        
        # Build JQL query for similar tickets
        jql = f"project = {issue.fields.project.key} AND key != {ticket_key} AND status != Closed"
        similar_issues = search_tickets(jql, max_results=50)
        
        # Simple similarity check (would use LLM for better matching)
        duplicates = []
        for similar_issue in similar_issues:
            similar_summary = similar_issue.fields.summary.lower()
            common_words = sum(1 for word in summary_words if word in similar_summary)
            similarity = common_words / max(len(summary_words), len(similar_summary.split()))
            
            if similarity >= similarity_threshold:
                duplicates.append(similar_issue.key)
        
        logger.info("Found %d potential duplicates for ticket %s", len(duplicates), ticket_key)
        logger.info("find_duplicate_tickets completed for ticket_key=%s: %d duplicates", ticket_key, len(duplicates))
        return duplicates
    except Exception as e:
        logger.error("Failed to find duplicates for ticket %s: %s", ticket_key, e)
        return []


# ==================== PROJECT & USER INFO ====================

def get_project_info(project_key: str) -> Dict[str, Any]:
    logger.info("get_project_info called for project_key=%s", project_key)
    """Get information about a JIRA project."""
    logger.info("Fetching project info: %s", project_key)
    try:
        jira = get_jira_client()
        project = jira.project(project_key)
        
        result = {
            'key': project.key,
            'name': project.name,
            'lead': project.lead.displayName if project.lead else None,
            'components': [c.name for c in project.components],
            'issue_types': [it.name for it in project.issueTypes]
        }
        logger.info("get_project_info completed for project_key=%s", project_key)
        return result
    except JIRAError as e:
        logger.error("Failed to get project info for %s: %s", project_key, e)
        raise


def get_user_info(username: str) -> Dict[str, Any]:
    logger.info("get_user_info called for username=%s", username)
    """Get information about a JIRA user."""
    logger.info("Fetching user info: %s", username)
    try:
        jira = get_jira_client()
        user = jira.user(username)
        
        result = {
            'name': user.name,
            'display_name': user.displayName,
            'email': user.emailAddress if hasattr(user, 'emailAddress') else None,
            'active': user.active if hasattr(user, 'active') else True
        }
        logger.info("get_user_info completed for username=%s", username)
        return result
    except JIRAError as e:
        logger.error("Failed to get user info for %s: %s", username, e)
        raise


def get_user_workload(username: str) -> Dict[str, int]:
    logger.info("get_user_workload called for username=%s", username)
    """
    Get workload statistics for a user.
    
    Returns:
        Dict with ticket counts by status
    """
    logger.info("Fetching workload for user: %s", username)
    try:
        jql = f"assignee = {username} AND status != Closed"
        issues = search_tickets(jql, max_results=1000)
        
        workload = {}
        for issue in issues:
            status = issue.fields.status.name
            workload[status] = workload.get(status, 0) + 1
        
        logger.info("User %s workload: %s", username, workload)
        logger.info("get_user_workload completed for username=%s", username)
        return workload
    except Exception as e:
        logger.error("Failed to get workload for user %s: %s", username, e)
        return {}


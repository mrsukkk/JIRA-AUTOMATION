import os
import pandas as pd
import pdfplumber
import requests
import logging
from docx import Document
from jira import JIRA
from jira.exceptions import JIRAError
from config.settings import settings
from models.llm_config import LLMConfig
from langchain_core.messages import HumanMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Removed FileHandler for jira_utils.log
)
logger = logging.getLogger(__name__)

# Constants
ATTACHMENT_DIR = "jira_attachments"
TEXT_EXTENSIONS = {".txt", ".csv", ".json", ".md", ".log"}
PDF_EXTENSIONS = {".pdf"}
EXCEL_EXTENSIONS = {".xls", ".xlsx"}
WORD_EXTENSIONS = {".docx"}  # Removed .doc
CHUNK_SIZE = 8000  # Characters per chunk for LLM summarization

def get_jira_client():
    logger.info("get_jira_client called")
    """Initialize and return a Jira client using settings from config."""
    logger.info("Initializing Jira client")
    try:
        jira = JIRA(
            server=settings.JIRA_BASE_URL,
            basic_auth=(settings.JIRA_USERNAME, settings.JIRA_PAT)
        )
        logger.debug("Jira client initialized successfully")
        logger.info("get_jira_client completed")
        return jira
    except JIRAError as e:
        logger.error("Failed to initialize Jira client: %s", e)
        raise

def fetch_tickets_by_status(status: str = None):
    logger.info("fetch_tickets_by_status called with status=%s", status)
    """
    Fetch tickets assigned to, reported by, or mentioning the current user.
    Optionally filter by status (e.g., 'Closed', 'In Progress').
    Returns a human-readable string grouped by role.
    """
    logger.info("Fetching tickets with status: %s", status if status else "All")
    try:
        jira = get_jira_client()
        current_user = jira.current_user()
        logger.debug("Current user: %s", current_user)
        profile = jira.user(current_user)
        display_name = profile.displayName
        account_id = profile.raw.get('accountId')  # Correctly access accountId from raw JSON
        logger.info("User display name: %s", display_name)

        # JQL queries for assigned, reported, and mentioned tickets
        status_clause = f" AND status = '{status}'" if status else ""
        assigned_jql = f"assignee = currentUser(){status_clause} ORDER BY updated DESC"
        reported_jql = f"reporter = currentUser(){status_clause} ORDER BY updated DESC"
        # all_issues_jql = f'text ~ "{display_name}"{status_clause} ORDER BY updated DESC'

        # Fetch tickets
        logger.debug("Fetching assigned tickets with JQL: %s", assigned_jql)
        assigned_issues = jira.search_issues(assigned_jql, maxResults=None)
        logger.info("Found %d assigned tickets", len(assigned_issues))
        
        logger.debug("Fetching reported tickets with JQL: %s", reported_jql)
        reported_issues = jira.search_issues(reported_jql, maxResults=None)
        logger.info("Found %d reported tickets", len(reported_issues))

        # Fetch mentioned tickets
        # mentioned_issues = []
        # start_at = 0
        # batch_size = 50
        # logger.debug("Fetching mentioned tickets with JQL: %s", all_issues_jql)
        # while True:
        #     issues = jira.search_issues(all_issues_jql, startAt=start_at, maxResults=batch_size, fields="summary,status,comment")
        #     if not issues:
        #         logger.debug("No more issues to fetch for mentioned tickets")
        #         break
        #     for issue in issues:
        #         if issue in assigned_issues or issue in reported_issues:
        #             continue
        #         comments = getattr(issue.fields, "comment", {}).comments or []
        #         for comment in comments:
        #             if f"[~accountid:{account_id}]" in comment.body.lower():
        #                 mentioned_issues.append(issue)
        #                 logger.debug("Found mentioned ticket: %s", issue.key)
        #                 break
        #     start_at += batch_size
        # logger.info("Found %d mentioned tickets", len(mentioned_issues))

        # Helper function to format issues
        def format_issues(issues):
            return [
                f"[{issue.key}] {issue.fields.summary} (Status: {issue.fields.status.name})"
                for issue in issues
            ]

        # Build output
        output_lines = []
        if assigned_issues:
            output_lines.append("🔹 Assigned to You:")
            output_lines.extend(f"  {i+1}. {line}" for i, line in enumerate(format_issues(assigned_issues)))
        if reported_issues:
            output_lines.append("\n🔹 Reported by You:")
            output_lines.extend(f"  {i+1}. {line}" for i, line in enumerate(format_issues(reported_issues)))
        # if mentioned_issues:
        #     output_lines.append("\n🔹 You are Mentioned in:")
        #     output_lines.extend(f"  {i+1}. {line}" for i, line in enumerate(format_issues(mentioned_issues)))

        if output_lines:
            logger.info("Tickets fetched successfully")
            logger.info("fetch_tickets_by_status completed with tickets found")
            return "\n".join(output_lines)
        else:
            message = f"No tickets found for status '{status}'." if status else "No tickets found."
            logger.info(message)
            logger.info("fetch_tickets_by_status completed with no tickets found")
            return message
    except Exception as e:
        logger.error("Error fetching tickets: %s", e)
        raise

def summarize_large_text(text: str, llm):
    logger.info("summarize_large_text called with text length=%d", len(text))
    """Summarize large text by chunking it for LLM processing."""
    logger.info("Summarizing text of length: %d characters", len(text))
    summaries = []
    try:
        for i in range(0, len(text), CHUNK_SIZE):
            chunk = text[i:i + CHUNK_SIZE]
            logger.debug("Processing chunk %d to %d", i, i + CHUNK_SIZE)
            response = llm.invoke([
                HumanMessage(content=f"Summarize this part of a Jira ticket attachment:\n\n{chunk}")
            ])
            summaries.append(response.content)
            logger.debug("Chunk summary generated")
        logger.info("Text summarization completed")
        logger.info("summarize_large_text completed")
        return "\n".join(summaries)
    except Exception as e:
        logger.error("Error summarizing text: %s", e)
        raise

def extract_text_from_attachment(filepath: str, ext: str):
    logger.info("extract_text_from_attachment called for filepath=%s, ext=%s", filepath, ext)
    """Extract text from various file types (text, PDF, Excel, Word)."""
    logger.info("Extracting text from attachment: %s", filepath)
    try:
        if ext in TEXT_EXTENSIONS:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                logger.debug("Extracted text from %s", filepath)
                logger.info("extract_text_from_attachment completed for text file: %s", filepath)
                return content
        elif ext in PDF_EXTENSIONS:
            text = ""
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
            logger.debug("Extracted text from PDF: %s", filepath)
            logger.info("extract_text_from_attachment completed for PDF: %s", filepath)
            return text
        elif ext in EXCEL_EXTENSIONS:
            df = pd.read_excel(filepath, engine='openpyxl' if ext == ".xlsx" else None)
            content = df.to_csv(index=False)
            logger.debug("Converted Excel to CSV: %s", filepath)
            logger.info("extract_text_from_attachment completed for Excel: %s", filepath)
            return content
        elif ext in WORD_EXTENSIONS:
            try:
                doc = Document(filepath)
                content = "\n".join([p.text for p in doc.paragraphs])
                logger.debug("Extracted text from Word document: %s", filepath)
                logger.info("extract_text_from_attachment completed for Word: %s", filepath)
                return content
            except Exception as e:
                logger.error("Failed to extract from Word: %s", e)
                return f"(Could not extract content from Word file: {e})"
        logger.warning("Unsupported file extension: %s", ext)
        logger.info("extract_text_from_attachment completed: unsupported file type %s", ext)
        return "(Unsupported file type)"
    except Exception as e:
        logger.error("Failed to extract text from %s: %s", filepath, e)
        logger.info("extract_text_from_attachment failed for %s", filepath)
        return f"(Could not extract content: {e})"

def fetch_and_summarize_ticket(ticket_key: str):
    logger.info("fetch_and_summarize_ticket called for ticket_key=%s", ticket_key)
    """Fetch and summarize a Jira ticket, including comments and attachments."""
    logger.info("Fetching and summarizing ticket: %s", ticket_key)
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)
    try:
        jira = get_jira_client()
        issue = jira.issue(ticket_key)  # Removed unused expand parameters
        logger.debug("Fetched ticket: %s", ticket_key)

        summary_parts = [
            f"Ticket: {issue.key}",
            f"Title: {issue.fields.summary}",
            f"Status: {issue.fields.status.name}",
            f"Reporter: {issue.fields.reporter.displayName}",
            f"Assignee: {issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'}",
            f"Description:\n{issue.fields.description or 'No description'}"
        ]

        # Add comments
        if issue.fields.comment.comments:
            logger.debug("Processing %d comments for ticket %s", len(issue.fields.comment.comments), ticket_key)
            summary_parts.append("\nComments:")
            for comment in issue.fields.comment.comments:
                summary_parts.append(f"- {comment.author.displayName}: {comment.body}")

        # Process attachments
        llm = LLMConfig.get_llm()
        if issue.fields.attachment:
            logger.info("Processing %d attachments for ticket %s", len(issue.fields.attachment), ticket_key)
            summary_parts.append("\nAttachments:")
            for attachment in issue.fields.attachment:
                filename = attachment.filename
                filepath = os.path.join(ATTACHMENT_DIR, filename)
                logger.debug("Downloading attachment: %s", filename)
                response = requests.get(attachment.content, auth=(settings.JIRA_USERNAME, settings.JIRA_PAT))
                with open(filepath, "wb") as f:
                    f.write(response.content)
                logger.debug("Downloaded attachment: %s", filename)

                ext = os.path.splitext(filename)[1].lower()
                attachment_info = f"- {filename} ({attachment.size} bytes) | URL: {attachment.content}"
                text_content = extract_text_from_attachment(filepath, ext)
                if text_content:
                    logger.debug("Summarizing attachment content: %s", filename)
                    attachment_summary = summarize_large_text(text_content, llm)
                    attachment_info += f"\n  Content summary:\n{attachment_summary}\n"
                summary_parts.append(attachment_info)

                # Delete the attachment file after processing
                try:
                    os.remove(filepath)
                    logger.debug("Deleted attachment file: %s", filepath)
                except Exception as e:
                    logger.warning("Failed to delete attachment file %s: %s", filepath, e)

        # Summarize with LLM
        logger.debug("Invoking LLM for final ticket summary")
        raw_text = "\n".join(summary_parts)
        response = llm.invoke([
            HumanMessage(content=f"Summarize this Jira ticket including all details, comments, attachments, and history:\n\n{raw_text}")
        ])
        logger.info("Ticket %s summarized successfully", ticket_key)
        logger.info("fetch_and_summarize_ticket completed for ticket_key=%s", ticket_key)
        return response.content
    except JIRAError as e:
        logger.error("JIRA error for ticket %s: %s", ticket_key, e)
        if e.status_code == 404:
            return f"Ticket '{ticket_key}' does not exist or is not accessible."
        raise
    except Exception as e:
        logger.error("Unexpected error summarizing ticket %s: %s", ticket_key, e)
        raise

def fetch_statuses():
    logger.info("fetch_statuses called")
    """Return all possible Jira statuses (lowercased)."""
    logger.info("Fetching available Jira statuses")
    try:
        jira = get_jira_client()
        statuses = [s.name.lower() for s in jira.statuses()]
        logger.info("Retrieved %d Jira statuses", len(statuses))
        logger.info("fetch_statuses completed with %d statuses", len(statuses))
        return statuses
    except Exception as e:
        logger.error("Error fetching Jira statuses: %s", e)
        raise
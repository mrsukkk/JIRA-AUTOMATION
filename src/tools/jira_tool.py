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
    Fetch tickets assigned to or reported by the current user.
    Optionally filter by status (e.g., 'Closed', 'In Progress').
    Returns a clean multiline string for UI display.
    """
    try:
        jira = get_jira_client()
        current_user = jira.current_user()
        profile = jira.user(current_user)
        display_name = profile.displayName
        logger.info("User display name: %s", display_name)

        # Build JQL
        status_clause = f" AND status = '{status}'" if status else ""

        assigned_jql = f"assignee = currentUser(){status_clause} ORDER BY updated DESC"
        reported_jql = f"reporter = currentUser(){status_clause} ORDER BY updated DESC"

        # Fetch tickets
        assigned_issues = jira.search_issues(assigned_jql, maxResults=None)
        reported_issues = jira.search_issues(reported_jql, maxResults=None)

        def format_issue_list(issues):
            """Format issue list cleanly with bullets."""
            lines = []
            for i, issue in enumerate(issues, start=1):
                key = issue.key
                summary = issue.fields.summary
                status_name = issue.fields.status.name
                lines.append(f"  {i}. [{key}] {summary} (Status: {status_name})")
            return lines

        output = ""

        # Assigned to you
        if assigned_issues:
            output += "🔹 Assigned to You:\n"
            output += "\n".join(format_issue_list(assigned_issues)) + "\n\n"

        # Reported by you
        if reported_issues:
            output += "🔹 Reported by You:\n"
            output += "\n".join(format_issue_list(reported_issues)) + "\n\n"

        # Nothing found
        if not output.strip():
            output = f"No tickets found for status '{status}'." if status else "No tickets found."

        logger.info("fetch_tickets_by_status completed successfully")
        return output.strip()

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
# JIRA Agent with Human Approval

A JIRA management agent powered by LangGraph and Google Gemini AI with **strict human approval** for all write operations. Every task requires a human message and explicit approval before execution.

## 🚀 Key Features

### Human Approval System
- 🔒 **Strict Approval Required**: All write operations require explicit human approval
- 👤 **Human Message Required**: Every task needs a human message to proceed
- 👀 **Preview Before Execution**: See exactly what will change before approving
- ✅ **Approve/Reject**: Explicit approval or rejection for each operation
- 📋 **Approval Tracking**: All approvals logged and tracked

### Read Operations (No Approval)
- 🔍 **Fetch Tickets**: Retrieve tickets assigned to you or reported by you
- 🎯 **Filter by Status**: Filter tickets by status (e.g., "Closed", "In Progress")
- 📝 **Summarize Tickets**: Get AI-powered summaries including:
  - Ticket details (title, status, assignee, reporter)
  - Comments
  - Attachments (PDF, Excel, Word, text files)

### Write Operations (Approval Required)
- ⚠️ **Create Tickets**: Create new tickets (approval required)
- ⚠️ **Update Tickets**: Update ticket fields (approval required)
- ⚠️ **Transition Tickets**: Move tickets through workflows (approval required)
- ⚠️ **Assign Tickets**: Assign tickets to users (approval required)
- ⚠️ **Add Comments**: Add comments to tickets (approval required)

### Interactive CLI
- 💬 **Natural Language Interface**: Chat with the agent using natural language
- 🔄 **Stateful Conversations**: Maintains context across interactions
- 📊 **Clear Feedback**: Shows approval requests with detailed previews

## Prerequisites

- Python 3.13 or higher
- JIRA account with API access
- Google Gemini API key

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd jira-langgraph-agent
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   Or if using `uv`:
   ```bash
   uv pip install -r requirements.txt
   ```

## Configuration

1. **Create a `.env` file** in the project root directory:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   JIRA_BASE_URL=https://your-jira-instance.atlassian.net
   JIRA_USERNAME=your_jira_username
   JIRA_PAT=your_jira_personal_access_token
   ```

2. **Get your Google Gemini API key:**
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Add it to your `.env` file

3. **Get your JIRA Personal Access Token:**
   - Log into your JIRA instance
   - Go to Account Settings → Security → API tokens
   - Create a new API token
   - Add it to your `.env` file

## Quick Start

### Step 1: Install Dependencies

```bash
# Navigate to project directory
cd jira-langgraph-agent

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_api_key_here
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_USERNAME=your_jira_username
JIRA_PAT=your_jira_personal_access_token
SECRET_KEY=your_secret_key_for_jwt  # Optional, auto-generated if not provided
```

### Step 3: Run Tests (Optional but Recommended)

```bash
python test_scenarios.py
```

This will verify:
- ✅ Environment variables are set
- ✅ All modules can be imported
- ✅ JIRA connection works
- ✅ LLM initialization works
- ✅ Approval system works
- ✅ Read operations work
- ✅ Web server can start

### Step 4: Start the Application

**Option A: Web Chatbot Interface (Recommended)**

```bash
python run_web.py
```

Then open your browser to `http://localhost:8000`

**Option B: Command Line Interface**

```bash
python src/main.py
```

### Step 5: Start Interacting

**Web Interface:**
1. Register a new account or login
2. Type messages in the chat
3. For write operations, click "Approve" or "Reject"

**CLI Interface:**
1. Type commands directly
2. For write operations, type `approve <request_id>` or `reject <request_id>`

See [START_GUIDE.md](START_GUIDE.md) for detailed test cases and examples!

## Usage Examples

### Interactive CLI

**Read Operations (No Approval):**
```
You: show me my tickets
AI: [Shows your tickets immediately]

You: show me closed
AI: [Shows closed tickets immediately]

You: summarize ticket PROJ-123
AI: [Shows ticket summary immediately]
```

**Write Operations (Approval Required):**
```
You: create ticket in PROJ: Fix authentication bug

AI: ============================================================
    ⚠️  APPROVAL REQUIRED - CREATE_TICKET
    ============================================================
    Request ID: abc-123-def-456
    
    📋 PREVIEW OF CHANGES:
      • project: PROJ
      • summary: Fix authentication bug
      • issue_type: Task
      ...
    
    Type 'approve abc-123-def-456' to proceed or 'reject abc-123-def-456' to cancel
    ============================================================

You: approve abc-123-def-456

AI: ✅ Approval granted. Executing operation...
    ✅ Ticket created successfully: PROJ-123
```

See [APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md) for detailed workflow documentation.

## Project Structure

```
jira-langgraph-agent/
├── src/
│   ├── main.py                          # Interactive CLI entry point
│   ├── approval/
│   │   └── approval_manager.py          # Approval request management
│   ├── config/
│   │   └── settings.py                  # Configuration management
│   ├── models/
│   │   └── llm_config.py                # LLM singleton configuration
│   ├── graphs/
│   │   └── jira_agent_graph.py          # LangGraph workflow (with approval)
│   └── tools/
│       ├── jira_tool.py                 # Read operations (fetch, summarize)
│       ├── jira_operations.py           # Base JIRA operations
│       └── jira_operations_approved.py  # Write operations (approval required)
├── pyproject.toml                       # Project metadata & dependencies
├── requirements.txt                     # Python dependencies
├── README.md                            # This file
├── APPROVAL_WORKFLOW.md                 # Approval workflow documentation
└── CLEANUP_SUMMARY.md                   # Cleanup summary
```

## How It Works

### Architecture

The system uses a **human-in-the-loop approval workflow**:

1. **Approval Manager** (`src/approval/approval_manager.py`)
   - Manages approval requests
   - Tracks pending and historical approvals
   - Formats approval messages with previews

2. **LangGraph Workflow** (`src/graphs/jira_agent_graph.py`)
   - Processes user messages
   - Creates approval requests for write operations
   - Executes approved operations
   - Handles read operations immediately

3. **JIRA Operations**
   - `jira_tool.py`: Read operations (no approval)
   - `jira_operations.py`: Base operations
   - `jira_operations_approved.py`: Write operations (approval required)

### Workflow

1. **User sends message** → Human message required
2. **Agent processes** → Determines operation type
3. **Read operation?** → Execute immediately
4. **Write operation?** → Create approval request with preview
5. **User reviews** → Sees exactly what will change
6. **User approves/rejects** → Explicit confirmation
7. **If approved** → Execute operation
8. **If rejected** → Cancel operation

### LangGraph Nodes

- **agent_node**: Processes user input, handles approve/reject commands
- **tools_node**: Fetches tickets (read-only, no approval)
- **summarizer_node**: Summarizes tickets (read-only, no approval)
- **approval_node**: Creates and displays approval requests
- **execute_node**: Executes approved operations

## Supported File Types

The agent can process attachments in the following formats:
- **Text files**: `.txt`, `.csv`, `.json`, `.md`, `.log`
- **PDF**: `.pdf`
- **Excel**: `.xls`, `.xlsx`
- **Word**: `.docx`

## Approval Workflow

All write operations follow this strict workflow:

1. **Human message required** - No operations without explicit user input
2. **Preview shown** - User sees exactly what will change
3. **Approval required** - User must explicitly approve or reject
4. **Execution** - Operation only executes if approved

See [APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md) for detailed documentation.

## Documentation

- [APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md) - Detailed approval workflow documentation
- [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md) - Codebase cleanup summary

## Deployment

The agent runs as a simple Python application:

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# Create .env file with your credentials

# Run the agent
python src/main.py
```

No additional services or infrastructure required.

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Required
GOOGLE_API_KEY=your_google_api_key
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_USERNAME=your_username
JIRA_PAT=your_personal_access_token
```

## Logging

Logs are output to the console with the following levels:
- **INFO**: Normal operations
- **WARNING**: Non-critical issues
- **ERROR**: Errors requiring attention

All operations are logged, including approval requests and executions.

## Security

- **API Keys**: Store in `.env` file, never commit to git (already in `.gitignore`)
- **Approval Required**: All write operations require explicit approval
- **Preview Before Execution**: Users see exactly what will change
- **No Autonomous Operations**: No operations execute without human approval

## Troubleshooting

### Common Issues

**Agent not starting:**
- Check environment variables in `.env` file
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (requires 3.13+)

**Approval not working:**
- Ensure you're using the correct approval request ID
- Check that the approval request hasn't expired
- Review console logs for error messages

**JIRA connection issues:**
- Verify JIRA credentials in `.env` file
- Check JIRA URL format (include `https://`)
- Ensure API token has necessary permissions

### Getting Help

- Check console logs for error messages
- Review [APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md) for workflow details
- JIRA API docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/

## Key Principles

1. **Human Message Required**: Every operation requires explicit human input
2. **Approval Required**: All write operations must be approved
3. **Preview Before Execution**: Users see exactly what will change
4. **No Silent Operations**: Nothing happens without user knowledge
5. **Complete Control**: Users have full control over all JIRA modifications

## License

This project is provided as-is for educational and development purposes.

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) - Workflow orchestration
- [LangChain](https://github.com/langchain-ai/langchain) - LLM integration
- [FastAPI](https://fastapi.tiangolo.com/) - REST API framework
- [JIRA Python](https://jira.readthedocs.io/) - JIRA API client


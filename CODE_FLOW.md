# JIRA Automation - Code Flow Navigation Guide

This document provides a navigable code flow explanation. Use Ctrl+Click (or Cmd+Click on Mac) on file paths to jump to the code.

---

## 🚀 **ENTRY POINT: Application Startup**

### Step 1: Run the Application
**File:** [`src/main.py`](src/main.py) - **Line 78-80**

When you run `python src/main.py`, execution starts here:

```python
if __name__ == "__main__":
    LLMConfig.get_llm()  # Line 79 - Initialize LLM
    run_agent()          # Line 80 - Start the agent
```

**What happens:**
1. **LLM Initialization** → [`src/models/llm_config.py`](src/models/llm_config.py) - **Line 9-19**
   - Calls `LLMConfig.get_llm()` which creates a singleton LLM instance
   - Uses settings from [`src/config/settings.py`](src/config/settings.py) - **Line 6-18**
   - Settings loads environment variables via `load_dotenv()` - **Line 4**
   - Returns `ChatGoogleGenerativeAI` instance with Gemini model

2. **Agent Execution** → [`src/main.py`](src/main.py) - **Line 6-77**
   - `run_agent()` function starts the main loop

---

## 🔄 **MAIN LOOP: User Interaction**

### Step 2: Main Loop Initialization
**File:** [`src/main.py`](src/main.py) - **Line 22-29**

```python
current_state = {
    "messages": [],
    "greeted": False,
    "status_filter": None,
    "ticket_to_summarize": None,
    "pending_approval_id": None,
    "operation_type": None
}
```

**State Structure:**
- `messages`: Conversation history (HumanMessage/AIMessage)
- `greeted`: Whether user has been greeted
- `status_filter`: Filter for ticket status queries
- `ticket_to_summarize`: Ticket key to summarize
- `pending_approval_id`: ID of pending approval request
- `operation_type`: Type of operation (create, update, transition, etc.)

### Step 3: User Input Collection
**File:** [`src/main.py`](src/main.py) - **Line 31-47**

```python
while True:
    user_input = input("\nYou: ").strip()  # Line 33
    # ... validation ...
    input_state = {
        **current_state,
        "messages": [HumanMessage(content=user_input)]  # Line 46
    }
```

**What happens:**
- Waits for user input
- Creates `HumanMessage` with user input
- Prepares state for workflow

### Step 4: Invoke LangGraph Workflow
**File:** [`src/main.py`](src/main.py) - **Line 49-51**

```python
result = app.invoke(input_state)  # Line 51
```

**The `app` object:**
- Defined in [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 395**
- `app = workflow.compile()` - Compiled LangGraph workflow

---

## 🕸️ **WORKFLOW GRAPH: LangGraph State Machine**

### Step 5: Graph Entry Point
**File:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 358**

```python
workflow.set_entry_point("agent")  # Always starts at "agent" node
```

**Graph Structure:**
- **Entry:** `agent` node
- **Nodes:** `agent`, `tools`, `summarizer`, `approval`, `execute`
- **Routing:** Conditional edges based on state

### Step 6: Agent Node - Process User Input
**File:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 50-209**

**Function:** `agent_node(state: AgentState)`

**What it does:**
1. **Validates Human Message** - **Line 57-67**
   - Ensures there's a human message to proceed
   - Returns error if no human input

2. **Handles Approval Commands** - **Line 72-124**
   - If user says "approve <request_id>":
     - Calls [`approval_manager.approve()`](src/approval/approval_manager.py) - **Line 116-140**
     - Sets `pending_approval_id` and `operation_type` in state
   - If user says "reject <request_id>":
     - Calls [`approval_manager.reject()`](src/approval/approval_manager.py) - **Line 142-168**

3. **Detects Operation Commands** - **Line 126-193**
   - **"show me my tickets"** → Sets `greeted: True` - **Line 134-143**
   - **Status filter** (e.g., "In Progress") → Sets `status_filter` - **Line 145-154**
   - **"summarize ticket"** → Sets `ticket_to_summarize` - **Line 156-168**
   - **"create ticket"** → Sets `operation_type: "create"` - **Line 171-180**
   - **"update ticket"** → Sets `operation_type: "update"` - **Line 182-193**

4. **LLM Fallback** - **Line 196-206**
   - If no specific command detected, invokes LLM
   - Uses [`LLMConfig.get_llm()`](src/models/llm_config.py) - **Line 9-19**

### Step 7: Conditional Routing After Agent
**File:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 361-374**

**Function:** `route_after_agent(state: AgentState)`

**Routing Logic:**
```python
if state.get("pending_approval_id") and state.get("operation_type"):
    if approval_manager.is_approved(state.get("pending_approval_id")):
        return "execute"  # Go to execute node
    else:
        return "approval"  # Go to approval node
elif state.get("greeted", False):
    return "tools"  # Go to tools node
elif state.get("ticket_to_summarize"):
    return "summarizer"  # Go to summarizer node
else:
    return END  # End workflow
```

**Routes:**
- **"approval"** → Approval node (if pending approval exists)
- **"execute"** → Execute node (if approval granted)
- **"tools"** → Tools node (if `greeted: True`)
- **"summarizer"** → Summarizer node (if ticket to summarize)
- **END** → End workflow

---

## 📊 **TOOLS NODE: Fetch Tickets**

### Step 8: Tools Node Execution
**File:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 212-232**

**Function:** `tool_node(state: AgentState)`

**What it does:**
- Checks if `greeted: True` - **Line 216**
- Calls [`fetch_tickets_by_status()`](src/tools/jira_tool.py) - **Line 218**
- Returns formatted ticket list

**Implementation Details:**
**File:** [`src/tools/jira_tool.py`](src/tools/jira_tool.py) - **Line 43-124**

1. **Get JIRA Client** - **Line 51**
   - Calls [`get_jira_client()`](src/tools/jira_tool.py) - **Line 29-41**
   - Uses settings from [`src/config/settings.py`](src/config/settings.py) - **Line 14-16**
   - Creates `JIRA` instance with credentials

2. **Get Current User** - **Line 52-57**
   - Gets current JIRA user and account ID

3. **Build JQL Queries** - **Line 59-62**
   - Assigned tickets: `assignee = currentUser()`
   - Reported tickets: `reporter = currentUser()`
   - Optional status filter

4. **Fetch Tickets** - **Line 67-72**
   - Executes JQL queries via `jira.search_issues()`
   - Returns list of issue objects

5. **Format Output** - **Line 97-121**
   - Groups tickets by role (Assigned/Reported)
   - Formats as human-readable string
   - Returns formatted result

**Flow back to main:**
- Tools node → END → Returns to [`src/main.py`](src/main.py) - **Line 54-61**

---

## 📝 **SUMMARIZER NODE: Summarize Ticket**

### Step 9: Summarizer Node Execution
**File:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 235-256**

**Function:** `summarize_ticket_node(state: AgentState)`

**What it does:**
- Checks if `ticket_to_summarize` is set - **Line 240**
- Calls [`fetch_and_summarize_ticket()`](src/tools/jira_tool.py) - **Line 242**

**Implementation Details:**
**File:** [`src/tools/jira_tool.py`](src/tools/jira_tool.py) - **Line 181-251**

1. **Get JIRA Client** - **Line 186**
   - Uses [`get_jira_client()`](src/tools/jira_tool.py) - **Line 29-41**

2. **Fetch Ticket** - **Line 187**
   - Gets issue details via `jira.issue(ticket_key)`

3. **Build Summary Parts** - **Line 190-197**
   - Ticket key, title, status, reporter, assignee, description

4. **Process Comments** - **Line 200-204**
   - Iterates through ticket comments
   - Adds to summary parts

5. **Process Attachments** - **Line 208-234**
   - Downloads attachments to `jira_attachments/` directory
   - Extracts text using [`extract_text_from_attachment()`](src/tools/jira_tool.py) - **Line 145-179**
   - Supports: `.txt`, `.pdf`, `.xlsx`, `.docx`
   - Summarizes large text using [`summarize_large_text()`](src/tools/jira_tool.py) - **Line 126-143**
   - Uses LLM to summarize each chunk
   - Deletes attachment files after processing

6. **Final LLM Summary** - **Line 236-243**
   - Invokes LLM with all ticket data
   - Returns comprehensive summary

**Flow back to main:**
- Summarizer node → END → Returns to [`src/main.py`](src/main.py) - **Line 54-61**

---

## ✅ **APPROVAL NODE: Request Approval**

### Step 10: Approval Node Execution
**File:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 259-291**

**Function:** `approval_node(state: AgentState)`

**What it does:**
- Checks `operation_type` - **Line 263**
- Creates approval request based on operation type

**For "create" operation:**
- Calls [`create_ticket_with_approval()`](src/tools/jira_operations_approved.py) - **Line 271**
- **File:** [`src/tools/jira_operations_approved.py`](src/tools/jira_operations_approved.py) - **Line 21-55**

**Approval Request Creation:**
1. **Build Preview** - **Line 35-43**
   - Creates preview dict with ticket details
   - Project, summary, description, issue_type, assignee, priority, labels

2. **Create Approval Request** - **Line 47-52**
   - Calls [`approval_manager.create_approval_request()`](src/approval/approval_manager.py) - **Line 49-83**
   - **File:** [`src/approval/approval_manager.py`](src/approval/approval_manager.py)

**Approval Manager Details:**
- **Line 68-69:** Generates unique request ID (UUID)
- **Line 71-78:** Creates `ApprovalRequest` dataclass
- **Line 80:** Stores in `pending_approvals` dict
- **Line 81:** Logs approval request

3. **Format Approval Message** - **Line 278**
   - Calls [`approval_manager.format_approval_message()`](src/approval/approval_manager.py) - **Line 85-114**
   - Creates human-readable approval message
   - Shows preview of changes
   - Returns formatted string

4. **Return State** - **Line 279-286**
   - Sets `pending_approval_id` in state
   - Sets `operation_type`
   - Returns approval message

**Flow:**
- Approval node → END → Returns to [`src/main.py`](src/main.py) - **Line 54-61**
- User sees approval message
- User types "approve <request_id>" or "reject <request_id>"
- Loop continues, goes back to agent node

---

## ⚙️ **EXECUTE NODE: Execute Approved Operation**

### Step 11: Execute Node Execution
**File:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - **Line 294-347**

**Function:** `execute_node(state: AgentState)`

**What it does:**
- Checks if approval exists and is approved - **Line 298-309**
- Executes operation based on `operation_type`

**For "create_ticket" operation:**
- Calls [`execute_create_ticket()`](src/tools/jira_operations_approved.py) - **Line 313**
- **File:** [`src/tools/jira_operations_approved.py`](src/tools/jira_operations_approved.py) - **Line 58-93**

**Execution Flow:**
1. **Validate Approval** - **Line 65-77**
   - Checks if approval is approved via [`approval_manager.is_approved()`](src/approval/approval_manager.py) - **Line 174-183**
   - Retrieves approval from pending or history

2. **Get Preview Data** - **Line 79**
   - Extracts preview dict from approval request

3. **Execute Operation** - **Line 81-90**
   - Calls [`_create_ticket()`](src/tools/jira_operations.py) - **Line 18-69**
   - **File:** [`src/tools/jira_operations.py`](src/tools/jira_operations.py)

**JIRA Operation Details:**
- **Line 46:** Gets JIRA client via [`get_jira_client()`](src/tools/jira_tool.py) - **Line 29-41**
- **Line 48-62:** Builds issue dict with fields
- **Line 64:** Creates issue via `jira.create_issue()`
- **Line 65:** Returns ticket key (e.g., "PROJ-123")

4. **Return Success** - **Line 314-321**
   - Returns success message with ticket key
   - Clears `pending_approval_id` and `operation_type`

**For other operations:**
- **"update_ticket"** → [`execute_update_ticket()`](src/tools/jira_operations_approved.py) - **Line 155-185**
- **"transition_ticket"** → [`execute_transition_ticket()`](src/tools/jira_operations_approved.py) - **Line 222-246**
- **"assign_ticket"** → [`execute_assign_ticket()`](src/tools/jira_operations_approved.py) - **Line 278-301**
- **"add_comment"** → [`execute_add_comment()`](src/tools/jira_operations_approved.py) - **Line 325-349**

**Flow back to main:**
- Execute node → END → Returns to [`src/main.py`](src/main.py) - **Line 54-61**

---

## 🔄 **RETURN TO MAIN: State Update & Display**

### Step 12: Update State and Display Results
**File:** [`src/main.py`](src/main.py) - **Line 53-76**

**What happens:**
1. **Update State** - **Line 54-61**
   - Extracts new state from workflow result
   - Updates `current_state` with new values

2. **Print AI Responses** - **Line 64-66**
   - Iterates through messages
   - Prints all `AIMessage` content

3. **Show Pending Approvals** - **Line 69-71**
   - Calls [`approval_manager.get_pending_approvals()`](src/approval/approval_manager.py) - **Line 185-187**
   - Shows count of pending approvals

4. **Error Handling** - **Line 73-76**
   - Catches exceptions
   - Prints error message and traceback

5. **Loop Continues** - **Line 31**
   - Returns to input prompt
   - Waits for next user command

---

## 📁 **KEY FILES REFERENCE**

### Configuration
- **Settings:** [`src/config/settings.py`](src/config/settings.py)
  - Loads environment variables
  - JIRA credentials, LLM settings

### Models
- **LLM Config:** [`src/models/llm_config.py`](src/models/llm_config.py)
  - Singleton LLM instance
  - Gemini model initialization

### Workflow
- **Graph:** [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py)
  - LangGraph state machine
  - Node definitions and routing

### Tools
- **JIRA Tool:** [`src/tools/jira_tool.py`](src/tools/jira_tool.py)
  - Read operations (fetch, summarize)
  - JIRA client initialization

- **JIRA Operations:** [`src/tools/jira_operations.py`](src/tools/jira_operations.py)
  - Write operations (create, update, transition)
  - Direct JIRA API calls

- **Approved Operations:** [`src/tools/jira_operations_approved.py`](src/tools/jira_operations_approved.py)
  - Write operations with approval workflow
  - Approval request creation and execution

### Approval
- **Approval Manager:** [`src/approval/approval_manager.py`](src/approval/approval_manager.py)
  - Approval request management
  - Approval/rejection logic
  - Approval history tracking

---

## 🔍 **COMMON FLOW PATTERNS**

### Pattern 1: Read Operation (No Approval)
```
User Input → agent_node → tools_node → END → Display Results
```

### Pattern 2: Write Operation (With Approval)
```
User Input → agent_node → approval_node → END → Display Approval
User: "approve <id>" → agent_node → execute_node → END → Display Success
```

### Pattern 3: Summarize Ticket
```
User Input → agent_node → summarizer_node → END → Display Summary
```

### Pattern 4: LLM Conversation
```
User Input → agent_node → LLM → END → Display Response
```

---

## 🎯 **QUICK NAVIGATION CHECKLIST**

To understand the full flow, navigate through these files in order:

1. ✅ [`src/main.py`](src/main.py) - Entry point
2. ✅ [`src/models/llm_config.py`](src/models/llm_config.py) - LLM initialization
3. ✅ [`src/config/settings.py`](src/config/settings.py) - Configuration
4. ✅ [`src/graphs/jira_agent_graph.py`](src/graphs/jira_agent_graph.py) - Workflow graph
5. ✅ [`src/tools/jira_tool.py`](src/tools/jira_tool.py) - Read operations
6. ✅ [`src/tools/jira_operations.py`](src/tools/jira_operations.py) - Write operations
7. ✅ [`src/tools/jira_operations_approved.py`](src/tools/jira_operations_approved.py) - Approved operations
8. ✅ [`src/approval/approval_manager.py`](src/approval/approval_manager.py) - Approval system

---

**End of Code Flow Guide**


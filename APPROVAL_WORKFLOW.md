# Human Approval Workflow

This document describes the **strict human-in-the-loop approval system** implemented in the JIRA agent.

## 🔒 Core Principles

1. **Every task requires a human message** - No operations proceed without explicit human input
2. **All write operations require approval** - Create, update, transition, assign, and comment operations must be approved
3. **Preview before execution** - Users see exactly what will change before approving
4. **Explicit approval/rejection** - Users must explicitly approve or reject each operation

## 📋 How It Works

### Read Operations (No Approval Needed)
- ✅ Fetch tickets
- ✅ Search tickets
- ✅ Summarize tickets
- ✅ View ticket details

These operations execute immediately as they don't modify JIRA data.

### Write Operations (Approval Required)
- ⚠️ Create ticket
- ⚠️ Update ticket
- ⚠️ Transition ticket
- ⚠️ Assign ticket
- ⚠️ Add comment
- ⚠️ Bulk operations

These operations follow this workflow:

1. **User requests operation** → Human message required
2. **System creates approval request** → Shows preview of changes
3. **User reviews preview** → Sees exactly what will change
4. **User approves or rejects** → Explicit confirmation required
5. **System executes (if approved)** → Only after approval

## 🎯 Usage Examples

### Example 1: Creating a Ticket

```
You: create ticket in PROJ: Fix authentication bug

AI: ============================================================
    ⚠️  APPROVAL REQUIRED - CREATE_TICKET
    ============================================================
    Request ID: abc-123-def-456
    
    Description: Create new Task ticket in project PROJ
    
    📋 PREVIEW OF CHANGES:
      • project: PROJ
      • summary: Fix authentication bug
      • description: (user provided)
      • issue_type: Task
      • assignee: Unassigned
      • priority: Medium
      • labels: []
    
    ============================================================
    Type 'approve abc-123-def-456' to proceed or 'reject abc-123-def-456' to cancel
    ============================================================

You: approve abc-123-def-456

AI: ✅ Approval granted for create_ticket. Executing operation...
    ✅ Ticket created successfully: PROJ-123
```

### Example 2: Updating a Ticket

```
You: update ticket PROJ-123: change status to In Progress and assign to john.doe

AI: ============================================================
    ⚠️  APPROVAL REQUIRED - UPDATE_TICKET
    ============================================================
    Request ID: xyz-789-abc-012
    
    Description: Update ticket PROJ-123
    Changes:
      - Status: 'Open' → 'In Progress'
      - Assignee: 'Unassigned' → 'john.doe'
    
    📋 PREVIEW OF CHANGES:
      • ticket_key: PROJ-123
      • current_status: Open
      • new_status: In Progress
      • current_assignee: Unassigned
      • new_assignee: john.doe
      ...
    
    ============================================================
    Type 'approve xyz-789-abc-012' to proceed or 'reject xyz-789-abc-012' to cancel
    ============================================================

You: approve xyz-789-abc-012

AI: ✅ Approval granted for update_ticket. Executing operation...
    ✅ Ticket updated successfully.
```

### Example 3: Rejecting an Operation

```
You: update ticket PROJ-123: change priority to Highest

AI: [Shows approval request with preview]

You: reject xyz-789-abc-012 Wrong ticket

AI: ❌ Operation rejected. Approval request xyz-789-abc-012 has been cancelled.
```

## 🔧 Implementation Details

### Approval Manager

The `ApprovalManager` class (`src/approval/approval_manager.py`) handles:
- Creating approval requests
- Storing pending approvals
- Processing approvals/rejections
- Formatting approval messages

### Approved Operations

All write operations have two functions:
1. `*_with_approval()` - Creates approval request (does NOT execute)
2. `execute_*()` - Executes operation after approval

Example:
- `create_ticket_with_approval()` → Returns approval request
- `execute_create_ticket(approval_id)` → Creates ticket after approval

### LangGraph Workflow

The workflow (`src/graphs/jira_agent_graph_with_approval.py`) includes:
- **agent_node**: Processes human messages, detects operations
- **approval_node**: Creates and displays approval requests
- **execute_node**: Executes approved operations
- **tools_node**: Read-only operations (no approval)
- **summarizer_node**: Read-only operations (no approval)

### State Management

The workflow state tracks:
- `pending_approval_id`: Current approval request ID
- `operation_type`: Type of operation pending approval
- `messages`: Conversation history
- Other state for read operations

## 🚫 Automation Engine

The automation engine (`src/automation/automation_engine.py`) is **disabled by default** when approval workflow is active.

To enable automation with approvals:
1. Automation rules create approval requests
2. Human reviews and approves/rejects
3. Approved operations execute

This ensures **zero autonomous writes** - all changes require human approval.

## 📝 API Integration

The REST API (`src/api/server.py`) can be updated to:
- Require approval for all write endpoints
- Return approval request IDs
- Provide approval/rejection endpoints

Example API flow:
```bash
# 1. Create approval request
POST /api/v1/tickets/approval
→ Returns approval_request_id

# 2. Review preview
GET /api/v1/approvals/{id}

# 3. Approve or reject
POST /api/v1/approvals/{id}/approve
POST /api/v1/approvals/{id}/reject
```

## ✅ Safety Features

1. **No silent operations** - Every write requires explicit approval
2. **Preview before execution** - Users see exactly what will change
3. **Human message required** - No operations without human input
4. **Approval tracking** - All approvals logged in history
5. **Rejection support** - Users can reject with reason

## 🔄 Workflow Diagram

```
Human Message
    ↓
Agent Node (detects operation)
    ↓
Write Operation? → Yes → Approval Node (creates request)
    ↓                        ↓
   No                    Shows Preview
    ↓                        ↓
Execute Read          Wait for Approval
    ↓                        ↓
   END              Human: approve/reject
                           ↓
                    Execute Node (if approved)
                           ↓
                          END
```

## 🎓 Best Practices

1. **Always review previews** - Check what will change before approving
2. **Use descriptive rejections** - Provide reason when rejecting
3. **Batch operations** - Approve multiple related changes together
4. **Verify ticket keys** - Ensure correct tickets before approving
5. **Monitor approval history** - Review what was approved/rejected

## 🛡️ Security

- Approval requests are stored in memory (can be persisted to database)
- Approval IDs are UUIDs (hard to guess)
- Each approval is tied to specific operation
- Rejected operations are logged
- Approval history maintained for audit

This system ensures **complete human control** over all JIRA modifications while maintaining efficiency for read operations.


# Quick Start Guide

## 🚀 Starting the Application

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

**How to get credentials:**
- **Google API Key**: Visit https://makersuite.google.com/app/apikey
- **JIRA PAT**: JIRA → Account Settings → Security → API tokens

### Step 3: Start the Web Interface (Recommended)

```bash
python run_web.py
```

You should see:
```
============================================================
Starting JIRA Agent Chatbot Web Interface
============================================================

🌐 Server starting at: http://localhost:8000
📝 Open your browser and navigate to the URL above
🔐 Register a new user or login to start chatting
============================================================
```

### Step 4: Open in Browser

1. Open your web browser
2. Navigate to: `http://localhost:8000`
3. Register a new account (or login if you have one)
4. Start chatting!

---

## 💬 Alternative: Command Line Interface

If you prefer the CLI:

```bash
python src/main.py
```

Then type commands directly in the terminal.

---

## 📋 Test Cases

### Test Case 1: User Registration and Login

**Steps:**
1. Open `http://localhost:8000`
2. Click "Register"
3. Enter:
   - Username: `testuser`
   - Password: `testpass123`
   - Email: `test@example.com` (optional)
4. Click "Register"
5. Click "Back to Login"
6. Enter credentials and click "Login"

**Expected Result:**
- ✅ Registration successful message
- ✅ Redirected to chat interface
- ✅ Username displayed in header
- ✅ Welcome message from agent

---

### Test Case 2: Read Operation - Fetch Tickets

**Steps:**
1. After login, type in chat: `show me my tickets`
2. Press Enter or click "Send"

**Expected Result:**
- ✅ Agent responds: "Hi! Fetching your tickets..."
- ✅ List of tickets displayed (if any)
- ✅ Tickets grouped by "Assigned to You" and "Reported by You"
- ✅ Each ticket shows: `[TICKET-KEY] Summary (Status: STATUS)`
- ✅ No approval required (read operation)

**Sample Output:**
```
🔹 Assigned to You:
  1. [PROJ-123] Fix authentication bug (Status: In Progress)
  2. [PROJ-124] Update documentation (Status: Open)

🔹 Reported by You:
  1. [PROJ-125] Feature request: Add dark mode (Status: Open)
```

---

### Test Case 3: Read Operation - Filter by Status

**Steps:**
1. Type: `show me closed`
2. Press Enter

**Expected Result:**
- ✅ Agent responds: "Fetching tickets with status 'closed'..."
- ✅ Only closed tickets displayed
- ✅ No approval required

**Alternative Statuses to Test:**
- `show me in progress`
- `show me open`
- `show me resolved`

---

### Test Case 4: Read Operation - Summarize Ticket

**Steps:**
1. Type: `summarize ticket PROJ-123` (replace with actual ticket key)
2. Press Enter

**Expected Result:**
- ✅ Agent responds: "Summarizing ticket PROJ-123..."
- ✅ Detailed summary displayed including:
  - Ticket key, title, status
  - Reporter and assignee
  - Description
  - Comments
  - Attachments (if any)
- ✅ No approval required

**Sample Output:**
```
Ticket: PROJ-123
Title: Fix authentication bug
Status: In Progress
Reporter: John Doe
Assignee: Jane Smith
Description: Users cannot log in after password reset...

Comments:
- John Doe: Investigating the issue...
- Jane Smith: Found the root cause...

[AI-generated comprehensive summary]
```

---

### Test Case 5: Write Operation - Create Ticket (Approval Required)

**Steps:**
1. Type: `create ticket in PROJ: Test ticket for approval workflow`
2. Press Enter

**Expected Result:**
- ✅ Agent responds with approval request
- ✅ Approval box appears with:
  - Request ID
  - Operation type: CREATE_TICKET
  - Preview of changes:
    - Project: PROJ
    - Summary: Test ticket for approval workflow
    - Issue type: Task
    - Assignee: Unassigned
    - Priority: Medium
- ✅ "Approve" and "Reject" buttons visible

**To Complete:**
- Click "Approve" → Ticket created, success message shown
- OR Click "Reject" → Operation cancelled, rejection message shown

**Sample Approval Box:**
```
⚠️ APPROVAL REQUIRED - CREATE_TICKET
============================================================
Request ID: abc-123-def-456

📋 PREVIEW OF CHANGES:
  • project: PROJ
  • summary: Test ticket for approval workflow
  • issue_type: Task
  • assignee: Unassigned
  • priority: Medium
  • labels: []

[Approve] [Reject]
```

---

### Test Case 6: Write Operation - Update Ticket (Approval Required)

**Steps:**
1. Type: `update ticket PROJ-123: change status to In Progress`
2. Press Enter

**Expected Result:**
- ✅ Approval request displayed
- ✅ Preview shows:
  - Current status vs New status
  - Current assignee vs New assignee (if changed)
  - Other changes highlighted
- ✅ Approval/Reject buttons

**Sample Preview:**
```
📋 PREVIEW OF CHANGES:
  • ticket_key: PROJ-123
  • current_status: Open
  • new_status: In Progress
  • current_assignee: Unassigned
  • new_assignee: (unchanged)
```

---

### Test Case 7: Write Operation - Assign Ticket (Approval Required)

**Steps:**
1. Type: `assign ticket PROJ-123 to john.doe`
2. Press Enter

**Expected Result:**
- ✅ Approval request with preview
- ✅ Shows current assignee → new assignee
- ✅ Approval required before execution

---

### Test Case 8: Write Operation - Add Comment (Approval Required)

**Steps:**
1. Type: `add comment to PROJ-123: This is a test comment`
2. Press Enter

**Expected Result:**
- ✅ Approval request displayed
- ✅ Preview shows comment text
- ✅ Approval required

---

### Test Case 9: Approval Workflow - Approve Request

**Steps:**
1. Trigger any write operation (create, update, etc.)
2. Review the approval preview
3. Click "Approve" button

**Expected Result:**
- ✅ "Approval granted" message
- ✅ "Executing operation..." message
- ✅ Success message with result
- ✅ Operation completed in JIRA

**Sample Flow:**
```
User: create ticket in PROJ: New feature
AI: [Shows approval request]
User: [Clicks Approve]
AI: ✅ Approval granted. Executing operation...
AI: ✅ Ticket created successfully: PROJ-126
```

---

### Test Case 10: Approval Workflow - Reject Request

**Steps:**
1. Trigger any write operation
2. Review the approval preview
3. Click "Reject" button
4. (Optional) Enter rejection reason

**Expected Result:**
- ✅ "Operation rejected" message
- ✅ Request cancelled
- ✅ No changes made to JIRA
- ✅ Can continue with other operations

---

### Test Case 11: Multiple Operations in Sequence

**Steps:**
1. Fetch tickets: `show me my tickets`
2. Summarize a ticket: `summarize ticket PROJ-123`
3. Create a ticket: `create ticket in PROJ: Test`
4. Approve the creation
5. Update the new ticket: `update ticket PROJ-126: change priority to High`
6. Approve the update

**Expected Result:**
- ✅ All operations execute in sequence
- ✅ Conversation state maintained
- ✅ Each write operation requires approval
- ✅ Read operations execute immediately

---

### Test Case 12: Error Handling - Invalid Ticket Key

**Steps:**
1. Type: `summarize ticket INVALID-999`
2. Press Enter

**Expected Result:**
- ✅ Error message displayed
- ✅ Agent handles error gracefully
- ✅ Can continue with other operations

**Sample Error:**
```
AI: ❌ Error: Ticket 'INVALID-999' does not exist or is not accessible.
```

---

### Test Case 13: Error Handling - Invalid Command

**Steps:**
1. Type: `random gibberish text`
2. Press Enter

**Expected Result:**
- ✅ Agent responds with LLM-generated response
- ✅ Tries to understand the intent
- ✅ May ask for clarification

---

### Test Case 14: Session Management - Logout

**Steps:**
1. Perform some operations
2. Click "Logout" button in header

**Expected Result:**
- ✅ Session invalidated
- ✅ Redirected to login screen
- ✅ Chat history cleared
- ✅ Must login again to continue

---

### Test Case 15: Session Management - Multiple Users

**Steps:**
1. Open browser in incognito/private mode
2. Register user1, perform operations
3. Open another browser/incognito window
4. Register user2, perform operations

**Expected Result:**
- ✅ Each user has separate session
- ✅ Each user has separate conversation state
- ✅ Operations don't interfere with each other

---

## 🧪 Quick Test Checklist

Run through these quickly to verify everything works:

- [ ] Server starts without errors
- [ ] Can register new user
- [ ] Can login with registered user
- [ ] Can fetch tickets (read operation)
- [ ] Can summarize ticket (read operation)
- [ ] Can request ticket creation (shows approval)
- [ ] Can approve request (ticket created)
- [ ] Can reject request (operation cancelled)
- [ ] Can logout and login again
- [ ] Error messages display correctly

---

## 🐛 Troubleshooting

### Server Won't Start

**Error:** `ModuleNotFoundError: No module named 'fastapi'`
**Solution:** Run `pip install -r requirements.txt`

**Error:** `Address already in use`
**Solution:** Change port in `run_web.py` or kill process using port 8000

### Can't Connect to JIRA

**Error:** `Failed to initialize Jira client`
**Solution:** 
- Check `.env` file has correct credentials
- Verify JIRA URL format (include `https://`)
- Verify API token is valid

### Chat Not Responding

**Error:** No response from agent
**Solution:**
- Check browser console for errors (F12)
- Check server logs for errors
- Verify Google API key is valid
- Check network connection

### Approval Not Working

**Error:** Approval button does nothing
**Solution:**
- Check browser console for JavaScript errors
- Verify session is still valid (try refreshing)
- Check server logs

---

## 📝 Example Conversation Flow

```
User: show me my tickets
AI: Hi! Fetching your tickets...
AI: 🔹 Assigned to You:
     1. [PROJ-123] Fix bug (Status: Open)

User: summarize ticket PROJ-123
AI: Summarizing ticket PROJ-123...
AI: [Detailed summary of ticket]

User: create ticket in PROJ: New feature request
AI: ⚠️ APPROVAL REQUIRED - CREATE_TICKET
    [Preview of changes]
    [Approve] [Reject]

User: [Clicks Approve]
AI: ✅ Approval granted. Executing operation...
AI: ✅ Ticket created successfully: PROJ-124

User: update ticket PROJ-124: change status to In Progress
AI: ⚠️ APPROVAL REQUIRED - UPDATE_TICKET
    [Preview showing status change]
    [Approve] [Reject]

User: [Clicks Approve]
AI: ✅ Approval granted. Executing operation...
AI: ✅ Ticket updated successfully.
```

---

## 🎯 Next Steps

After testing:
1. Customize the interface (colors, styling)
2. Add more JIRA operations
3. Implement message history persistence
4. Add file upload support
5. Integrate with external authentication

Happy testing! 🚀


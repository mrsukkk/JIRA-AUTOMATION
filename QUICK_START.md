# 🚀 Quick Start - 5 Minutes

## 1️⃣ Install & Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with:
GOOGLE_API_KEY=your_key
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_USERNAME=your_username
JIRA_PAT=your_token
```

## 2️⃣ Test Everything Works

```bash
python test_scenarios.py
```

Should see: ✅ All tests passed!

## 3️⃣ Start the Server

```bash
python run_web.py
```

## 4️⃣ Open Browser

Go to: **http://localhost:8000**

## 5️⃣ Register & Chat

1. Click "Register"
2. Create account
3. Login
4. Start chatting!

---

## 💬 Quick Test Commands

**Read Operations (No Approval):**
- `show me my tickets`
- `show me closed`
- `summarize ticket PROJ-123`

**Write Operations (Approval Required):**
- `create ticket in PROJ: Test ticket`
- `update ticket PROJ-123: change status to In Progress`
- `assign ticket PROJ-123 to john.doe`

---

## 📚 Full Documentation

- **START_GUIDE.md** - Complete guide with all test cases
- **WEB_INTERFACE.md** - Web interface documentation
- **APPROVAL_WORKFLOW.md** - Approval system details

---

## ❓ Troubleshooting

**Server won't start?**
→ Run `pip install -r requirements.txt`

**Can't connect to JIRA?**
→ Check `.env` file has correct credentials

**Chat not working?**
→ Check browser console (F12) for errors

---

That's it! You're ready to go! 🎉


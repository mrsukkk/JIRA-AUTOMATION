# Web Chatbot Interface

A beautiful, modern web-based chatbot interface with user authentication for the JIRA agent.

## Features

- 🔐 **User Authentication**: Register and login system
- 💬 **Real-time Chat**: Interactive chat interface
- ✅ **Approval System**: Visual approval requests with previews
- 🎨 **Modern UI**: Beautiful, responsive design
- 📱 **Mobile Friendly**: Works on all devices

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables** (create `.env` file):
   ```env
   GOOGLE_API_KEY=your_google_api_key
   JIRA_BASE_URL=https://your-instance.atlassian.net
   JIRA_USERNAME=your_jira_username
   JIRA_PAT=your_jira_personal_access_token
   SECRET_KEY=your_secret_key_for_jwt  # Optional, auto-generated if not provided
   ```

3. **Start the web server:**
   ```bash
   python run_web.py
   ```

4. **Open your browser:**
   Navigate to `http://localhost:8000`

5. **Register/Login:**
   - Click "Register" to create a new account
   - Or login with existing credentials

6. **Start chatting:**
   - Type your messages in the chat input
   - For write operations, you'll see approval requests
   - Click "Approve" or "Reject" to handle approvals

## Usage

### Read Operations (No Approval)
- `show me my tickets` - Fetch all your tickets
- `show me closed` - Fetch tickets with "Closed" status
- `summarize ticket PROJ-123` - Get ticket summary

### Write Operations (Approval Required)
- `create ticket in PROJ: Fix bug` - Create ticket (approval required)
- `update ticket PROJ-123: change status to In Progress` - Update ticket (approval required)

When you request a write operation:
1. The system shows a preview of what will change
2. You see an approval box with "Approve" and "Reject" buttons
3. Click "Approve" to execute or "Reject" to cancel

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get session
- `POST /api/auth/logout` - Logout and invalidate session

### Chat
- `POST /api/chat` - Send message and get response
- `GET /api/approvals/pending` - Get pending approvals
- `POST /api/approvals/{request_id}/approve` - Approve request
- `POST /api/approvals/{request_id}/reject` - Reject request

## Architecture

### Frontend
- Single-page HTML application
- Vanilla JavaScript (no frameworks needed)
- Responsive CSS design
- Real-time message updates

### Backend
- FastAPI web framework
- JWT-based authentication
- Session management
- Integration with LangGraph workflow

### Security
- Password hashing (bcrypt)
- JWT tokens for authentication
- Session-based user tracking
- Secure password storage

## Customization

### Change Port
Edit `run_web.py`:
```python
uvicorn.run(web_app, host="0.0.0.0", port=8080)  # Change port
```

### Change Theme
Edit `src/web/templates/chat.html` CSS section to customize colors and styling.

### Add Features
- Extend `src/web/app.py` with new endpoints
- Update `chat.html` with new UI elements
- Add new chat commands in the LangGraph workflow

## Production Deployment

### Using Docker
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "run_web.py"]
```

### Using Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.web.app:web_app --bind 0.0.0.0:8000
```

### Environment Variables
For production, set:
- `SECRET_KEY` - Strong random secret for JWT
- All JIRA and Google API credentials
- `ENVIRONMENT=production` (if needed)

## Troubleshooting

### Port Already in Use
Change the port in `run_web.py` or kill the process using port 8000.

### Template Not Found
Ensure `src/web/templates/chat.html` exists. The app will auto-detect the path.

### Authentication Issues
- Clear browser cookies
- Check that passwords are being hashed correctly
- Verify JWT secret key is set

### Chat Not Working
- Check browser console for errors
- Verify LangGraph workflow is initialized
- Check server logs for errors

## Features in Detail

### User Registration
- Username and password required
- Email optional
- Passwords are securely hashed
- Duplicate usernames prevented

### Chat Interface
- Real-time message display
- Auto-scrolling to latest message
- Loading indicators
- Error handling

### Approval System
- Visual approval boxes
- Preview of changes
- One-click approve/reject
- Request ID tracking

## Next Steps

- Add user profiles
- Implement message history persistence
- Add file upload support
- Integrate with external authentication (OAuth)
- Add admin dashboard
- Implement rate limiting


# Deployment Guide

This guide covers deploying the JIRA Autonomous Agent as a fully automated, production-ready system.

## Architecture Overview

The system consists of two main components:

1. **API Server**: REST API for external integrations and webhooks
2. **Automation Scheduler**: Background service for periodic automation tasks

Both components can run as separate Docker containers or as a single service.

## Prerequisites

- Docker and Docker Compose installed
- JIRA instance with API access
- Google Gemini API key
- (Optional) PostgreSQL database for production

## Quick Start with Docker Compose

1. **Create `.env` file:**
   ```env
   GOOGLE_API_KEY=your_google_api_key
   JIRA_BASE_URL=https://your-instance.atlassian.net
   JIRA_USERNAME=your_username
   JIRA_PAT=your_personal_access_token
   DATABASE_URL=sqlite:///./jira_agent.db  # or PostgreSQL URL
   ```

2. **Start services:**
   ```bash
   docker-compose up -d
   ```

3. **Check status:**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

4. **Access API:**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## Manual Deployment

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file with required variables (see above).

### 3. Initialize Database

```bash
python -c "from src.database.models import init_db; init_db()"
```

### 4. Run API Server

```bash
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

### 5. Run Automation Scheduler (separate terminal)

```bash
python -m src.automation.scheduler
```

## Production Deployment

### Using Docker

1. **Build image:**
   ```bash
   docker build -t jira-agent:latest .
   ```

2. **Run with environment variables:**
   ```bash
   docker run -d \
     --name jira-agent-api \
     -p 8000:8000 \
     -e GOOGLE_API_KEY=... \
     -e JIRA_BASE_URL=... \
     -e JIRA_USERNAME=... \
     -e JIRA_PAT=... \
     -v $(pwd)/logs:/app/logs \
     jira-agent:latest
   ```

### Using Kubernetes

See `k8s/` directory for Kubernetes manifests (create as needed).

### Using Cloud Platforms

#### AWS ECS/Fargate
- Use Docker image
- Configure environment variables via ECS task definition
- Set up ALB for API access

#### Google Cloud Run
- Deploy container image
- Configure environment variables
- Set up Cloud Scheduler for automation tasks

#### Azure Container Instances
- Deploy container
- Configure environment variables
- Use Azure Functions for scheduled tasks

## Configuration

### Automation Rules

Automation rules are defined in `src/automation/automation_engine.py`. To customize:

1. Edit `AutomationEngine._setup_default_rules()`
2. Add custom rules using `AutomationRule` class
3. Rules are evaluated in priority order

### API Configuration

Edit `src/api/server.py` to:
- Configure CORS origins
- Add authentication middleware
- Customize rate limiting
- Add request logging

## Monitoring

### Health Checks

- API health: `GET /health`
- Returns status and timestamp

### Logging

Logs are written to:
- Console (stdout)
- `logs/` directory (if configured)

Log levels:
- INFO: Normal operations
- WARNING: Non-critical issues
- ERROR: Errors requiring attention

### Metrics

Track automation performance:
- Tickets processed per cycle
- SLA violations
- Error rates
- Response times

## Webhook Configuration

### JIRA Webhooks

Configure JIRA to send webhooks to:
```
POST https://your-domain.com/api/v1/webhooks/jira
```

Supported events:
- `jira:issue_created`
- `jira:issue_updated`
- `jira:issue_deleted`
- `jira:issue_assigned`

### External System Integration

The API accepts webhooks from external systems:
- CI/CD pipelines
- Monitoring tools
- Chat platforms (Slack, Teams)
- Email systems

## Scaling

### Horizontal Scaling

- API server: Stateless, can run multiple instances behind load balancer
- Scheduler: Run single instance to avoid duplicate processing

### Database

For production, use PostgreSQL:
```env
DATABASE_URL=postgresql://user:password@host:5432/jira_agent
```

## Security

### API Authentication

Add authentication middleware:
```python
from fastapi import Depends, HTTPException, Header

async def verify_token(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=403)
    return x_api_key
```

### Secrets Management

- Use environment variables (not hardcoded)
- Use secret management services (AWS Secrets Manager, HashiCorp Vault)
- Rotate API keys regularly

### Network Security

- Use HTTPS in production
- Restrict API access via firewall
- Use VPN for internal access

## Backup & Recovery

### Database Backups

```bash
# SQLite
cp jira_agent.db backups/jira_agent_$(date +%Y%m%d).db

# PostgreSQL
pg_dump jira_agent > backups/jira_agent_$(date +%Y%m%d).sql
```

### Configuration Backups

Backup `.env` and automation rules regularly.

## Troubleshooting

### API Not Starting

1. Check environment variables
2. Verify port 8000 is available
3. Check logs: `docker-compose logs jira-agent-api`

### Automation Not Running

1. Check scheduler logs: `docker-compose logs jira-agent-scheduler`
2. Verify JIRA credentials
3. Check automation rules are enabled

### Database Issues

1. Verify database connection string
2. Check database permissions
3. Initialize database: `python -c "from src.database.models import init_db; init_db()"`

## Maintenance

### Updates

1. Pull latest code
2. Rebuild Docker image
3. Restart services: `docker-compose restart`

### Monitoring

- Set up alerts for:
  - API downtime
  - High error rates
  - SLA violations
  - Automation failures

## Support

For issues or questions:
- Check logs first
- Review API documentation: `/docs`
- Check JIRA API documentation: https://developer.atlassian.com/cloud/jira/platform/rest/v3/


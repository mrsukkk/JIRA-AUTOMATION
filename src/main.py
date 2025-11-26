
import logging
from graphs.jira_agent_graph import app
from langchain_core.messages import HumanMessage, AIMessage
from models.llm_config import LLMConfig
from approval.approval_manager import approval_manager

logger = logging.getLogger(__name__)

def run_agent():
    logger.info("run_agent called")
    print("="*60)
    print("JIRA Agent with Human Approval Required")
    print("="*60)
    print("\n ** IMPORTANT: All write operations require your approval! **")
    print("   - Read operations (fetch, summarize) work immediately")
    print("   - Write operations (create, update, transition) require approval")
    print("   - Type 'approve <request_id>' to approve or 'reject <request_id>' to reject")
    print("\nExample commands:")
    print("  - 'show me my tickets' - Fetch tickets (no approval needed)")
    print("  - 'create ticket in PROJ: Fix bug' - Create ticket (approval required)")
    print("  - 'update ticket PROJ-123: change status to In Progress' - Update (approval required)")
    print("="*60)
    print()
    
    # Initialize state
    current_state = {
        "messages": [],
        "greeted": False,
        "status_filter": None,
        "ticket_to_summarize": None,
        "pending_approval_id": None,
        "operation_type": None
    }
    
    while True:
        # STRICT: Require human message to proceed
        user_input = input("\nYou: ").strip()
        logger.info("User input: %s", user_input)
        
        if not user_input:
            logger.warning("No user input provided.")
            print("Please provide a message to proceed.")
            continue
            
        if user_input.lower() in ("exit", "quit"):
            logger.info("Exiting agent loop.")
            print("Exiting agent.")
            break

        # Prepare input state for the workflow
        input_state = {
            **current_state,
            "messages": [HumanMessage(content=user_input)]
        }

        # Invoke the LangGraph workflow
        try:
            logger.info("Invoking LangGraph workflow with input_state: %s", input_state)
            result = app.invoke(input_state)
            logger.info("LangGraph workflow completed")
            # Update state
            current_state = {
                "messages": result.get("messages", []),
                "greeted": result.get("greeted", False),
                "status_filter": result.get("status_filter"),
                "ticket_to_summarize": result.get("ticket_to_summarize"),
                "pending_approval_id": result.get("pending_approval_id"),
                "operation_type": result.get("operation_type")
            }
            # Print AI responses
            for msg in result.get("messages", []):
                if isinstance(msg, AIMessage):
                    logger.info("AI response: %s", msg.content)
                    print(f"\n ** AI: {msg.content} **")
            # Show pending approvals
            pending = approval_manager.get_pending_approvals()
            if pending:
                logger.info("%d pending approvals found.", len(pending))
                print(f"\n ** You have {len(pending)} pending approval(s). Review and approve/reject them. **")
        except Exception as e:
            logger.error("Error in agent loop: %s", str(e))
            print(f"\n ** Error: {str(e)} **")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    logger.info("Main execution started.")
    LLMConfig.get_llm()
    run_agent()
    logger.info("Main execution completed.")
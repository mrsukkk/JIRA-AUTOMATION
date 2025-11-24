"""
Approval manager for human-in-the-loop operations.
All write operations require human approval before execution.
"""
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Represents a pending approval request."""
    request_id: str
    operation_type: str  # create, update, transition, assign, comment, etc.
    ticket_key: Optional[str] = None
    preview: Dict[str, Any] = None  # What will be changed
    description: str = ""  # Human-readable description
    created_at: datetime = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.preview is None:
            self.preview = {}


class ApprovalManager:
    """Manages approval requests and human-in-the-loop operations."""
    
    def __init__(self):
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_history: List[ApprovalRequest] = []
    
    def create_approval_request(
        self,
        operation_type: str,
        preview: Dict[str, Any],
        description: str = "",
        ticket_key: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Create a new approval request.
        
        Args:
            operation_type: Type of operation (create, update, transition, etc.)
            preview: Preview of what will be changed
            description: Human-readable description
            ticket_key: Optional ticket key if applicable
            
        Returns:
            ApprovalRequest object
        """
        import uuid
        request_id = str(uuid.uuid4())
        
        approval = ApprovalRequest(
            request_id=request_id,
            operation_type=operation_type,
            ticket_key=ticket_key,
            preview=preview,
            description=description,
            status=ApprovalStatus.PENDING
        )
        
        self.pending_approvals[request_id] = approval
        logger.info("Created approval request %s for operation: %s", request_id, operation_type)
        
        return approval
    
    def format_approval_message(self, approval: ApprovalRequest) -> str:
        """
        Format an approval request as a human-readable message.
        
        Returns:
            Formatted message string
        """
        lines = [
            f"\n{'='*60}",
            f"⚠️  APPROVAL REQUIRED - {approval.operation_type.upper()}",
            f"{'='*60}",
            f"Request ID: {approval.request_id}",
        ]
        
        if approval.ticket_key:
            lines.append(f"Ticket: {approval.ticket_key}")
        
        if approval.description:
            lines.append(f"\nDescription: {approval.description}")
        
        lines.append("\n📋 PREVIEW OF CHANGES:")
        for key, value in approval.preview.items():
            if value is not None:
                lines.append(f"  • {key}: {value}")
        
        lines.append(f"\n{'='*60}")
        lines.append("Type 'approve {request_id}' to proceed or 'reject {request_id}' to cancel")
        lines.append(f"{'='*60}\n")
        
        return "\n".join(lines)
    
    def approve(self, request_id: str, approved_by: str = "user") -> bool:
        """
        Approve a pending request.
        
        Args:
            request_id: ID of the approval request
            approved_by: Who approved it
            
        Returns:
            True if approved, False if not found
        """
        if request_id not in self.pending_approvals:
            logger.warning("Approval request %s not found", request_id)
            return False
        
        approval = self.pending_approvals[request_id]
        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = approved_by
        
        # Move to history
        self.approval_history.append(approval)
        del self.pending_approvals[request_id]
        
        logger.info("Approval request %s approved by %s", request_id, approved_by)
        return True
    
    def reject(self, request_id: str, reason: str = "", rejected_by: str = "user") -> bool:
        """
        Reject a pending request.
        
        Args:
            request_id: ID of the approval request
            reason: Reason for rejection
            rejected_by: Who rejected it
            
        Returns:
            True if rejected, False if not found
        """
        if request_id not in self.pending_approvals:
            logger.warning("Approval request %s not found", request_id)
            return False
        
        approval = self.pending_approvals[request_id]
        approval.status = ApprovalStatus.REJECTED
        approval.rejection_reason = reason
        approval.approved_by = rejected_by
        
        # Move to history
        self.approval_history.append(approval)
        del self.pending_approvals[request_id]
        
        logger.info("Approval request %s rejected by %s: %s", request_id, rejected_by, reason)
        return True
    
    def get_approval(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self.pending_approvals.get(request_id)
    
    def is_approved(self, request_id: str) -> bool:
        """Check if a request is approved."""
        approval = self.get_approval(request_id)
        if not approval:
            # Check history
            for hist_approval in self.approval_history:
                if hist_approval.request_id == request_id:
                    return hist_approval.status == ApprovalStatus.APPROVED
            return False
        return approval.status == ApprovalStatus.APPROVED
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self.pending_approvals.values())


# Global approval manager instance
approval_manager = ApprovalManager()


"""
Pipeline Orchestrator for Media Buddy

Manages the multi-phase collaborative writing workflow, tracking state 
and coordinating between different services.
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class WorkflowPhase(Enum):
    """Enum for workflow phases."""
    DISCOVERY = "discovery"          # Article discovered, ready for user contribution
    USER_CONTRIBUTION = "user_contribution"  # User has provided their take
    AI_ENHANCEMENT = "ai_enhancement"       # AI has enhanced user's contribution
    TIMELINE_GENERATION = "timeline_generation"  # Timeline created
    IMAGE_PROCESSING = "image_processing"    # Images generated and stylized
    FINAL_ASSEMBLY = "final_assembly"       # Final assets assembled
    COMPLETE = "complete"                   # Pipeline complete

@dataclass
class WorkflowState:
    """Represents the current state of an article in the workflow."""
    article_id: int
    current_phase: WorkflowPhase
    phases_completed: List[WorkflowPhase]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    
    def is_phase_complete(self, phase: WorkflowPhase) -> bool:
        """Check if a specific phase has been completed."""
        return phase in self.phases_completed
    
    def can_advance_to(self, phase: WorkflowPhase) -> bool:
        """Check if workflow can advance to a specific phase."""
        phase_order = list(WorkflowPhase)
        current_index = phase_order.index(self.current_phase)
        target_index = phase_order.index(phase)
        
        # Can execute current phase or advance to next phase
        return target_index <= current_index + 1
    
    def mark_phase_complete(self, phase: WorkflowPhase):
        """Mark a phase as completed and advance if appropriate."""
        if phase not in self.phases_completed:
            self.phases_completed.append(phase)
        
        # Advance to next phase if current phase is complete
        if phase == self.current_phase:
            phase_order = list(WorkflowPhase)
            current_index = phase_order.index(self.current_phase)
            if current_index < len(phase_order) - 1:
                self.current_phase = phase_order[current_index + 1]
        
        self.updated_at = datetime.now()

class PipelineOrchestrator:
    """Orchestrates the multi-phase collaborative writing pipeline."""
    
    def __init__(self):
        """Initialize the pipeline orchestrator."""
        self._workflow_states: Dict[int, WorkflowState] = {}
    
    def initialize_workflow(self, article_id: int, metadata: Optional[Dict] = None) -> WorkflowState:
        """
        Initialize a new workflow for an article.
        
        Args:
            article_id: Database ID of the article
            metadata: Optional metadata dictionary
            
        Returns:
            Initialized workflow state
        """
        now = datetime.now()
        state = WorkflowState(
            article_id=article_id,
            current_phase=WorkflowPhase.DISCOVERY,
            phases_completed=[],
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        self._workflow_states[article_id] = state
        logger.info(f"Initialized workflow for article {article_id}")
        return state
    
    def get_workflow_state(self, article_id: int) -> Optional[WorkflowState]:
        """
        Get the current workflow state for an article.
        
        Args:
            article_id: Database ID of the article
            
        Returns:
            Workflow state if exists, None otherwise
        """
        # Check in-memory state first
        if article_id in self._workflow_states:
            return self._workflow_states[article_id]
        
        # If not in memory, try to restore from database
        return self._restore_workflow_from_database(article_id)
    
    def advance_workflow(self, article_id: int, completed_phase: WorkflowPhase) -> bool:
        """
        Advance the workflow by marking a phase as complete.
        
        Args:
            article_id: Database ID of the article
            completed_phase: Phase that has been completed
            
        Returns:
            True if advancement successful, False otherwise
        """
        state = self.get_workflow_state(article_id)
        if not state:
            logger.error(f"No workflow state found for article {article_id}")
            return False
        
        state.mark_phase_complete(completed_phase)
        logger.info(f"Advanced workflow for article {article_id} - completed {completed_phase.value}")
        return True
    
    def can_execute_phase(self, article_id: int, target_phase: WorkflowPhase) -> bool:
        """
        Check if a specific phase can be executed for an article.
        
        Args:
            article_id: Database ID of the article
            target_phase: Phase to check
            
        Returns:
            True if phase can be executed, False otherwise
        """
        state = self.get_workflow_state(article_id)
        if not state:
            return False
        
        return state.can_advance_to(target_phase)
    
    def get_next_phase(self, article_id: int) -> Optional[WorkflowPhase]:
        """
        Get the next phase that should be executed for an article.
        
        Args:
            article_id: Database ID of the article
            
        Returns:
            Next phase or None if workflow is complete
        """
        state = self.get_workflow_state(article_id)
        if not state:
            return None
        
        if state.current_phase == WorkflowPhase.COMPLETE:
            return None
        
        return state.current_phase
    
    def get_workflow_summary(self, article_id: int) -> Dict[str, Any]:
        """
        Get a summary of the workflow state for an article.
        
        Args:
            article_id: Database ID of the article
            
        Returns:
            Dictionary with workflow summary information
        """
        state = self.get_workflow_state(article_id)
        if not state:
            return {"error": "No workflow found"}
        
        phase_order = list(WorkflowPhase)
        total_phases = len(phase_order)
        completed_phases = len(state.phases_completed)
        
        return {
            "article_id": article_id,
            "current_phase": state.current_phase.value,
            "progress": f"{completed_phases}/{total_phases}",
            "progress_percent": int((completed_phases / total_phases) * 100),
            "phases_completed": [p.value for p in state.phases_completed],
            "next_action": self._get_next_action_description(state),
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "metadata": state.metadata
        }
    
    def _get_next_action_description(self, state: WorkflowState) -> str:
        """Get a human-readable description of the next action needed."""
        phase_actions = {
            WorkflowPhase.DISCOVERY: "Add your perspective/take on this story",
            WorkflowPhase.USER_CONTRIBUTION: "Enhance your contribution with AI",
            WorkflowPhase.AI_ENHANCEMENT: "Generate visual timeline",
            WorkflowPhase.TIMELINE_GENERATION: "Process images for scenes",
            WorkflowPhase.IMAGE_PROCESSING: "Assemble final assets",
            WorkflowPhase.FINAL_ASSEMBLY: "Complete!",
            WorkflowPhase.COMPLETE: "Workflow complete"
        }
        
        return phase_actions.get(state.current_phase, "Unknown phase")
    
    def list_active_workflows(self) -> List[Dict[str, Any]]:
        """
        List all active workflows with their current status.
        
        Returns:
            List of workflow summaries
        """
        return [
            self.get_workflow_summary(article_id) 
            for article_id in self._workflow_states.keys()
        ]
    
    def cleanup_completed_workflows(self, max_age_days: int = 30):
        """
        Clean up old completed workflows.
        
        Args:
            max_age_days: Maximum age in days for completed workflows
        """
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        to_remove = []
        for article_id, state in self._workflow_states.items():
            if (state.current_phase == WorkflowPhase.COMPLETE and 
                state.updated_at < cutoff_date):
                to_remove.append(article_id)
        
        for article_id in to_remove:
            del self._workflow_states[article_id]
            logger.info(f"Cleaned up completed workflow for article {article_id}")
    
    def _restore_workflow_from_database(self, article_id: int) -> Optional[WorkflowState]:
        """
        Restore workflow state from database article data.
        
        Args:
            article_id: Database ID of the article
            
        Returns:
            Restored workflow state or None if article not found
        """
        try:
            # Import here to avoid circular imports
            from .. import db
            from ..models import NewsArticle
            
            article = NewsArticle.query.get(article_id)
            if not article:
                return None
            
            # Determine current phase and completed phases based on database state
            if article.enhanced_content:
                if article.timeline_json:
                    current_phase = WorkflowPhase.IMAGE_PROCESSING
                    completed_phases = [
                        WorkflowPhase.DISCOVERY,
                        WorkflowPhase.USER_CONTRIBUTION, 
                        WorkflowPhase.AI_ENHANCEMENT,
                        WorkflowPhase.TIMELINE_GENERATION
                    ]
                else:
                    current_phase = WorkflowPhase.TIMELINE_GENERATION
                    completed_phases = [
                        WorkflowPhase.DISCOVERY,
                        WorkflowPhase.USER_CONTRIBUTION,
                        WorkflowPhase.AI_ENHANCEMENT
                    ]
            elif article.user_contribution:
                current_phase = WorkflowPhase.AI_ENHANCEMENT
                completed_phases = [
                    WorkflowPhase.DISCOVERY,
                    WorkflowPhase.USER_CONTRIBUTION
                ]
            elif article.raw_content:
                current_phase = WorkflowPhase.USER_CONTRIBUTION
                completed_phases = [WorkflowPhase.DISCOVERY]
            else:
                # No workflow data found
                return None
            
            # Create workflow state
            now = datetime.now()
            state = WorkflowState(
                article_id=article_id,
                current_phase=current_phase,
                phases_completed=completed_phases,
                created_at=now,
                updated_at=now,
                metadata={'restored_from_db': True}
            )
            
            # Cache in memory for future use
            self._workflow_states[article_id] = state
            
            logger.info(f"Restored workflow state for article {article_id} from database")
            return state
            
        except Exception as e:
            logger.error(f"Error restoring workflow from database for article {article_id}: {e}")
            return None

# Global orchestrator instance
orchestrator = PipelineOrchestrator() 
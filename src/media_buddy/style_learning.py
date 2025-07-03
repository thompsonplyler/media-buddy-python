"""
Style Learning System - Captures and learns from the user's edits to improve future outputs.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np
from pathlib import Path

class StyleLearningSystem:
    """
    Learns from the user's editing patterns to improve future voice generation.
    """
    
    def __init__(self, learning_dir: str = "private/style_learning"):
        self.learning_dir = Path(learning_dir)
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        
        self.edits_file = self.learning_dir / "edit_history.jsonl"
        self.patterns_file = self.learning_dir / "learned_patterns.json"
        self.successful_examples_dir = self.learning_dir / "successful_examples"
        self.successful_examples_dir.mkdir(exist_ok=True)
        
        # For semantic analysis of edits
        self._embedding_model = None
    
    @property
    def embedding_model(self):
        """Lazy load embedding model."""
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model
    
    def record_edit_session(self, 
                           original_script: str, 
                           edited_script: str,
                           topic: str,
                           context: Dict = None) -> str:
        """
        Record a complete edit session for learning.
        
        Args:
            original_script: The AI-generated script
            edited_script: the user's edited version
            topic: The topic/query that generated this script
            context: Additional context (article sources, etc.)
            
        Returns:
            Edit session ID for reference
        """
        session_id = f"edit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Calculate edit metrics
        edit_analysis = self._analyze_edits(original_script, edited_script)
        
        edit_record = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "original_script": original_script,
            "edited_script": edited_script,
            "context": context or {},
            "analysis": edit_analysis
        }
        
        # Append to edit history
        with open(self.edits_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(edit_record) + '\n')
        
        # Save successful example if significantly different
        if edit_analysis['edit_magnitude'] > 0.3:  # Significant changes
            self._save_successful_example(session_id, edited_script, topic, edit_analysis)
        
        # Update learned patterns
        self._update_patterns(edit_analysis, topic)
        
        logging.info(f"Recorded edit session {session_id} - {edit_analysis['edit_magnitude']:.2f} magnitude")
        return session_id
    
    def _analyze_edits(self, original: str, edited: str) -> Dict:
        """Analyze the differences between original and edited scripts."""
        
        # Basic metrics
        original_words = original.split()
        edited_words = edited.split()
        
        length_change = len(edited_words) - len(original_words)
        length_ratio = len(edited_words) / len(original_words) if original_words else 1.0
        
        # Semantic similarity
        original_embedding = self.embedding_model.encode(original)
        edited_embedding = self.embedding_model.encode(edited)
        similarity = np.dot(original_embedding, edited_embedding) / (
            np.linalg.norm(original_embedding) * np.linalg.norm(edited_embedding)
        )
        edit_magnitude = 1.0 - similarity
        
        # Common edit types (simple heuristics)
        edit_types = []
        if abs(length_change) > 10:
            edit_types.append("length_adjustment")
        if "," in edited and edited.count(",") > original.count(","):
            edit_types.append("added_pauses")
        if any(word in edited.lower() for word in ["actually", "really", "basically", "essentially"]):
            if not any(word in original.lower() for word in ["actually", "really", "basically", "essentially"]):
                edit_types.append("added_qualifiers")
        
        return {
            "edit_magnitude": edit_magnitude,
            "length_change": length_change,
            "length_ratio": length_ratio,
            "semantic_similarity": similarity,
            "edit_types": edit_types,
            "original_word_count": len(original_words),
            "edited_word_count": len(edited_words)
        }
    
    def _save_successful_example(self, session_id: str, edited_script: str, topic: str, analysis: Dict):
        """Save significantly improved scripts as successful examples."""
        
        example_file = self.successful_examples_dir / f"{session_id}.md"
        
        with open(example_file, 'w', encoding='utf-8') as f:
            f.write(f"# Successful Script: {topic}\n\n")
            f.write(f"*Edit session: {session_id}*\n")
            f.write(f"*Edit magnitude: {analysis['edit_magnitude']:.3f}*\n\n")
            f.write("---\n\n")
            f.write(edited_script)
            f.write("\n\n---\n\n")
            f.write("## Edit Analysis\n\n")
            f.write(f"- Length change: {analysis['length_change']} words\n")
            f.write(f"- Edit types: {', '.join(analysis['edit_types']) if analysis['edit_types'] else 'general_improvement'}\n")
        
        logging.info(f"Saved successful example: {example_file}")
    
    def _update_patterns(self, analysis: Dict, topic: str):
        """Update learned patterns based on new edit data."""
        
        # Load existing patterns
        patterns = {}
        if self.patterns_file.exists():
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                patterns = json.load(f)
        
        # Initialize pattern categories
        if "edit_types" not in patterns:
            patterns["edit_types"] = {}
        if "topic_preferences" not in patterns:
            patterns["topic_preferences"] = {}
        if "length_preferences" not in patterns:
            patterns["length_preferences"] = []
        
        # Update edit type frequencies
        for edit_type in analysis["edit_types"]:
            patterns["edit_types"][edit_type] = patterns["edit_types"].get(edit_type, 0) + 1
        
        # Track length preferences
        patterns["length_preferences"].append({
            "topic": topic,
            "original_length": analysis["original_word_count"],
            "edited_length": analysis["edited_word_count"],
            "ratio": analysis["length_ratio"]
        })
        
        # Keep only recent preferences (last 50)
        if len(patterns["length_preferences"]) > 50:
            patterns["length_preferences"] = patterns["length_preferences"][-50:]
        
        # Save updated patterns
        with open(self.patterns_file, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, indent=2)
    
    def get_style_recommendations(self, topic: str, current_length: int) -> Dict:
        """
        Get recommendations for improving a script based on learned patterns.
        
        Args:
            topic: The topic of the script
            current_length: Current word count
            
        Returns:
            Dictionary of recommendations
        """
        recommendations = {
            "suggested_length": current_length,
            "common_edits": [],
            "style_notes": []
        }
        
        if not self.patterns_file.exists():
            return recommendations
        
        with open(self.patterns_file, 'r', encoding='utf-8') as f:
            patterns = json.load(f)
        
        # Length recommendations
        if "length_preferences" in patterns and patterns["length_preferences"]:
            avg_ratio = np.mean([p["ratio"] for p in patterns["length_preferences"]])
            recommendations["suggested_length"] = int(current_length * avg_ratio)
            
            if avg_ratio < 0.9:
                recommendations["style_notes"].append("Tend to prefer shorter, more concise scripts")
            elif avg_ratio > 1.1:
                recommendations["style_notes"].append("Tend to prefer longer, more detailed scripts")
        
        # Common edit types
        if "edit_types" in patterns:
            sorted_edits = sorted(patterns["edit_types"].items(), key=lambda x: x[1], reverse=True)
            for edit_type, count in sorted_edits[:3]:  # Top 3 edit types
                recommendations["common_edits"].append(f"{edit_type} (seen {count} times)")
        
        return recommendations
    
    def get_successful_examples(self, limit: int = 5) -> List[str]:
        """Get paths to the most recent successful examples."""
        
        example_files = list(self.successful_examples_dir.glob("*.md"))
        example_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        return [str(f) for f in example_files[:limit]]

# Global instance
style_learner = StyleLearningSystem() 
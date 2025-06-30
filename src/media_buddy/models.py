from src.media_buddy.extensions import db
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

# User model removed - not needed for media-buddy functionality

class DailyLog(db.Model):
    log_date = db.Column(db.Date, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    last_updated = db.Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f'<DailyLog {self.log_date.isoformat()}>'

class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    raw_content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    voiced_summary = db.Column(db.Text, nullable=True)
    
    # Collaborative writing workflow fields
    user_contribution = db.Column(db.Text, nullable=True)  # User's original perspective/take
    enhanced_content = db.Column(db.Text, nullable=True)   # AI-enhanced version of user contribution
    workflow_phase = db.Column(db.String(50), nullable=True, default='discovery')  # Current workflow phase
    workflow_metadata = db.Column(db.JSON, nullable=True)  # Workflow state and metadata
    
    # The embedding dimension must match the model output.
    # all-MiniLM-L6-v2 produces a 384-dimensional vector.
    embedding = db.Column(Vector(384))
    timeline_json = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f'<NewsArticle {self.title}>' 
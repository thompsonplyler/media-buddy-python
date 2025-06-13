from . import db
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func

class User(db.Model):
    # Using discord_id as the primary key since it's unique per user
    discord_id = db.Column(db.BigInteger, primary_key=True, autoincrement=False) 
    discord_name = db.Column(db.String(100), nullable=False)
    
    # Riot Games specific information
    lol_summoner_name = db.Column(db.String(80), nullable=True)
    lol_summoner_tag = db.Column(db.String(10), nullable=True)
    puuid = db.Column(db.String(100), unique=True, nullable=True)

    def __repr__(self):
        return f'<User discord_id={self.discord_id} discord_name={self.discord_name}>'

class DailyLog(db.Model):
    log_date = db.Column(db.Date, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    last_updated = db.Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f'<DailyLog {self.log_date.isoformat()}>' 
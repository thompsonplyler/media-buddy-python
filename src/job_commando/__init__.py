import sys
import os
import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import text

# Correct the path to allow for absolute imports from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.job_commando.config import Config
from src.job_commando.extensions import db, migrate
from src.job_commando.models import NewsArticle
from src.job_commando.news_client import fetch_articles
from src.job_commando.text_processor import generate_summary, generate_embedding

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    from src.job_commando.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # Import models here to ensure they are registered with SQLAlchemy
    from src.job_commando import models

    # --- Register CLI Commands ---
    @click.command(name='init-db')
    @with_appcontext
    def init_db_command():
        """Drops and recreates the database with the current schema."""
        print("Initializing the database...")
        try:
            db.drop_all()
            db.create_all()
            # Also create the vector extension if it doesn't exist.
            with db.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            print("Database initialized successfully.")
        except Exception as e:
            print(f"Error initializing database: {e}")

    @click.command(name='fetch-news')
    @click.argument('query')
    @with_appcontext
    def fetch_news_command(query):
        """Fetches news articles for a given query and stores them in the database."""
        print(f"Fetching and storing articles for query: '{query}'")
        articles = fetch_articles(query)
        
        if not articles:
            print("No articles found or an error occurred.")
            return

        new_articles_count = 0
        for article_data in articles:
            exists = db.session.query(NewsArticle.id).filter_by(url=article_data['url']).first() is not None
            if not exists:
                new_article = NewsArticle(
                    url=article_data['url'],
                    title=article_data['title'],
                    raw_content=article_data.get('content', '') or '',
                    summary=None,
                    embedding=None
                )
                db.session.add(new_article)
                new_articles_count += 1
        
        if new_articles_count > 0:
            db.session.commit()
            print(f"Successfully stored {new_articles_count} new articles.")
        else:
            print("No new articles to store.")

    @click.command(name='process-articles')
    @with_appcontext
    def process_articles_command():
        """
        Processes all unprocessed articles in the database, generating
        summaries and embeddings for them.
        """
        print("Fetching unprocessed articles from the database...")
        unprocessed_articles = NewsArticle.query.filter(
            (NewsArticle.summary == None) | (NewsArticle.embedding == None)
        ).all()

        if not unprocessed_articles:
            print("No new articles to process.")
            return

        print(f"Found {len(unprocessed_articles)} articles to process.")
        for article in unprocessed_articles:
            print(f"  - Processing article: {article.title[:50]}...")
            if not article.summary:
                article.summary = generate_summary(article.raw_content)
            
            if article.embedding is None:
                article.embedding = generate_embedding(article.raw_content)
            
            db.session.add(article)

        db.session.commit()
        print("All articles processed and updated successfully.")

    app.cli.add_command(init_db_command)
    app.cli.add_command(fetch_news_command)
    app.cli.add_command(process_articles_command)

    return app

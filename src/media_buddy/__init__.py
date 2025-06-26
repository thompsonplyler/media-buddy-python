import sys
import os
import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
import shutil

# Correct the path to allow for absolute imports from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.media_buddy.config import Config
from src.media_buddy.extensions import db, migrate
from src.media_buddy.models import NewsArticle
from src.media_buddy.services.legacy_adapter import fetch_articles
from src.media_buddy.text_processor import generate_summary, generate_embedding, generate_timeline, generate_voiced_summary_from_article, generate_voiced_summary_from_raw_content, generate_voiced_response_from_articles
from src.media_buddy.image_scout import source_image_for_scene, generate_raw_image, apply_style_to_image
from src.media_buddy.themes import FLUX_THEMES

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    from src.media_buddy.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # Import models here to ensure they are registered with SQLAlchemy
    from src.media_buddy import models

    # --- Register CLI Commands ---
    @click.command(name='init-db')
    @with_appcontext
    def init_db_command():
        """Drops and recreates the database with the current schema."""
        try:
            # Drop the migration tracking table first to ensure a clean slate.
            with db.engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version;"))
                conn.commit()
            
            db.drop_all()
            db.create_all()
            # Also create the vector extension if it doesn't exist.
            with db.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
        except Exception as e:
            print(f"Error initializing database: {e}")

    @click.command(name='fetch-news')
    @click.argument('query')
    @with_appcontext
    def fetch_news_command(query):
        """Fetches news articles for a given query and stores them in the database."""
        articles = fetch_articles(query)
        
        if not articles:
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
        else:
            print("No new articles to store.")

    @click.command(name='process-articles')
    @with_appcontext
    def process_articles_command():
        """
        Processes all unprocessed articles in the database, generating
        summaries and embeddings for them.
        """
        unprocessed_articles = NewsArticle.query.filter(
            (NewsArticle.summary == None) | (NewsArticle.embedding == None)
        ).all()

        if not unprocessed_articles:
            return

        for article in unprocessed_articles:
            if not article.summary:
                article.summary = generate_summary(article.raw_content)
            
            if article.embedding is None:
                article.embedding = generate_embedding(article.raw_content)
            
            db.session.add(article)

        db.session.commit()

    @click.command(name='generate-voiced-summary')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to process.')
    @click.option('--length', default=250, type=int, help='The target word count for the summary.')
    @with_appcontext
    def generate_voiced_summary_command(article_id, length):
        """Generates a stylized summary based on your writing samples."""
        article = NewsArticle.query.get(article_id)
        if not article:
            print(f"Error: Article with ID {article_id} not found.")
            return

        if not article.summary:
            print(f"Error: Article {article_id} does not have a base summary. Run 'process-articles' first.")
            return
        
        print(f"Generating voiced summary for article: {article.title}...")

        try:
            voiced_summary = generate_voiced_summary_from_article(article, length)
            article.voiced_summary = voiced_summary
            db.session.commit()
            
            print("\n--- STYLIZED SUMMARY ---")
            print(voiced_summary)
            print("--- END ---")
            print(f"\nSuccessfully generated and saved voiced summary for article {article_id}.")
        except Exception as e:
            print(f"An error occurred while generating the voiced summary: {e}")

    @click.command(name='generate-voice-response')
    @click.argument('query')
    @click.option('--length', default=400, type=int, help='The target word count for the response.')
    @click.option('--top-articles', default=3, type=int, help='Number of top articles to synthesize from.')
    @with_appcontext
    def generate_voice_response_command(query, length, top_articles):
        """Generates Thompson's response to the top articles on a given topic."""
        
        print(f"🔍 Finding top {top_articles} articles for query: '{query}'")
        
        # Find articles matching the query with flexible keyword search
        query_keywords = [word.strip().lower() for word in query.split() if len(word.strip()) > 2]
        print(f"🔍 Searching for keywords: {query_keywords}")
        
        if not query_keywords:
            print("❌ No valid keywords in query")
            return
        
        # Build flexible search conditions
        title_conditions = [NewsArticle.title.ilike(f'%{keyword}%') for keyword in query_keywords]
        content_conditions = [NewsArticle.raw_content.ilike(f'%{keyword}%') for keyword in query_keywords]
        
        # Article matches if it contains ANY of the keywords in title OR content
        articles = NewsArticle.query.filter(
            NewsArticle.raw_content.isnot(None),
            db.or_(
                db.or_(*title_conditions),
                db.or_(*content_conditions)
            )
        ).order_by(NewsArticle.id.desc()).limit(top_articles * 3).all()  # Get extra for filtering
        
        if not articles:
            print(f"❌ No articles found matching '{query}'. Try running 'fetch-news \"{query}\"' first.")
            return
        
        # Score articles by keyword matches and content quality
        scored_articles = []
        for article in articles:
            if len(article.raw_content.strip()) < 1000:
                continue  # Skip short articles
                
            # Count keyword matches
            title_lower = article.title.lower()
            content_lower = article.raw_content.lower()
            
            keyword_score = 0
            for keyword in query_keywords:
                if keyword in title_lower:
                    keyword_score += 3  # Title matches worth more
                if keyword in content_lower:
                    keyword_score += 1
            
            # Bonus for multiple keyword matches
            if keyword_score > len(query_keywords):
                keyword_score += 2
                
            scored_articles.append((article, keyword_score))
        
        # Sort by score (highest first) and take top articles
        scored_articles.sort(key=lambda x: x[1], reverse=True)
        quality_articles = [article for article, score in scored_articles[:top_articles]]
        
        if len(quality_articles) < top_articles:
            print(f"⚠️  Only found {len(quality_articles)} quality articles (wanted {top_articles})")
        
        if not quality_articles:
            print("❌ No articles with substantial content found.")
            return
        
        print(f"📰 Selected articles:")
        for i, (article, score) in enumerate(scored_articles[:len(quality_articles)], 1):
            print(f"  {i}. {article.title[:60]}... ({len(article.raw_content)} chars, score: {score})")
        
        try:
            # Generate Thompson's response to the combined articles
            voice_response = generate_voiced_response_from_articles(quality_articles, query, length)
            
            # Save to private/writing_style_samples/test/ with logical filename
            output_dir = os.path.join('private', 'writing_style_samples', 'test')
            os.makedirs(output_dir, exist_ok=True)
            
            # Create filename from query and date
            from datetime import datetime
            safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-')).rstrip()
            safe_query = safe_query.replace(' ', '-').lower()
            timestamp = datetime.now().strftime('%Y-%m-%d')
            filename = f"{safe_query}-{timestamp}.md"
            filepath = os.path.join(output_dir, filename)
            
            # Save the response
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Thompson's Response: {query}\n\n")
                f.write(f"*Generated from {len(quality_articles)} articles on {timestamp}*\n\n")
                f.write("---\n\n")
                f.write(voice_response)
                f.write("\n\n---\n\n")
                f.write("## Source Articles:\n\n")
                for i, article in enumerate(quality_articles, 1):
                    f.write(f"{i}. **{article.title}**\n")
                    f.write(f"   - URL: {article.url}\n")
                    f.write(f"   - Content: {len(article.raw_content)} characters\n\n")
            
            print(f"\n💾 Saved Thompson's response to: {filepath}")
            print("\n--- THOMPSON'S RESPONSE ---")
            print(voice_response)
            print("--- END ---")
            
        except Exception as e:
            print(f"❌ Error generating voice response: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='generate-timeline')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to process.')
    @with_appcontext
    def generate_timeline_command(article_id):
        """Generates a timeline of scenes from the voiced summary."""
        article = NewsArticle.query.get(article_id)
        if not article:
            print(f"Error: Article with ID {article_id} not found.")
            return

        if not article.voiced_summary:
            print(f"Error: Article {article_id} does not have a voiced summary. Please run 'generate-voiced-summary' first.")
            return

        print(f"Generating timeline for article: {article.title}")
        timeline = generate_timeline(article.voiced_summary)
        
        article.timeline_json = timeline
        db.session.commit()
        
        print(f"Successfully generated and saved timeline for article {article_id}.")
        print("\n--- TIMELINE ---")
        import json
        print(json.dumps(timeline, indent=2))
        print("--- END ---")

    @click.command(name='source-images')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to process.')
    @with_appcontext
    def source_images_command(article_id):
        """Finds or generates image prompts for each scene in an article's timeline."""
        article = NewsArticle.query.get(article_id)
        if not article:
            print(f"Error: Article with ID {article_id} not found.")
            return

        if not article.timeline_json:
            print(f"Error: Article {article_id} does not have a timeline. Please run 'generate-timeline' first.")
            return
        
        print(f"Sourcing images for article: {article.title}")
        
        timeline = article.timeline_json
        
        # First, clean up any old image data to ensure idempotency.
        for scene in timeline:
            if 'found_image_url' in scene:
                del scene['found_image_url']
            if 'generated_image_prompt' in scene:
                del scene['generated_image_prompt']

        # Now, process each scene to get new image data.
        for scene in timeline:
            image_data = source_image_for_scene(scene['description'])
            scene.update(image_data)
            
        # Explicitly flag the column as modified.
        flag_modified(article, "timeline_json")
        db.session.commit()
        
        print(f"Successfully sourced images and updated timeline for article {article_id}.")
        print("\n--- UPDATED TIMELINE ---")
        import json
        print(json.dumps(article.timeline_json, indent=2))
        print("--- END ---")

    @click.command(name='generate-raw-images')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to generate raw images for.')
    @click.option('--limit', type=int, default=0, help='Limit the number of images to generate (0 for all).')
    @with_appcontext
    def generate_raw_images_command(article_id, limit):
        """Generates raw, unstyled images for each scene in a timeline."""
        article = NewsArticle.query.get(article_id)
        if not article:
            print(f"Error: Article with ID {article_id} not found.")
            return

        if not article.timeline_json:
            print(f"Error: Article {article_id} does not have a timeline. Please run 'generate-timeline' first.")
            return
            
        print(f"Generating raw images for article: {article.title}")
        
        timeline = article.timeline_json
        
        scenes_to_process = timeline
        if limit > 0:
            scenes_to_process = [s for s in timeline if not s.get('raw_image_path')][:limit]
        else:
            scenes_to_process = [s for s in timeline if not s.get('raw_image_path')]

        if not scenes_to_process:
            print("No new scenes to process. All raw images may already exist.")
            return

        for scene in scenes_to_process:
            scene_number = scene['scene']

            # Use the main 'description' as the source of the prompt
            if scene.get('description'):
                raw_path = generate_raw_image(
                    prompt=scene['description'],
                    article_id=article.id,
                    scene_number=scene_number,
                    is_user_scene=scene.get('is_user_scene', False)
                )
                
                if raw_path:
                    scene['raw_image_path'] = raw_path
                else:
                    print(f"Failed to produce a raw image for scene {scene_number}. See logs for details.")
            else:
                print(f"Skipping scene {scene_number} - no description found.")

        flag_modified(article, "timeline_json")
        db.session.commit()
        
        print(f"\nRaw image generation complete for article {article_id}.")

    @click.command(name='stylize-images')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to stylize images for.')
    @click.option('--theme', required=True, type=click.Choice(FLUX_THEMES.keys()), help='The name of the visual theme to apply.')
    @click.option('--limit', type=int, default=0, help='Limit the number of images to stylize (0 for all).')
    @with_appcontext
    def stylize_images_command(article_id, theme, limit):
        """Applies a consistent visual theme to the raw images of an article."""
        article = NewsArticle.query.get(article_id)
        if not article:
            print(f"Error: Article with ID {article_id} not found.")
            return

        if not article.timeline_json:
            print(f"Error: Article {article_id} does not have a timeline. Please run 'generate-timeline' first.")
            return
            
        style_prompt = FLUX_THEMES.get(theme)
        if not style_prompt:
            # This case should theoretically not be hit due to click.Choice
            print(f"Error: Invalid theme '{theme}'.")
            return

        print(f"Stylizing raw images for article: {article.title} with theme '{theme}'")
        
        timeline = article.timeline_json
        
        scenes_to_process = timeline
        # Select scenes that have a raw image but not a stylized one yet.
        if limit > 0:
            scenes_to_process = [s for s in timeline if s.get('raw_image_path') and not s.get('stylized_image_path')][:limit]
        else:
            scenes_to_process = [s for s in timeline if s.get('raw_image_path') and not s.get('stylized_image_path')]

        if not scenes_to_process:
            print("No new scenes to process. All raw images may already be stylized.")
            return

        for scene in scenes_to_process:
            scene_number = scene['scene']
            raw_image_path = scene.get('raw_image_path')

            if raw_image_path:
                stylized_path = apply_style_to_image(
                    image_path_or_url=raw_image_path,
                    style_prompt=style_prompt,
                    article_id=article.id,
                    scene_number=scene_number
                )
                
                if stylized_path:
                    scene['stylized_image_path'] = stylized_path
                    print(f"Successfully stylized image for scene {scene_number}.")
                else:
                    print(f"Failed to stylize image for scene {scene_number}. See logs for details.")
            else:
                print(f"Skipping scene {scene_number} - no raw image path found.")

        flag_modified(article, "timeline_json")
        db.session.commit()
        print(f"\nCompleted stylization pass for article {article.id}.")

    @click.command(name='process-story')
    @click.option('--query', type=str, help='The news query to fetch and process a new article.')
    @click.option('--article-id', type=int, help='The ID of an existing article to process.')
    @click.option('--theme', required=True, type=click.Choice(FLUX_THEMES.keys()), help='The visual theme for stylization.')
    @click.option('--length', default=200, type=int, help='Target word count for the voiced summary.')
    @with_appcontext
    def process_story_command(query, article_id, theme, length):
        """Runs the full pipeline to generate all assets for a story."""
        if not query and not article_id:
            print("Error: You must provide either --query or --article-id.")
            return
        if query and article_id:
            print("Error: Please provide either --query or --article-id, not both.")
            return

        article = None
        try:
            # Step 1: Get the Article
            if query:
                print(f"Fetching new article for query: '{query}'")
                articles_data = fetch_articles(query)
                if not articles_data:
                    print("No articles found for that query.")
                    return
                
                new_article_data = next((a for a in articles_data if not db.session.query(NewsArticle.id).filter_by(url=a['url']).first()), None)

                if not new_article_data:
                    print("No *new* articles found for that query. All are already in the database.")
                    return

                article = NewsArticle(
                    url=new_article_data['url'],
                    title=new_article_data['title'],
                    raw_content=new_article_data.get('content', '') or '',
                )
                db.session.add(article)
                db.session.commit()
                article_id = article.id
                print(f"Successfully fetched and created new article with ID: {article_id}")
            else:
                article = NewsArticle.query.get(article_id)
                if not article:
                    print(f"Error: Article with ID {article_id} not found.")
                    return

            print(f"--- Starting processing pipeline for Article {article.id}: {article.title} ---")

            # Step 2: Run the asset generation pipeline
            if not article.summary:
                print("Generating base summary...")
                article.summary = generate_summary(article.raw_content)
            
            if not article.voiced_summary:
                print("Generating voiced summary...")
                article.voiced_summary = generate_voiced_summary_from_article(article, length)
            
            if not article.timeline_json:
                print("Generating timeline...")
                article.timeline_json = generate_timeline(article.voiced_summary)
            
            db.session.commit()

            timeline = article.timeline_json
            
            # Re-process images every time for now to ensure consistency.
            print("Sourcing and generating raw images...")
            for scene in timeline:
                image_data = source_image_for_scene(scene['description'])
                scene.update(image_data)
                
                raw_path = generate_raw_image(
                    prompt=scene.get('generated_image_prompt', scene['description']),
                    article_id=article.id,
                    scene_number=scene['scene'],
                    is_user_scene=scene.get('is_user_scene', False)
                )
                if raw_path:
                    scene['raw_image_path'] = raw_path

            flag_modified(article, "timeline_json")
            db.session.commit()

            print(f"Stylizing images with theme: '{theme}'...")
            style_prompt = FLUX_THEMES.get(theme)
            for scene in timeline:
                raw_image_path = scene.get('raw_image_path')
                if raw_image_path:
                    stylized_path = apply_style_to_image(
                        image_path_or_url=raw_image_path,
                        style_prompt=style_prompt,
                        article_id=article.id,
                        scene_number=scene['scene']
                    )
                    if stylized_path:
                        scene['stylized_image_path'] = stylized_path
            
            flag_modified(article, "timeline_json")
            db.session.commit()
            print("Image generation and stylization complete.")

            # Step 3: Aggregate final assets
            print("--- Aggregating final assets ---")
            output_dir = os.path.join('instance', 'output', str(article.id))
            os.makedirs(output_dir, exist_ok=True)

            script_path = os.path.join(output_dir, 'script.txt')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(article.voiced_summary)
            print(f"Voiced summary script saved to: {script_path}")

            image_count = 0
            for i, scene in enumerate(timeline):
                stylized_path = scene.get('stylized_image_path')
                if stylized_path and os.path.exists(stylized_path):
                    ext = os.path.splitext(stylized_path)[1]
                    dest_filename = f"{i+1:02d}{ext}"
                    dest_path = os.path.join(output_dir, dest_filename)
                    shutil.copy(stylized_path, dest_path)
                    image_count += 1
            
            print(f"Copied {image_count} stylized images to: {output_dir}")

            print("\n--- Voiced Summary ---")
            print(article.voiced_summary)
            print("----------------------")
            
            print(f"\n--- Pipeline complete for Article {article.id} ---")

        except Exception as e:
            print(f"An error occurred during the pipeline: {e}")
            import traceback
            traceback.print_exc()

    app.cli.add_command(init_db_command)
    app.cli.add_command(fetch_news_command)
    app.cli.add_command(process_articles_command)
    app.cli.add_command(generate_voiced_summary_command)
    app.cli.add_command(generate_voice_response_command)
    app.cli.add_command(generate_timeline_command)
    app.cli.add_command(source_images_command)
    app.cli.add_command(generate_raw_images_command)
    app.cli.add_command(stylize_images_command)
    app.cli.add_command(process_story_command)

    return app

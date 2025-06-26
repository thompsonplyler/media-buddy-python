import sys
import os
import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
import shutil
from pathlib import Path

# Correct the path to allow for absolute imports from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.media_buddy.config import Config
from src.media_buddy.extensions import db, migrate
from src.media_buddy.models import NewsArticle
from src.media_buddy.services.legacy_adapter import fetch_articles
from src.media_buddy.text_processor import generate_summary, generate_embedding, generate_timeline, generate_voiced_summary_from_article, generate_voiced_summary_from_raw_content, generate_voiced_response_from_articles, generate_voiced_summary_from_content
from src.media_buddy.style_learning import style_learner
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
    @click.option('--length', default=175, type=int, help='The target word count for the 60-second script.')
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
            
            print(f"\n💾 Saved Thompson's 60-second script to: {filepath}")
            print("\n--- THOMPSON'S SCRIPT (60 SECONDS) ---")
            print(voice_response)
            print("--- END SCRIPT ---")
            
            # Return the filepath for potential chaining
            return filepath
            
        except Exception as e:
            print(f"❌ Error generating voice response: {e}")
            import traceback
            traceback.print_exc()
            return None

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

    @click.command(name='process-script')
    @click.argument('script_file')
    @click.option('--theme', type=click.Choice(FLUX_THEMES.keys()), help='Optional visual theme for image generation.')
    @with_appcontext
    def process_script_command(script_file, theme):
        """Processes a script file through the timeline and image generation pipeline."""
        
        # Check if file exists
        if not os.path.exists(script_file):
            print(f"❌ Script file not found: {script_file}")
            return
        
        print(f"📄 Processing script file: {script_file}")
        
        try:
            # Read the script content
            with open(script_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract just the script part (between the --- markers)
            script_start = content.find('---\n\n') + 5
            script_end = content.find('\n\n---\n\n', script_start)
            
            if script_start == 4 or script_end == -1:  # markers not found
                print("⚠️  Using entire file content as script")
                script_content = content
            else:
                script_content = content[script_start:script_end].strip()
            
            if len(script_content) < 50:
                print("❌ Script content too short to process")
                return
            
            print(f"📝 Extracted script ({len(script_content)} characters)")
            print(f"🎬 Generating timeline from script...")
            
            # Generate timeline from the script
            timeline = generate_timeline(script_content)
            
            print(f"✅ Generated timeline with {len(timeline)} scenes")
            print("\n--- TIMELINE ---")
            import json
            print(json.dumps(timeline, indent=2))
            print("--- END TIMELINE ---")
            
            # If theme is provided, generate image prompts
            if theme:
                print(f"\n🎨 Processing images with theme: '{theme}'...")
                
                # Add image prompts to each scene
                for scene in timeline:
                    print(f"🖼️  Processing scene {scene['scene']}: {scene['description'][:50]}...")
                    image_data = source_image_for_scene(scene['description'])
                    scene.update(image_data)
                
                print("✅ Image prompts generated for all scenes")
                print("\n--- UPDATED TIMELINE WITH IMAGE PROMPTS ---")
                print(json.dumps(timeline, indent=2))
                print("--- END ---")
            
            # Save the timeline to a JSON file next to the script
            script_dir = os.path.dirname(script_file)
            script_name = os.path.splitext(os.path.basename(script_file))[0]
            timeline_file = os.path.join(script_dir, f"{script_name}-timeline.json")
            
            with open(timeline_file, 'w', encoding='utf-8') as f:
                json.dump(timeline, f, indent=2)
            
            print(f"\n💾 Saved timeline to: {timeline_file}")
            
            if theme:
                print(f"\n🎯 NEXT STEPS:")
                print(f"   Timeline saved with image prompts")
                print(f"   Ready for image generation (not implemented in this test)")
            else:
                print(f"\n🎯 NEXT STEPS:")
                print(f"   Run with --theme to add image prompts")
                print(f"   Available themes: {', '.join(FLUX_THEMES.keys())}")
            
        except Exception as e:
            print(f"❌ Error processing script: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='record-edit')
    @click.argument('original_script_file')
    @click.argument('edited_script_file')
    @click.argument('topic')
    @with_appcontext
    def record_edit_command(original_script_file, edited_script_file, topic):
        """Record an edit session to learn Thompson's style preferences."""
        
        try:
            # Read both scripts
            with open(original_script_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            with open(edited_script_file, 'r', encoding='utf-8') as f:
                edited_content = f.read()
            
            # Extract script content (between --- markers if present)
            def extract_script(content):
                start = content.find('---\n\n') + 5
                end = content.find('\n\n---\n\n', start)
                if start == 4 or end == -1:
                    return content.strip()
                return content[start:end].strip()
            
            original_script = extract_script(original_content)
            edited_script = extract_script(edited_content)
            
            if len(original_script) < 20 or len(edited_script) < 20:
                print("❌ Scripts too short to analyze")
                return
            
            # Record the edit session
            session_id = style_learner.record_edit_session(
                original_script=original_script,
                edited_script=edited_script,
                topic=topic,
                context={
                    "original_file": original_script_file,
                    "edited_file": edited_script_file
                }
            )
            
            print(f"✅ Recorded edit session: {session_id}")
            
            # Show recommendations based on this edit
            recommendations = style_learner.get_style_recommendations(topic, len(original_script.split()))
            
            if recommendations["style_notes"]:
                print(f"\n📚 Style insights:")
                for note in recommendations["style_notes"]:
                    print(f"  • {note}")
            
            if recommendations["common_edits"]:
                print(f"\n🔄 Your common edits:")
                for edit in recommendations["common_edits"]:
                    print(f"  • {edit}")
            
            print(f"\n💡 Suggested length for future '{topic}' scripts: {recommendations['suggested_length']} words")
            
        except Exception as e:
            print(f"❌ Error recording edit: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='style-insights')
    @with_appcontext
    def style_insights_command():
        """Show learned patterns from Thompson's editing history."""
        
        try:
            # Check if we have any learning data
            if not style_learner.edits_file.exists():
                print("📚 No edit history found yet.")
                print("💡 Use 'record-edit' to start building your style profile.")
                return
            
            # Count total edits
            edit_count = 0
            with open(style_learner.edits_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        edit_count += 1
            
            print(f"📊 Style Learning Report")
            print(f"Total edit sessions: {edit_count}")
            
            # Show successful examples
            successful_examples = style_learner.get_successful_examples(3)
            if successful_examples:
                print(f"\n🌟 Recent successful examples:")
                for i, example in enumerate(successful_examples, 1):
                    example_name = Path(example).stem
                    print(f"  {i}. {example_name}")
            
            # Show general recommendations  
            sample_recommendations = style_learner.get_style_recommendations("general", 175)
            
            if sample_recommendations["style_notes"]:
                print(f"\n📝 Your writing tendencies:")
                for note in sample_recommendations["style_notes"]:
                    print(f"  • {note}")
            
            if sample_recommendations["common_edits"]:
                print(f"\n✏️  Your most frequent edits:")
                for edit in sample_recommendations["common_edits"]:
                    print(f"  • {edit}")
            
            print(f"\n💾 Learning data stored in: {style_learner.learning_dir}")
            
        except Exception as e:
            print(f"❌ Error showing insights: {e}")
            import traceback
            traceback.print_exc()

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
            # Step 1: Get the Article using our new service architecture
            if query:
                print(f"Fetching new article for query: '{query}' using {os.getenv('ARTICLE_SERVICE', 'newsapi')} service")
                
                from .services.article_factory import ArticleServiceFactory
                
                # Get articles using our new service architecture
                service = ArticleServiceFactory.create_service()
                articles_data = service.fetch_articles(query, count=5)
                
                if not articles_data:
                    print("❌ No articles found for that query.")
                    return
                
                # Find first new article with substantial content
                new_article_data = None
                for article_obj in articles_data:
                    # Check if already exists in database
                    existing = db.session.query(NewsArticle.id).filter_by(url=article_obj.url).first()
                    if existing:
                        continue
                    
                    # Check if content is substantial (not a snippet or CAPTCHA)
                    content = article_obj.content or ''
                    if len(content) > 1000:  # Require substantial content
                        new_article_data = article_obj
                        break

                if not new_article_data:
                    print("❌ No new articles with substantial content found. All may be snippets, CAPTCHA pages, or already in database.")
                    return

                article = NewsArticle(
                    url=new_article_data.url,
                    title=new_article_data.title,
                    raw_content=new_article_data.content or '',
                )
                db.session.add(article)
                db.session.commit()
                article_id = article.id
                print(f"✅ Successfully fetched and created new article with ID: {article_id}")
                print(f"📄 Content length: {len(article.raw_content)} characters")
            else:
                article = NewsArticle.query.get(article_id)
                if not article:
                    print(f"❌ Error: Article with ID {article_id} not found.")
                    return

            print(f"🚀 Starting processing pipeline for Article {article.id}: {article.title}")

            # Step 2: Skip base summary, go directly to voiced summary with full content
            if not article.voiced_summary:
                print("🎤 Generating voiced summary directly from full article content...")
                # Generate voiced summary directly from raw content (our new way)
                article.voiced_summary = generate_voiced_summary_from_content(article.raw_content, length)
                print(f"✅ Generated {len(article.voiced_summary.split())} word voiced summary")
            
            if not article.timeline_json:
                print("🎬 Generating timeline...")
                article.timeline_json = generate_timeline(article.voiced_summary)
                print(f"✅ Generated timeline with {len(article.timeline_json)} scenes")
            
            db.session.commit()

            timeline = article.timeline_json
            
            # Step 3: Process images
            print("🖼️  Sourcing and generating raw images...")
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

            print(f"🎨 Stylizing images with theme: '{theme}'...")
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
            print("✅ Image generation and stylization complete.")

            # Step 4: Aggregate final assets
            print("📦 Aggregating final assets...")
            output_dir = os.path.join('instance', 'output', str(article.id))
            os.makedirs(output_dir, exist_ok=True)

            script_path = os.path.join(output_dir, 'script.txt')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(article.voiced_summary)
            print(f"💾 Voiced summary script saved to: {script_path}")

            image_count = 0
            for i, scene in enumerate(timeline):
                stylized_path = scene.get('stylized_image_path')
                if stylized_path and os.path.exists(stylized_path):
                    ext = os.path.splitext(stylized_path)[1]
                    dest_filename = f"{i+1:02d}{ext}"
                    dest_path = os.path.join(output_dir, dest_filename)
                    shutil.copy(stylized_path, dest_path)
                    image_count += 1
            
            print(f"🖼️  Copied {image_count} stylized images to: {output_dir}")

            print("\n" + "="*60)
            print("🎯 VOICED SUMMARY")
            print("="*60)
            print(article.voiced_summary)
            print("="*60)
            
            print(f"\n🎉 Pipeline complete for Article {article.id}")

        except Exception as e:
            print(f"❌ An error occurred during the pipeline: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='create-video')
    @click.option('--article-id', type=int, help='The ID of the article to create video for.')
    @click.option('--output-dir', type=str, help='Directory containing vo.mp3 and images (overrides article-id).')
    @click.option('--output-filename', default='video_out.mp4', help='Name of output video file.')
    @with_appcontext
    def create_video_command(article_id, output_dir, output_filename):
        """Create video from images and voiceover using FFmpeg with H.264 codec."""
        from .services.video_service import VideoService
        
        try:
            # Determine output directory
            if output_dir:
                target_dir = output_dir
            elif article_id:
                target_dir = os.path.join('instance', 'output', str(article_id))
            else:
                print("❌ Error: You must provide either --article-id or --output-dir.")
                return
            
            if not os.path.exists(target_dir):
                print(f"❌ Error: Directory not found: {target_dir}")
                return
            
            print(f"🎬 Creating video from directory: {target_dir}")
            
            # Initialize video service
            video_service = VideoService()
            
            # Create the video
            video_path = video_service.create_video(target_dir, output_filename)
            
            # Get video info for confirmation
            video_info = video_service.get_video_info(video_path)
            
            print(f"✅ Video created successfully!")
            print(f"📁 Location: {video_path}")
            print(f"⏱️  Duration: {video_info.get('duration', 'Unknown'):.2f} seconds")
            print(f"📐 Resolution: {video_info.get('width', 'Unknown')}x{video_info.get('height', 'Unknown')}")
            print(f"🎥 Codec: {video_info.get('codec', 'Unknown')}")
            print(f"📦 Size: {video_info.get('size_bytes', 0) / (1024*1024):.1f} MB")
            
        except Exception as e:
            print(f"❌ Video creation failed: {e}")
            import traceback
            traceback.print_exc()

    app.cli.add_command(init_db_command)
    app.cli.add_command(fetch_news_command)
    app.cli.add_command(process_articles_command)
    app.cli.add_command(generate_voiced_summary_command)
    app.cli.add_command(generate_voice_response_command)
    app.cli.add_command(process_script_command)
    app.cli.add_command(record_edit_command)
    app.cli.add_command(style_insights_command)
    app.cli.add_command(generate_timeline_command)
    app.cli.add_command(source_images_command)
    app.cli.add_command(generate_raw_images_command)
    app.cli.add_command(stylize_images_command)
    app.cli.add_command(process_story_command)
    app.cli.add_command(create_video_command)

    return app

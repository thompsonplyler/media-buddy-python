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
from src.media_buddy.services.video_compositor import VideoCompositor
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

    # Initialize services
    from src.media_buddy.services.pipeline_orchestrator import PipelineOrchestrator
    orchestrator = PipelineOrchestrator()

    # =============================================================================
    # STREAMLINED TURNKEY WORKFLOW COMMANDS
    # =============================================================================

    @click.command(name='story-create')
    @click.option('--story-file', required=True, type=str, help='Path to file containing your preliminary story.')
    @click.option('--news-query', required=True, type=str, help='News search query to supplement your story.')
    @click.option('--title', type=str, help='Optional title for the story (defaults to filename).')
    @with_appcontext
    def story_create_command(story_file, news_query, title):
        """Step 1: Create story from user input + 3 reliable news articles."""
        from .services.article_factory import ArticleServiceFactory
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        import datetime
        
        try:
            # Read user story
            if not os.path.exists(story_file):
                print(f"❌ Story file not found: {story_file}")
                return
            
            with open(story_file, 'r', encoding='utf-8') as f:
                user_story = f.read().strip()
            
            if not user_story:
                print(f"❌ Story file is empty: {story_file}")
                return
            
            # Generate title if not provided
            if not title:
                title = f"Story: {os.path.splitext(os.path.basename(story_file))[0]}"
            
            print(f"📖 Creating story: {title}")
            print(f"📄 User story: {len(user_story)} characters")
            print(f"🔍 News query: '{news_query}'")
            print("=" * 80)
            
            # Fetch exactly 3 articles, prioritizing reliability
            print("📡 Fetching 3 reliable news articles...")
            service = ArticleServiceFactory.create_service()
            articles_data = service.fetch_articles(news_query, count=10)  # Get more to filter
            
            if not articles_data:
                print(f"❌ No articles found for query: '{news_query}'")
                return
            
            # Filter and rank by reliability/content quality
            quality_articles = []
            for article_obj in articles_data:
                content = article_obj.content or ''
                if len(content) > 500:  # Only substantial articles
                    quality_articles.append(article_obj)
            
            if len(quality_articles) < 3:
                print(f"❌ Found only {len(quality_articles)} quality articles. Need at least 3.")
                print("💡 Try a broader news query or use archive enhancement.")
                return
            
            # Take top 3 by content length (proxy for quality)
            selected_articles = sorted(quality_articles, key=lambda a: len(a.content or ''), reverse=True)[:3]
            
            # Combine all article content
            combined_news = "\n\n".join([
                f"**Article {i+1}: {article.title}**\n{article.content}"
                for i, article in enumerate(selected_articles)
            ])
            
            # Create database entry
            article = NewsArticle(
                title=title,
                url=f"story://created_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
                raw_content=combined_news,  # Store news articles in raw_content
                user_contribution=user_story,  # Store user story in contribution
                workflow_phase=WorkflowPhase.AI_ENHANCEMENT.value  # Skip to enhancement
            )
            
            db.session.add(article)
            db.session.commit()
            
            # Initialize workflow
            orchestrator.initialize_workflow(article.id, {'source': 'story-workflow'})
            state = orchestrator.get_workflow_state(article.id)
            state.current_phase = WorkflowPhase.AI_ENHANCEMENT
            state.phases_completed = [WorkflowPhase.DISCOVERY, WorkflowPhase.USER_CONTRIBUTION]
            
            print("✅ Story created successfully!")
            print(f"📰 Article ID: {article.id}")
            print(f"📄 User story: {len(user_story)} characters")
            print(f"📊 News articles: {len(selected_articles)} articles, {len(combined_news)} total characters")
            print(f"📑 Sources: {', '.join([a.source or 'Unknown' for a in selected_articles])}")
            print("\n🎯 NEXT STEP:")
            print(f"   flask script-generate --article-id {article.id}")
            
        except Exception as e:
            print(f"❌ Error creating story: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='script-generate')
    @click.option('--article-id', required=True, type=int, help='Article ID to generate script for.')
    @click.option('--length', default=200, type=int, help='Target word count for final script.')
    @with_appcontext
    def script_generate_command(article_id, length):
        """Step 2: Generate AI script + timeline with duration estimates."""
        from .text_processor import generate_voiced_story_from_user_and_news, generate_timeline
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            if not article.user_contribution:
                print(f"❌ Article {article_id} has no user story. Use 'story-create' first.")
                return
            
            print(f"🎬 Generating script for: {article.title}")
            print("=" * 80)
            
            # Generate enhanced script combining user story + news
            print("🤖 Generating AI-enhanced script...")
            enhanced_content = generate_voiced_story_from_user_and_news(
                user_story=article.user_contribution,
                news_content=article.raw_content,
                length=length
            )
            
            if not enhanced_content:
                print("❌ Failed to generate enhanced script.")
                return
            
            # Generate timeline with text + descriptions
            print("📋 Generating timeline with duration estimates...")
            timeline = generate_timeline(enhanced_content)
            
            if not timeline:
                print("❌ Failed to generate timeline.")
                return
            
            # Add duration estimates (average 150 words per minute)
            words_per_minute = 150
            total_duration = 0
            
            for scene in timeline:
                scene_text = scene.get('text', '')
                word_count = len(scene_text.split())
                duration = (word_count / words_per_minute) * 60  # Convert to seconds
                scene['duration_seconds'] = round(duration, 1)
                scene['word_count'] = word_count
                total_duration += duration
            
            # Save to database
            article.enhanced_content = enhanced_content
            article.timeline_json = timeline
            article.workflow_phase = WorkflowPhase.TIMELINE_GENERATION.value
            db.session.commit()
            
            # Update workflow
            orchestrator.advance_workflow(article_id, WorkflowPhase.TIMELINE_GENERATION)
            
            print("✅ Script and timeline generated successfully!")
            print(f"📄 Final script: {len(enhanced_content.split())} words")
            print(f"⏱️  Estimated duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
            print(f"🎬 Timeline scenes: {len(timeline)}")
            print()
            
            # Show script preview
            print("📖 SCRIPT PREVIEW:")
            print("-" * 60)
            print(enhanced_content[:500] + "..." if len(enhanced_content) > 500 else enhanced_content)
            print("-" * 60)
            
            # Show timeline summary
            print("\n📋 TIMELINE SUMMARY:")
            print("-" * 60)
            for i, scene in enumerate(timeline[:5], 1):  # Show first 5 scenes
                print(f"Scene {scene['scene']}: {scene['word_count']} words ({scene['duration_seconds']}s)")
                print(f"  Text: {scene['text'][:80]}...")
                print(f"  Visual: {scene['description'][:80]}...")
                print()
            
            if len(timeline) > 5:
                print(f"... and {len(timeline) - 5} more scenes")
            
            print("\n🎯 NEXT STEP:")
            print(f"   flask timeline-approve --article-id {article_id} --theme [theme_name]")
            
        except Exception as e:
            print(f"❌ Error generating script: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='timeline-approve')
    @click.option('--article-id', required=True, type=int, help='Article ID to approve timeline for.')
    @click.option('--theme', required=True, type=click.Choice(FLUX_THEMES.keys()), help='Visual theme for image generation.')
    @click.option('--preview-only', is_flag=True, help='Show timeline without generating images.')
    @with_appcontext
    def timeline_approve_command(article_id, theme, preview_only):
        """Step 3: Approve timeline and generate images."""
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        from .image_scout import generate_raw_image, apply_style_to_image
        from .themes import FLUX_THEMES
        from sqlalchemy.orm.attributes import flag_modified
        import json
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            if not article.timeline_json:
                print(f"❌ Article {article_id} has no timeline. Run 'script-generate' first.")
                return
            
            timeline = article.timeline_json
            
            print(f"📋 Timeline Approval for: {article.title}")
            print("=" * 80)
            
            # Calculate total duration
            total_duration = sum(scene.get('duration_seconds', 0) for scene in timeline)
            total_words = sum(scene.get('word_count', 0) for scene in timeline)
            
            print(f"📊 Timeline Statistics:")
            print(f"   🎬 Total scenes: {len(timeline)}")
            print(f"   📝 Total words: {total_words}")
            print(f"   ⏱️  Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
            print(f"   🎨 Theme: {theme}")
            print()
            
            # Show complete timeline
            print("📋 COMPLETE TIMELINE:")
            print("=" * 80)
            for scene in timeline:
                print(f"🎬 Scene {scene['scene']} ({scene.get('duration_seconds', 0)}s)")
                print(f"   📝 Text: {scene['text']}")
                print(f"   🖼️  Visual: {scene['description']}")
                print(f"   👤 User scene: {'Yes' if scene.get('is_user_scene') else 'No'}")
                print()
            
            if preview_only:
                print("👁️  Preview mode - no images generated.")
                print(f"\n🎯 To generate images, run:")
                print(f"   flask timeline-approve --article-id {article_id} --theme {theme}")
                return
            
            # Generate images
            print("🎨 Generating images...")
            print("-" * 60)
            
            # Generate raw images using existing modular interface
            raw_image_count = 0
            style_prompt = FLUX_THEMES.get(theme)
            
            # Generate raw images for scenes that need them
            scenes_to_process = [s for s in timeline if not s.get('raw_image_path')]
            for scene in scenes_to_process:
                scene_number = scene['scene']
                description = scene.get('description', '')
                
                if description:
                    raw_path = generate_raw_image(
                        prompt=description,
                        article_id=article_id,
                        scene_number=scene_number,
                        is_user_scene=scene.get('is_user_scene', False)
                    )
                    
                    if raw_path:
                        scene['raw_image_path'] = raw_path
                        raw_image_count += 1
                        print(f"✅ Generated raw image for scene {scene_number}")
                    else:
                        print(f"❌ Failed to generate raw image for scene {scene_number}")
            
            print(f"✅ Generated {raw_image_count} raw images")
            
            # Apply theme styling using existing modular interface
            styled_count = 0
            scenes_to_stylize = [s for s in timeline if s.get('raw_image_path') and not s.get('stylized_image_path')]
            
            for scene in scenes_to_stylize:
                scene_number = scene['scene']
                raw_image_path = scene.get('raw_image_path')
                
                if raw_image_path and os.path.exists(raw_image_path):
                    styled_path = apply_style_to_image(
                        image_path_or_url=raw_image_path,
                        style_prompt=style_prompt,
                        article_id=article_id,
                        scene_number=scene_number
                    )
                    
                    if styled_path:
                        scene['stylized_image_path'] = styled_path
                        styled_count += 1
                        print(f"✅ Styled image for scene {scene_number}")
                    else:
                        print(f"❌ Failed to style image for scene {scene_number}")
            
            # Mark timeline as modified for SQLAlchemy
            flag_modified(article, "timeline_json")
            
            # Update timeline with image paths
            article.timeline_json = timeline
            article.workflow_phase = WorkflowPhase.FINAL_ASSEMBLY.value
            db.session.commit()
            
            # Update workflow
            orchestrator.advance_workflow(article_id, WorkflowPhase.IMAGE_PROCESSING)
            orchestrator.advance_workflow(article_id, WorkflowPhase.FINAL_ASSEMBLY)
            
            # Save script text to file alongside images
            text_output_dir = f"instance/text/{article_id}"
            os.makedirs(text_output_dir, exist_ok=True)
            
            # Create full script file
            script_path = os.path.join(text_output_dir, 'full_script.txt')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(f"# {article.title}\n")
                f.write(f"# Generated: {article.url.replace('story://created_', '').replace('_', ' ')}\n")
                f.write(f"# Total Duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)\n\n")
                f.write("="*80 + "\n")
                f.write("FULL SCRIPT\n")
                f.write("="*80 + "\n\n")
                f.write(article.enhanced_content)
            
            # Create scene-by-scene script file  
            scene_script_path = os.path.join(text_output_dir, 'scene_by_scene.txt')
            with open(scene_script_path, 'w', encoding='utf-8') as f:
                f.write(f"# {article.title} - Scene by Scene\n")
                f.write(f"# Generated: {article.url.replace('story://created_', '').replace('_', ' ')}\n")
                f.write(f"# Total Duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)\n\n")
                
                for scene in timeline:
                    f.write(f"{'='*60}\n")
                    f.write(f"SCENE {scene['scene']} ({scene.get('duration_seconds', 0)}s)\n")
                    f.write(f"{'='*60}\n")
                    f.write(f"TEXT TO SPEAK:\n{scene['text']}\n\n")
                    f.write(f"VISUAL DESCRIPTION:\n{scene['description']}\n\n")
                    f.write(f"USER SCENE: {'Yes' if scene.get('is_user_scene') else 'No'}\n\n")
            
            print(f"✅ Images generated and styled!")
            print(f"🎨 Raw images: {raw_image_count}")
            print(f"🎭 Styled images: {styled_count}")
            print(f"📁 Images saved to: instance/images/{article_id}/")
            print(f"📄 Script files saved to: instance/text/{article_id}/")
            print(f"   📝 Full script: {script_path}")
            print(f"   🎬 Scene breakdown: {scene_script_path}")
            
            print("\n🎯 NEXT STEP:")
            print(f"   flask video-compose --article-id {article_id} --video-file \"path/to/your/video.mov\"")
            
        except Exception as e:
            print(f"❌ Error approving timeline: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='video-compose')
    @click.option('--article-id', required=True, type=int, help='Article ID with generated images.')
    @click.option('--video-file', required=True, type=str, help='Path to recorded video file.')
    @click.option('--output-name', default='final_composed_video.mp4', help='Output video filename.')
    @with_appcontext
    def video_compose_command(article_id, video_file, output_name):
        """Step 4: Final video composition with video on top, images on bottom."""
        from .services.video_compositor import VideoCompositor
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            if not article.timeline_json:
                print(f"❌ Article {article_id} has no timeline.")
                return
            
            # Check video file exists
            if not os.path.exists(video_file):
                print(f"❌ Video file not found: {video_file}")
                return
            
            print(f"🎬 Final Video Composition")
            print("=" * 80)
            print(f"📰 Story: {article.title}")
            print(f"🎥 Video: {video_file}")
            print(f"🖼️  Images: instance/images/{article_id}/")
            print(f"📦 Output: {output_name}")
            
            # Setup output directory
            output_dir = f"instance/output/{article_id}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Copy video to output directory
            video_filename = os.path.basename(video_file)
            dest_video = os.path.join(output_dir, video_filename)
            import shutil
            shutil.copy2(video_file, dest_video)
            print(f"📁 Copied video to: {dest_video}")
            
            # Copy and rename images
            timeline = article.timeline_json
            copied_images = 0
            
            for scene in timeline:
                scene_num = scene['scene']
                source_image = f"instance/images/{article_id}/scene_{scene_num}_styled.png"
                if os.path.exists(source_image):
                    dest_image = os.path.join(output_dir, f"{scene_num}.png")
                    shutil.copy2(source_image, dest_image)
                    copied_images += 1
            
            print(f"📁 Copied {copied_images} images")
            
            # Compose video
            print("\n🎬 Creating layered composition...")
            compositor = VideoCompositor()
            
            final_video_path = compositor.create_layered_composition(
                input_dir=output_dir,
                output_filename=output_name,
                target_width=1080,
                target_height=1920
            )
            
            # Get video info
            video_info = compositor.get_video_info(final_video_path)
            file_size = os.path.getsize(final_video_path) / (1024*1024)
            
            print("\n🎉 VIDEO COMPOSITION COMPLETE!")
            print("=" * 80)
            print(f"📁 Final video: {final_video_path}")
            print(f"⏱️  Duration: {video_info.get('duration', 0):.1f} seconds")
            print(f"📐 Resolution: {video_info.get('width')}x{video_info.get('height')}")
            print(f"📦 File size: {file_size:.1f} MB")
            print(f"🎨 Layout: Video on TOP, Images on BOTTOM")
            print(f"🖼️  Images: {copied_images} stylized scenes")
            
        except Exception as e:
            print(f"❌ Error composing video: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='story-status')
    @click.option('--article-id', type=int, help='Show status for specific story.')
    @click.option('--list-all', is_flag=True, help='List all story workflows.')
    @with_appcontext
    def story_status_command(article_id, list_all):
        """Show status of story workflows."""
        try:
            if list_all:
                stories = NewsArticle.query.filter(NewsArticle.url.like('story://%')).all()
                if not stories:
                    print("📭 No story workflows found.")
                    return
                
                print(f"📚 Story Workflows ({len(stories)}):")
                print("="*80)
                for story in stories:
                    phase = story.workflow_phase or 'unknown'
                    print(f"📖 Article {story.id}: {story.title}")
                    print(f"   📍 Phase: {phase}")
                    print(f"   📄 User story: {len(story.user_contribution or '') if story.user_contribution else 0} chars")
                    print(f"   📊 Enhanced: {len(story.enhanced_content or '') if story.enhanced_content else 0} chars")
                    print(f"   🎬 Timeline: {len(story.timeline_json) if story.timeline_json else 0} scenes")
                    print(f"   📅 Created: {story.url.replace('story://created_', '').replace('_', ' ')}")
                    print()
            
            elif article_id:
                article = NewsArticle.query.get(article_id)
                if not article:
                    print(f"❌ Article {article_id} not found.")
                    return
                
                if not article.url.startswith('story://'):
                    print(f"❌ Article {article_id} is not a story workflow.")
                    return
                
                timeline = article.timeline_json or []
                total_duration = sum(scene.get('duration_seconds', 0) for scene in timeline)
                
                print(f"📖 Story Status: {article.title}")
                print("="*60)
                print(f"📍 Current Phase: {article.workflow_phase or 'unknown'}")
                print(f"📄 User Story: {len(article.user_contribution or '')} characters")
                print(f"📊 Enhanced Content: {len(article.enhanced_content or '')} characters")
                print(f"🎬 Timeline Scenes: {len(timeline)}")
                print(f"⏱️  Estimated Duration: {total_duration:.1f}s ({total_duration/60:.1f} min)")
                print(f"📅 Created: {article.url.replace('story://created_', '').replace('_', ' ')}")
                
                # Show next step
                phase = article.workflow_phase
                if phase == 'ai_enhancement':
                    print(f"\n🎯 NEXT STEP: flask script-generate --article-id {article_id}")
                elif phase == 'timeline_generation':
                    print(f"\n🎯 NEXT STEP: flask timeline-approve --article-id {article_id} --theme [theme]")
                elif phase == 'final_assembly':
                    print(f"\n🎯 NEXT STEP: flask video-compose --article-id {article_id} --video-file \"path/to/video.mov\"")
                else:
                    print(f"\n✅ Story workflow complete!")
            
            else:
                print("❌ Specify either --article-id or --list-all")
                
        except Exception as e:
            print(f"❌ Error checking story status: {e}")
            import traceback
            traceback.print_exc()

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

    @click.command(name='test-image')
    @click.option('--prompt', required=True, type=str, help='The prompt to generate an image for.')
    @click.option('--user-scene', is_flag=True, help='Generate as a user scene (uses your custom LoRA model).')
    @with_appcontext
    def test_image_command(prompt, user_scene):
        """Generate a single test image with a custom prompt to test aspect ratio and other settings."""
        import os
        import datetime
        
        print(f"🧪 Testing image generation...")
        print(f"📝 Prompt: '{prompt}'")
        print(f"👤 User scene: {'Yes' if user_scene else 'No'}")
        
        # Create test directory
        test_dir = os.path.join('instance', 'test_images')
        os.makedirs(test_dir, exist_ok=True)
        
        # Generate timestamp for unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        test_filename = f"test_{timestamp}.webp"
        
        # Use a dummy article_id and scene_number for testing
        test_article_id = 999999
        test_scene_number = 1
        
        # Temporarily override the output directory in generate_raw_image
        original_path = generate_raw_image(
            prompt=prompt,
            article_id=test_article_id,
            scene_number=test_scene_number,
            is_user_scene=user_scene
        )
        
        if original_path:
            # Move the generated image to our test directory with better naming
            test_path = os.path.join(test_dir, test_filename)
            if os.path.exists(original_path):
                import shutil
                shutil.move(original_path, test_path)
                
                # Clean up the temporary directory
                temp_dir = os.path.dirname(original_path)
                try:
                    os.rmdir(temp_dir)  # Only removes if empty
                except:
                    pass  # Ignore if not empty
                
                print(f"✅ Test image generated successfully!")
                print(f"📁 Saved to: {test_path}")
                print(f"📊 File size: {os.path.getsize(test_path) / 1024:.1f} KB")
                
                # Try to get image dimensions for verification
                try:
                    from PIL import Image
                    with Image.open(test_path) as img:
                        width, height = img.size
                        aspect_ratio = width / height
                        print(f"📐 Dimensions: {width}x{height}")
                        print(f"📏 Aspect ratio: {aspect_ratio:.3f} ({width}:{height})")
                        
                        # Check if it matches expected 2:3 ratio
                        expected_ratio = 2/3
                        if abs(aspect_ratio - expected_ratio) < 0.01:
                            print("✅ Aspect ratio matches expected 2:3!")
                        else:
                            print(f"⚠️  Aspect ratio differs from expected 2:3 ({expected_ratio:.3f})")
                            
                except ImportError:
                    print("ℹ️  Install Pillow to see image dimensions: pip install Pillow")
                except Exception as e:
                    print(f"⚠️  Could not read image dimensions: {e}")
            else:
                print(f"❌ Generated image file not found at: {original_path}")
        else:
            print("❌ Failed to generate test image. Check logs for details.")

    @click.command(name='test-archive')
    @click.option('--verbose', is_flag=True, help='Enable verbose logging for debugging.')
    @with_appcontext
    def test_archive_command(verbose):
        """Test Archive.is service with the three specific URLs to debug content extraction."""
        import logging
        from .services.article_factory import ArticleServiceFactory
        
        # Set up verbose logging if requested
        if verbose:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                force=True
            )
            print("🔍 Verbose logging enabled")
        else:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s [%(levelname)s]: %(message)s',
                force=True
            )
        
        print("🏛️  Testing Archive.is Service")
        print("=" * 80)
        
        # The three test URLs provided
        test_urls = [
            "https://www.npr.org/2025/06/17/g-s1-73126/senate-republican-tax-spending",
            "https://www.bbc.com/news/articles/c0j76djzgpvo",
            "https://www.npr.org/2025/06/02/g-s1-70017/up-first-newsletter-senate-republicans-trump-bill-boulder-colorado-attack-ukraine-russia"
        ]
        
        print(f"📋 Testing {len(test_urls)} URLs through Archive.is:")
        for i, url in enumerate(test_urls, 1):
            print(f"  {i}. {url}")
        print()
        
        try:
            # Create the archive service
            print("🏗️  Creating Archive.is service...")
            service = ArticleServiceFactory.create_service('archive')
            print(f"✅ Service created: {service.get_service_name()}")
            print()
            
            # Fetch articles through archive.is
            print("🚀 Starting archive extraction process...")
            print("-" * 80)
            
            articles = service.fetch_articles(
                query="test",  # Not used by archive service
                max_articles=len(test_urls),
                urls=test_urls
            )
            
            print("-" * 80)
            print(f"\n📊 ARCHIVE EXTRACTION RESULTS:")
            print("=" * 80)
            
            if articles:
                print(f"✅ Successfully extracted {len(articles)}/{len(test_urls)} articles\n")
                
                for i, article in enumerate(articles, 1):
                    print(f"📰 ARTICLE {i}:")
                    print(f"  📋 Title: {article.title}")
                    print(f"  🔗 URL: {article.url}")
                    print(f"  📺 Source: {article.source}")
                    print(f"  📝 Content: {len(article.content)} characters")
                    print(f"  🔍 Preview: {article.content[:200].replace(chr(10), ' ')}...")
                    print()
                
                # Show success rate
                success_rate = (len(articles) / len(test_urls)) * 100
                print(f"📈 Success Rate: {success_rate:.1f}% ({len(articles)}/{len(test_urls)})")
                
                if len(articles) == len(test_urls):
                    print("🎉 ALL ARTICLES SUCCESSFULLY EXTRACTED!")
                    print("✅ Archive.is service is working correctly for these URLs")
                else:
                    print("⚠️  Some articles failed extraction")
                    failed_count = len(test_urls) - len(articles)
                    print(f"❌ {failed_count} article(s) failed - check logs above for details")
                
                # Provide next steps
                print(f"\n🎯 NEXT STEPS:")
                print("   • These URLs can now be used in the collaborative workflow")
                print("   • Archive.is service can be used as fallback when direct scraping fails")
                print("   • Consider integrating archive fallback into GoogleNewsService")
                
            else:
                print("❌ NO ARTICLES SUCCESSFULLY EXTRACTED")
                print("\nPossible issues:")
                print("  • URLs may not be archived on archive.is")
                print("  • Archive.is may be blocking requests")
                print("  • Content extraction selectors may need adjustment")
                print("  • Network connectivity issues")
                print("\n🔍 Check the verbose logs above for detailed error information")
                
        except Exception as e:
            print(f"❌ CRITICAL ERROR in archive testing: {e}")
            import traceback
            traceback.print_exc()
            print("\n🔧 Debug suggestions:")
            print("  • Check internet connectivity")
            print("  • Verify Playwright is properly installed")
            print("  • Run with --verbose flag for detailed logs")

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

    @click.command(name='compose-video')
    @click.option('--input-dir', required=True, type=str, help='Directory containing video file and images.')
    @click.option('--output-filename', default='composed_video.mp4', help='Name of output video file.')
    @click.option('--width', default=1080, type=int, help='Target width (default: 1080).')
    @click.option('--height', default=1920, type=int, help='Target height (default: 1920).')
    @with_appcontext
    def compose_video_command(input_dir, output_filename, width, height):
        """Create layered video composition with cycling images over base video."""
        try:
            if not os.path.exists(input_dir):
                print(f"❌ Error: Directory not found: {input_dir}")
                return
            
            print(f"🎬 Creating layered video composition from: {input_dir}")
            print(f"📐 Target dimensions: {width}x{height}")
            
            # Initialize video compositor
            compositor = VideoCompositor()
            
            # Create the layered composition
            video_path = compositor.create_layered_composition(
                input_dir=input_dir,
                output_filename=output_filename,
                target_width=width,
                target_height=height
            )
            
            # Get video info for confirmation
            video_info = compositor.get_video_info(video_path)
            
            print(f"✅ Layered video composition created successfully!")
            print(f"📁 Location: {video_path}")
            print(f"⏱️  Duration: {video_info.get('duration', 'Unknown'):.2f} seconds")
            print(f"📐 Resolution: {video_info.get('width', 'Unknown')}x{video_info.get('height', 'Unknown')}")
            print(f"🎥 Codec: {video_info.get('codec', 'Unknown')}")
            print(f"📦 Size: {os.path.getsize(video_path) / (1024*1024):.1f} MB")
            
        except Exception as e:
            print(f"❌ Video composition failed: {e}")
            import traceback
            traceback.print_exc()

    # Collaborative Writing Workflow Commands
    @click.command(name='discover-story')
    @click.argument('query')
    @click.option('--count', default=5, type=int, help='Number of articles to fetch.')
    @with_appcontext
    def discover_story_command(query, count):
        """Phase 1: Discover and present articles for user selection."""
        from .services.article_factory import ArticleServiceFactory
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            print(f"🔍 Discovering articles for: '{query}' using {os.getenv('ARTICLE_SERVICE', 'newsapi')} service")
            
            # Get articles using service architecture
            service = ArticleServiceFactory.create_service()
            articles_data = service.fetch_articles(query, count=count)
            
            if not articles_data:
                print("❌ No articles found for that query.")
                return
            
            print(f"📰 Found {len(articles_data)} articles:")
            print("=" * 80)
            
            # Present articles for selection
            quality_articles = []
            for i, article_obj in enumerate(articles_data, 1):
                # Check if already exists in database
                existing = db.session.query(NewsArticle.id).filter_by(url=article_obj.url).first()
                if existing:
                    print(f"{i}. [EXISTS] {article_obj.title}")
                    continue
                
                # Check content quality
                content = article_obj.content or ''
                content_quality = "🟢 FULL" if len(content) > 1000 else "🟡 SNIPPET" if len(content) > 200 else "🔴 MINIMAL"
                
                print(f"{i}. {content_quality} ({len(content)} chars)")
                print(f"   📰 {article_obj.title}")
                print(f"   🔗 {article_obj.url}")
                print()
                
                if len(content) > 1000:
                    quality_articles.append((i, article_obj))
            
            if not quality_articles:
                print("❌ No articles with substantial content found. All may be snippets or already in database.")
                return
            
            print("=" * 80)
            print(f"✅ Found {len(quality_articles)} articles with substantial content ready for collaborative writing.")
            print("\n🎯 NEXT STEPS:")
            print("   1. Choose an article number and run:")
            print("      flask create-article --article-number N --query \"your query\"")
            print("   2. Or run the automated selection:")
            print("      flask create-article --auto --query \"your query\"")
            
        except Exception as e:
            print(f"❌ Error discovering articles: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='archive-enhance')
    @click.argument('query')
    @click.option('--count', default=3, type=int, help='Number of top snippet articles to enhance via Archive.is.')
    @click.option('--verbose', is_flag=True, help='Enable verbose logging.')
    @with_appcontext
    def archive_enhance_command(query, count, verbose):
        """Phase 1b: Enhance snippet articles with full content from Archive.is."""
        from .services.article_factory import ArticleServiceFactory
        import logging
        
        # Set up logging
        if verbose:
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s]: %(message)s', force=True)
        else:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s', force=True)
        
        try:
            print(f"🏛️  Archive Enhancement for: '{query}'")
            print("=" * 80)
            
            # First, get the articles from regular discovery
            print("📡 Step 1: Getting articles from discovery...")
            service = ArticleServiceFactory.create_service()
            articles_data = service.fetch_articles(query, count=10)
            
            if not articles_data:
                print("❌ No articles found for that query.")
                return
            
            # Filter to snippet articles (reliable sources, but insufficient content)
            snippet_articles = []
            print(f"\n🔍 Step 2: Filtering for snippet articles to enhance...")
            
            for i, article_obj in enumerate(articles_data, 1):
                # Check if already exists in database
                existing = db.session.query(NewsArticle.id).filter_by(url=article_obj.url).first()
                if existing:
                    continue
                
                content = article_obj.content or ''
                content_length = len(content)
                
                # Target snippet articles (200-1000 chars) from reliable sources
                if 200 <= content_length <= 1000:
                    snippet_articles.append(article_obj)
                    source_name = article_obj.source or "Unknown"
                    print(f"  {len(snippet_articles)}. {source_name}: {article_obj.title}")
                    print(f"     🔗 {article_obj.url}")
                    print(f"     📄 Current: {content_length} chars (snippet)")
                    print()
            
            if not snippet_articles:
                print("❌ No snippet articles found to enhance.")
                print("💡 Either articles are already full-length or too short to be useful.")
                return
            
            # Limit to requested count
            snippet_articles = snippet_articles[:count]
            urls_to_enhance = [article.url for article in snippet_articles]
            
            print(f"🎯 Step 3: Archive enhancement for {len(urls_to_enhance)} URLs...")
            print("-" * 80)
            
            # Use Archive service to get full content
            archive_service = ArticleServiceFactory.create_service('archive')
            enhanced_articles = archive_service.fetch_articles(
                query="archive_enhance",  # Not used by archive service
                max_articles=count,
                urls=urls_to_enhance
            )
            
            print("-" * 80)
            print(f"\n📊 ARCHIVE ENHANCEMENT RESULTS:")
            print("=" * 80)
            
            if enhanced_articles:
                print(f"✅ Successfully enhanced {len(enhanced_articles)}/{len(urls_to_enhance)} articles\n")
                
                # Update original articles with enhanced content
                enhanced_lookup = {article.url: article for article in enhanced_articles}
                final_articles = []
                
                for original_article in snippet_articles:
                    if original_article.url in enhanced_lookup:
                        enhanced = enhanced_lookup[original_article.url]
                        # Update original with enhanced content but keep other metadata
                        original_article.content = enhanced.content
                        final_articles.append(original_article)
                        print(f"✅ Enhanced: {original_article.title}")
                        print(f"   📄 {len(enhanced.content)} characters (was {len(original_article.content or '')})")
                        print(f"   🔍 Preview: {enhanced.content[:150].replace(chr(10), ' ')}...")
                        print()
                    else:
                        print(f"❌ Failed: {original_article.title}")
                        print(f"   🔗 {original_article.url}")
                        print()
                
                if final_articles:
                    print(f"🎉 SUCCESS: {len(final_articles)} articles ready for collaborative writing!")
                    print("\n🎯 NEXT STEPS:")
                    print("   1. Choose an article and run:")
                    print("      flask create-article --auto --query \"your query\"")
                    print("   2. The enhanced articles are now available for selection")
                    print("   3. Continue with your collaborative workflow")
                    
                    # Store enhanced articles temporarily (in production, we'd cache these)
                    print(f"\n📋 Enhanced articles available for create-article command:")
                    for i, article in enumerate(final_articles, 1):
                        print(f"   {i}. {article.title} ({len(article.content)} chars)")
                else:
                    print("❌ No articles successfully enhanced")
                    
            else:
                print("❌ Archive enhancement failed for all articles")
                print("\n🔧 Possible issues:")
                print("  • URLs may not be archived")
                print("  • Archive services may be blocking requests")
                print("  • Network connectivity issues")
                print(f"\n💡 Try running with --verbose for detailed logs")
                
        except Exception as e:
            print(f"❌ Error in archive enhancement: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='create-article')
    @click.option('--query', required=True, type=str, help='The original query used for discovery.')
    @click.option('--article-number', type=int, help='Specific article number to create from discovery.')
    @click.option('--auto', is_flag=True, help='Automatically select the first quality article.')
    @click.option('--use-archive', is_flag=True, help='Automatically use Archive.is if no full articles found.')
    @with_appcontext
    def create_article_command(query, article_number, auto, use_archive):
        """Phase 1b: Create article from discovery and initialize workflow."""
        from .services.article_factory import ArticleServiceFactory
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Re-fetch articles (in production, we'd cache this)
            service = ArticleServiceFactory.create_service()
            articles_data = service.fetch_articles(query, count=10)
            
            if not articles_data:
                print("❌ No articles found. Run discover-story first.")
                return
            
            # Select article - try full articles first, then archive enhancement if needed
            selected_article = None
            
            # Step 1: Look for full articles (>1000 chars)
            quality_articles = []
            for article_obj in articles_data:
                existing = db.session.query(NewsArticle.id).filter_by(url=article_obj.url).first()
                if existing:
                    continue
                content = article_obj.content or ''
                if len(content) > 1000:
                    quality_articles.append(article_obj)
            
            # Step 2: If we have full articles, select from them
            if quality_articles:
                if auto:
                    selected_article = quality_articles[0]
                elif article_number:
                    if 1 <= article_number <= len(quality_articles):
                        selected_article = quality_articles[article_number - 1]
                    else:
                        print(f"❌ Invalid article number. Choose between 1 and {len(quality_articles)}")
                        return
                else:
                    print("❌ Specify either --article-number or --auto")
                    return
                    
                print(f"✅ Using full article: {selected_article.title}")
                
            # Step 3: If no full articles, try archive enhancement (if enabled)
            elif use_archive:
                print("📰 No full articles found. Trying Archive.is enhancement...")
                
                # Get snippet articles for archive enhancement
                snippet_articles = []
                for article_obj in articles_data:
                    existing = db.session.query(NewsArticle.id).filter_by(url=article_obj.url).first()
                    if existing:
                        continue
                    content = article_obj.content or ''
                    if 200 <= len(content) <= 1000:  # Snippet range
                        snippet_articles.append(article_obj)
                
                if not snippet_articles:
                    print("❌ No snippet articles available for archive enhancement.")
                    return
                
                # Use Archive service
                try:
                    archive_service = ArticleServiceFactory.create_service('archive')
                    urls_to_enhance = [article.url for article in snippet_articles[:3]]
                    
                    print(f"🏛️  Trying Archive.is for {len(urls_to_enhance)} URLs...")
                    enhanced_articles = archive_service.fetch_articles(
                        query="archive_enhance",
                        max_articles=3,
                        urls=urls_to_enhance
                    )
                    
                    if enhanced_articles:
                        selected_article = enhanced_articles[0]
                        print(f"✅ Archive.is success: {selected_article.title}")
                        print(f"📄 Content length: {len(selected_article.content)} characters")
                    else:
                        print("❌ Archive.is enhancement failed for all articles.")
                        return
                        
                except Exception as e:
                    print(f"❌ Archive enhancement error: {e}")
                    return
                    
            # Step 4: No articles available
            else:
                print("❌ No quality articles available.")
                print("💡 Try running with --use-archive to attempt Archive.is enhancement")
                return
            
            # Create article in database
            article = NewsArticle(
                url=selected_article.url,
                title=selected_article.title,
                raw_content=selected_article.content or '',
                workflow_phase='discovery'
            )
            db.session.add(article)
            db.session.commit()
            
            # Initialize workflow
            orchestrator.initialize_workflow(article.id, {'query': query})
            
            print(f"✅ Created Article {article.id}: {article.title}")
            print(f"📄 Content length: {len(article.raw_content)} characters")
            print(f"🔄 Workflow initialized in discovery phase")
            print(f"\n🎯 NEXT STEP:")
            print(f"   flask contribute-take --article-id {article.id}")
            
        except Exception as e:
            print(f"❌ Error creating article: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='contribute-take')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to contribute to.')
    @click.option('--input-file', type=str, help='File containing your contribution (optional).')
    @with_appcontext
    def contribute_take_command(article_id, input_file):
        """Phase 2: Add your perspective/take on the story."""
        from .services.collaborative_writing_service import CollaborativeWritingService
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            # Check workflow state
            if not orchestrator.can_execute_phase(article_id, WorkflowPhase.USER_CONTRIBUTION):
                print(f"❌ Cannot add contribution at this time. Current phase: {article.workflow_phase}")
                return
            
            writing_service = CollaborativeWritingService()
            
            # Check if contribution already exists
            existing_contribution = writing_service.load_contribution(article_id)
            if existing_contribution:
                print(f"📝 Existing contribution found:")
                print("=" * 60)
                print(existing_contribution)
                print("=" * 60)
                print(f"\n🎯 NEXT STEP:")
                print(f"   flask enhance-writing --article-id {article_id}")
                return
            
            # Handle input from file or prompt for contribution
            if input_file:
                if not os.path.exists(input_file):
                    print(f"❌ Input file not found: {input_file}")
                    return
                
                with open(input_file, 'r', encoding='utf-8') as f:
                    user_contribution = f.read().strip()
                print(f"📄 Loaded contribution from: {input_file}")
            else:
                # Create prompt template
                prompt_template = writing_service.create_user_contribution_prompt(
                    article.raw_content, article.title
                )
                
                # Save prompt to temp file for user editing
                temp_dir = os.path.join('private', 'writing_style_samples', 'input', str(article_id))
                os.makedirs(temp_dir, exist_ok=True)
                prompt_file = os.path.join(temp_dir, 'contribution_prompt.md')
                
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(prompt_template)
                
                print(f"📝 Contribution prompt created: {prompt_file}")
                print(f"\n🎯 NEXT STEPS:")
                print(f"   1. Edit the file above with your perspective")
                print(f"   2. Run: flask contribute-take --article-id {article_id} --input-file \"{prompt_file}\"")
                return
            
            if len(user_contribution.strip()) < 20:
                print("❌ Contribution too short. Please provide more substantial content.")
                return
            
            # Save contribution
            contrib_path = writing_service.save_contribution(article_id, user_contribution)
            
            # Update article and workflow
            article.user_contribution = user_contribution
            article.workflow_phase = 'user_contribution'
            db.session.commit()
            
            orchestrator.advance_workflow(article_id, WorkflowPhase.USER_CONTRIBUTION)
            
            print(f"✅ Your contribution saved!")
            print(f"💾 Location: {contrib_path}")
            print(f"📊 Length: {len(user_contribution.split())} words")
            print(f"\n🎯 NEXT STEP:")
            print(f"   flask enhance-writing --article-id {article_id}")
            
        except Exception as e:
            print(f"❌ Error adding contribution: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='enhance-writing')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to enhance.')
    @click.option('--length', default=200, type=int, help='Target word count for enhanced version.')
    @with_appcontext
    def enhance_writing_command(article_id, length):
        """Phase 3: AI enhance user's contribution while preserving their voice."""
        from .services.collaborative_writing_service import CollaborativeWritingService
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            if not article.user_contribution:
                print(f"❌ No user contribution found. Run contribute-take first.")
                return
            
            # Check workflow state
            if not orchestrator.can_execute_phase(article_id, WorkflowPhase.AI_ENHANCEMENT):
                print(f"❌ Cannot enhance at this time. Current phase: {article.workflow_phase}")
                return
            
            writing_service = CollaborativeWritingService()
            
            print(f"🤖 Enhancing your contribution while preserving your voice...")
            print(f"📝 Original: {len(article.user_contribution.split())} words")
            print(f"🎯 Target: {length} words")
            
            # Get style context for consistency
            style_context = writing_service.get_style_context()
            if style_context:
                print(f"📚 Using style context from previous writings")
            
            # Enhance the contribution
            enhanced_content = writing_service.enhance_user_contribution(
                user_contribution=article.user_contribution,
                original_article=article.raw_content,
                target_length=length,
                style_context=style_context
            )
            
            # Save enhanced content
            article.enhanced_content = enhanced_content
            article.workflow_phase = 'ai_enhancement'
            db.session.commit()
            
            orchestrator.advance_workflow(article_id, WorkflowPhase.AI_ENHANCEMENT)
            
            print(f"✅ Enhancement complete!")
            print(f"📈 Enhanced: {len(enhanced_content.split())} words")
            print(f"\n" + "=" * 80)
            print("🎯 ENHANCED CONTENT")
            print("=" * 80)
            print(enhanced_content)
            print("=" * 80)
            
            print(f"\n🎯 NEXT STEP:")
            print(f"   flask process-visuals --article-id {article_id} --theme [theme_name]")
            
        except Exception as e:
            print(f"❌ Error enhancing writing: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='generate-enhanced-timeline')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to generate timeline for.')
    @with_appcontext
    def generate_enhanced_timeline_command(article_id):
        """Generate timeline from enhanced content (stops before image generation)."""
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            if not article.enhanced_content:
                print(f"❌ No enhanced content found. Run enhance-writing first.")
                return
            
            # Check workflow state
            if not orchestrator.can_execute_phase(article_id, WorkflowPhase.TIMELINE_GENERATION):
                print(f"❌ Cannot generate timeline at this time. Current phase: {article.workflow_phase}")
                return
            
            print(f"🎬 Generating timeline from enhanced content...")
            print(f"📝 Content length: {len(article.enhanced_content.split())} words")
            
            # Generate timeline from enhanced content
            timeline = generate_timeline(article.enhanced_content)
            
            # Save timeline
            article.timeline_json = timeline
            article.workflow_phase = 'timeline_ready'
            db.session.commit()
            
            orchestrator.advance_workflow(article_id, WorkflowPhase.TIMELINE_GENERATION)
            
            print(f"✅ Timeline generated successfully!")
            print(f"🎬 Generated {len(timeline)} scenes")
            
            # Display the timeline
            print("\n" + "="*80)
            print("🎬 GENERATED TIMELINE")
            print("="*80)
            import json
            for i, scene in enumerate(timeline, 1):
                print(f"Scene {i}: {scene.get('description', 'No description')}")
            print("="*80)
            
            # Show detailed JSON if verbose
            print(f"\n📋 Full Timeline JSON:")
            print(json.dumps(timeline, indent=2))
            
            print(f"\n🎯 NEXT STEPS:")
            print(f"   Timeline ready for image generation")
            print(f"   • To generate images: flask process-visuals --article-id {article_id} --theme [theme]")
            print(f"   • To check status: flask workflow-status --article-id {article_id}")
            print(f"   • Available themes: {', '.join(FLUX_THEMES.keys())}")
            
        except Exception as e:
            print(f"❌ Error generating timeline: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='process-visuals')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to process visuals for.')
    @click.option('--theme', required=True, type=click.Choice(FLUX_THEMES.keys()), help='Visual theme for images.')
    @with_appcontext
    def process_visuals_command(article_id, theme):
        """Phase 4: Generate timeline and process images from enhanced content."""
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            if not article.enhanced_content:
                print(f"❌ No enhanced content found. Run enhance-writing first.")
                return
            
            # Check workflow state
            if not orchestrator.can_execute_phase(article_id, WorkflowPhase.TIMELINE_GENERATION):
                print(f"❌ Cannot process visuals at this time. Current phase: {article.workflow_phase}")
                return
            
            print(f"🎬 Processing visuals for enhanced content...")
            
            # Generate timeline from enhanced content
            if not article.timeline_json:
                print("🎬 Generating timeline from enhanced content...")
                article.timeline_json = generate_timeline(article.enhanced_content)
                print(f"✅ Generated timeline with {len(article.timeline_json)} scenes")
                orchestrator.advance_workflow(article_id, WorkflowPhase.TIMELINE_GENERATION)
            
            # Set voiced_summary to enhanced_content for compatibility with existing pipeline
            article.voiced_summary = article.enhanced_content
            article.workflow_phase = 'image_processing'
            db.session.commit()
            
            timeline = article.timeline_json
            
            # Process images (same as existing pipeline)
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
            
            orchestrator.advance_workflow(article_id, WorkflowPhase.IMAGE_PROCESSING)
            
            print("✅ Image generation and stylization complete.")
            
            print(f"\n🎯 NEXT STEP:")
            print(f"   flask assemble-final --article-id {article_id}")
            
        except Exception as e:
            print(f"❌ Error processing visuals: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='assemble-final')
    @click.option('--article-id', required=True, type=int, help='The ID of the article to assemble final assets for.')
    @with_appcontext
    def assemble_final_command(article_id):
        """Phase 5: Assemble final assets and complete workflow."""
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Get article
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            # Check workflow state
            if not orchestrator.can_execute_phase(article_id, WorkflowPhase.FINAL_ASSEMBLY):
                print(f"❌ Cannot assemble final assets at this time. Current phase: {article.workflow_phase}")
                return
            
            print("📦 Assembling final assets...")
            
            # Create output directory
            output_dir = os.path.join('instance', 'output', str(article.id))
            os.makedirs(output_dir, exist_ok=True)

            # Save enhanced script
            script_path = os.path.join(output_dir, 'enhanced_script.txt')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(article.enhanced_content)
            print(f"💾 Enhanced script saved to: {script_path}")
            
            # Save original contribution for reference
            original_path = os.path.join(output_dir, 'original_contribution.txt')
            with open(original_path, 'w', encoding='utf-8') as f:
                f.write(article.user_contribution)
            print(f"💾 Original contribution saved to: {original_path}")

            # Copy stylized images
            timeline = article.timeline_json or []
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
            
            # Update workflow
            article.workflow_phase = 'complete'
            db.session.commit()
            
            orchestrator.advance_workflow(article_id, WorkflowPhase.FINAL_ASSEMBLY)
            orchestrator.advance_workflow(article_id, WorkflowPhase.COMPLETE)
            
            # Show summary
            workflow_summary = orchestrator.get_workflow_summary(article_id)
            
            print("\n" + "="*80)
            print("🎉 COLLABORATIVE WORKFLOW COMPLETE!")
            print("="*80)
            print(f"📁 Final assets: {output_dir}")
            print(f"📊 Progress: {workflow_summary['progress']} ({workflow_summary['progress_percent']}%)")
            print(f"📄 Original contribution: {len(article.user_contribution.split())} words")
            print(f"🚀 Enhanced content: {len(article.enhanced_content.split())} words")
            print(f"🖼️  Generated images: {image_count}")
            print(f"🎬 Timeline scenes: {len(timeline)}")
            print("="*80)
            
        except Exception as e:
            print(f"❌ Error assembling final assets: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='workflow-status')
    @click.option('--article-id', type=int, help='Show status for specific article.')
    @click.option('--list-all', is_flag=True, help='List all active workflows.')
    @with_appcontext
    def workflow_status_command(article_id, list_all):
        """Show workflow status for articles."""
        from .services.pipeline_orchestrator import orchestrator
        
        try:
            if list_all:
                workflows = orchestrator.list_active_workflows()
                if not workflows:
                    print("📭 No active workflows found.")
                    return
                
                print(f"🔄 Active Workflows ({len(workflows)}):")
                print("="*80)
                for workflow in workflows:
                    print(f"📰 Article {workflow['article_id']}: {workflow['progress']} complete")
                    print(f"   📍 Current phase: {workflow['current_phase']}")
                    print(f"   🎯 Next action: {workflow['next_action']}")
                    print(f"   📅 Updated: {workflow['updated_at']}")
                    print()
            
            elif article_id:
                summary = orchestrator.get_workflow_summary(article_id)
                if 'error' in summary:
                    print(f"❌ {summary['error']}")
                    return
                
                article = NewsArticle.query.get(article_id)
                print(f"🔄 Workflow Status for Article {article_id}")
                print("="*60)
                print(f"📰 Title: {article.title if article else 'Unknown'}")
                print(f"📍 Current Phase: {summary['current_phase']}")
                print(f"📊 Progress: {summary['progress']} ({summary['progress_percent']}%)")
                print(f"🎯 Next Action: {summary['next_action']}")
                print(f"✅ Completed Phases: {', '.join(summary['phases_completed'])}")
                print(f"📅 Created: {summary['created_at']}")
                print(f"📅 Updated: {summary['updated_at']}")
                
            else:
                print("❌ Specify either --article-id or --list-all")
                
        except Exception as e:
            print(f"❌ Error checking workflow status: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='workflow-init')
    @click.option('--article-id', required=True, type=int, help='Article ID to initialize workflow for.')
    @click.option('--force', is_flag=True, help='Force re-initialization of existing workflow.')
    @with_appcontext
    def workflow_init_command(article_id, force):
        """Initialize or restore workflow state for an article."""
        from .services.pipeline_orchestrator import orchestrator, WorkflowPhase
        
        try:
            # Get article from database
            article = NewsArticle.query.get(article_id)
            if not article:
                print(f"❌ Article {article_id} not found.")
                return
            
            # Check if workflow already exists
            existing_state = orchestrator.get_workflow_state(article_id)
            if existing_state and not force:
                print(f"✅ Workflow already exists for Article {article_id}")
                print(f"📍 Current phase: {existing_state.current_phase.value}")
                print(f"💡 Use --force to re-initialize")
                return
            
            # Determine appropriate phase based on article database state
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
                print(f"❌ Article {article_id} has insufficient data for workflow initialization")
                return
            
            # Initialize workflow with appropriate state
            if force and existing_state:
                print(f"🔄 Re-initializing workflow for Article {article_id}")
            else:
                print(f"🚀 Initializing workflow for Article {article_id}")
            
            state = orchestrator.initialize_workflow(article_id, {'restored': True})
            
            # Set appropriate phase and completed phases
            state.current_phase = current_phase
            state.phases_completed = completed_phases
            
            # Update article workflow_phase in database to match
            article.workflow_phase = current_phase.value
            db.session.commit()
            
            print(f"✅ Workflow initialized successfully!")
            print(f"📰 Article: {article.title}")
            print(f"📍 Current phase: {current_phase.value}")
            print(f"✅ Completed phases: {[p.value for p in completed_phases]}")
            
            # Show next action
            next_action_map = {
                WorkflowPhase.USER_CONTRIBUTION: f"flask contribute-take --article-id {article_id}",
                WorkflowPhase.AI_ENHANCEMENT: f"flask enhance-writing --article-id {article_id}",
                WorkflowPhase.TIMELINE_GENERATION: f"flask generate-enhanced-timeline --article-id {article_id}",
                WorkflowPhase.IMAGE_PROCESSING: f"flask process-visuals --article-id {article_id} --theme [theme]",
                WorkflowPhase.FINAL_ASSEMBLY: f"flask assemble-final --article-id {article_id}"
            }
            
            if current_phase in next_action_map:
                print(f"\n🎯 NEXT STEP:")
                print(f"   {next_action_map[current_phase]}")
            else:
                print(f"\n🎉 Workflow complete!")
                
        except Exception as e:
            print(f"❌ Error initializing workflow: {e}")
            import traceback
            traceback.print_exc()

    @click.command(name='voice-respond')
    @click.option('--query', required=True, type=str, help='The question or prompt to respond to.')
    @click.option('--context-file', type=str, help='Optional path to file containing context content.')
    @click.option('--length', default=250, type=int, help='Target word count for the response.')
    @click.option('--output-file', type=str, help='Custom output filename (without extension).')
    @with_appcontext
    def voice_respond_command(query, context_file, length, output_file):
        """Generate Thompson's response to a query, optionally using context content."""
        from .text_processor import generate_voiced_response_to_query
        import os
        from datetime import datetime
        
        print(f"🤖 Generating Thompson's response to: '{query}'")
        
        context_content = None
        if context_file:
            if not os.path.exists(context_file):
                print(f"❌ Context file not found: {context_file}")
                return
            
            print(f"📖 Loading context from: {context_file}")
            with open(context_file, 'r', encoding='utf-8') as f:
                context_content = f.read().strip()
            
            if not context_content:
                print(f"⚠️  Context file is empty, proceeding without context")
                context_content = None
            else:
                print(f"✅ Loaded {len(context_content)} characters of context")
        
        try:
            # Generate Thompson's response
            response = generate_voiced_response_to_query(query, context_content, length)
            
            # Create output directory
            output_dir = os.path.join('private', 'writing_style_samples', 'output', 'enhanced_scripts')
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename
            if output_file:
                filename = f"{output_file}.txt"
            else:
                # Create filename from query and timestamp
                safe_query = "".join(c for c in query[:30] if c.isalnum() or c in (' ', '-')).strip()
                safe_query = safe_query.replace(' ', '-').lower()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"response_{safe_query}_{timestamp}.txt"
            
            filepath = os.path.join(output_dir, filename)
            
            # Save the response
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Thompson's Response\n\n")
                f.write(f"**Query:** {query}\n\n")
                if context_content:
                    f.write(f"**Context Used:** {os.path.basename(context_file) if context_file else 'None'}\n\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Word Count:** ~{len(response.split())} words\n\n")
                f.write("---\n\n")
                f.write(response)
            
            print(f"\n✅ Response generated and saved to: {filepath}")
            print(f"📊 Word count: ~{len(response.split())} words")
            print("\n--- THOMPSON'S RESPONSE ---")
            print(response)
            print("--- END RESPONSE ---")
            
        except Exception as e:
            print(f"❌ Error generating voice response: {e}")
            import traceback
            traceback.print_exc()

    # Register streamlined workflow commands
    app.cli.add_command(story_create_command)
    app.cli.add_command(script_generate_command)
    app.cli.add_command(timeline_approve_command)
    app.cli.add_command(video_compose_command)
    app.cli.add_command(story_status_command)
    
    # Register collaborative workflow commands
    app.cli.add_command(discover_story_command)
    app.cli.add_command(archive_enhance_command)
    app.cli.add_command(create_article_command)
    app.cli.add_command(contribute_take_command)
    app.cli.add_command(enhance_writing_command)
    app.cli.add_command(generate_enhanced_timeline_command)
    app.cli.add_command(process_visuals_command)
    app.cli.add_command(assemble_final_command)
    app.cli.add_command(workflow_status_command)
    app.cli.add_command(workflow_init_command)
    
    # Existing commands
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
    app.cli.add_command(test_image_command)
    app.cli.add_command(process_story_command)
    app.cli.add_command(create_video_command)
    app.cli.add_command(compose_video_command)
    app.cli.add_command(test_archive_command)
    app.cli.add_command(voice_respond_command)

    return app

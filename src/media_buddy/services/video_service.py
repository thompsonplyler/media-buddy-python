"""
Video Assembly Service for Media Buddy

Handles video creation from images and voiceover audio using FFmpeg.
Follows modular architecture - no root directory pollution.
"""

import os
import subprocess
import json
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class VideoService:
    """Service for assembling videos from images and audio using FFmpeg."""
    
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        
    def _find_ffmpeg(self) -> str:
        """Find FFmpeg executable on Windows system."""
        # Common FFmpeg locations on Windows
        possible_paths = [
            "ffmpeg",  # If in PATH
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe"
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], 
                             capture_output=True, 
                             check=True, 
                             timeout=5)
                logger.info(f"Found FFmpeg at: {path}")
                return path
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                continue
                
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and add to PATH.")
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get the duration of an audio file in seconds using FFprobe.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Duration in seconds as float
        """
        try:
            # Use FFprobe to get precise audio duration
            cmd = [
                self.ffmpeg_path.replace("ffmpeg", "ffprobe"),
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "json",
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])
            
            logger.info(f"Audio duration: {duration:.2f} seconds")
            return duration
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to get audio duration: {e}")
            raise RuntimeError(f"Could not determine audio duration: {e}")
    
    def get_image_files(self, directory: str) -> List[str]:
        """
        Get sorted list of image files from directory.
        
        Args:
            directory: Path to directory containing images
            
        Returns:
            Sorted list of image file paths
        """
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        image_files = []
        
        for file in os.listdir(directory):
            if Path(file).suffix.lower() in image_extensions:
                image_files.append(os.path.join(directory, file))
        
        # Sort numerically (01.png, 02.png, etc.)
        image_files.sort()
        logger.info(f"Found {len(image_files)} images: {[os.path.basename(f) for f in image_files]}")
        
        return image_files
    
    def create_video(self, output_dir: str, output_filename: str = "video_out.mp4") -> str:
        """
        Create video from images and voiceover in the specified directory.
        
        Args:
            output_dir: Directory containing vo.mp3 and image files
            output_filename: Name of output video file
            
        Returns:
            Path to created video file
        """
        output_dir = Path(output_dir)
        audio_path = output_dir / "vo.mp3"
        output_path = output_dir / output_filename
        
        # Validate inputs
        if not audio_path.exists():
            raise FileNotFoundError(f"Voiceover file not found: {audio_path}")
        
        # Get audio duration - this is our MASTER CLOCK
        audio_duration = self.get_audio_duration(str(audio_path))
        
        # Get image files
        image_files = self.get_image_files(str(output_dir))
        if not image_files:
            raise ValueError(f"No image files found in {output_dir}")
        
        # Calculate duration per image
        duration_per_image = audio_duration / len(image_files)
        logger.info(f"Video duration: {audio_duration:.2f}s, {len(image_files)} images, {duration_per_image:.2f}s per image")
        
        # Create a temporary file list for FFmpeg concat demuxer
        filelist_path = output_dir / "filelist.txt"
        try:
            with open(filelist_path, 'w') as f:
                for image_file in image_files:
                    # Write each image with its display duration
                    f.write(f"file '{os.path.basename(image_file)}'\n")
                    f.write(f"duration {duration_per_image}\n")
                # Add the last image again to ensure proper timing
                if image_files:
                    f.write(f"file '{os.path.basename(image_files[-1])}'\n")
            
            # Build FFmpeg command using concat demuxer
            cmd = [
                self.ffmpeg_path,
                "-y",  # Overwrite output file
                "-f", "concat",
                "-safe", "0",
                "-i", str(filelist_path),
                "-i", str(audio_path),  # Input audio
                "-c:v", "libx264",  # H.264 codec as requested
                "-c:a", "aac",  # AAC audio codec
                "-pix_fmt", "yuv420p",  # Compatibility format
                "-shortest",  # Stop when shortest stream ends
                "-r", "30",  # Output frame rate
                str(output_path)
            ]
        except Exception as e:
            logger.error(f"Failed to create file list: {e}")
            raise RuntimeError(f"Could not create file list for FFmpeg: {e}")
        
        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")
        
        try:
            # Execute FFmpeg command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.stderr:
                logger.info(f"FFmpeg output: {result.stderr}")
            
            # Verify output file was created
            if not output_path.exists():
                raise RuntimeError("Output video file was not created")
            
            file_size = output_path.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"✅ Video created successfully: {output_path} ({file_size:.1f} MB)")
            
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr}")
            raise RuntimeError(f"Video creation failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg process timed out")
            raise RuntimeError("Video creation timed out after 5 minutes")
        finally:
            # Clean up temporary file list
            if filelist_path.exists():
                filelist_path.unlink()
                logger.debug(f"Cleaned up temporary file: {filelist_path}")

    def get_video_info(self, video_path: str) -> dict:
        """
        Get information about a video file.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video information
        """
        try:
            cmd = [
                self.ffmpeg_path.replace("ffmpeg", "ffprobe"),
                "-v", "quiet",
                "-show_entries", "format=duration,size:stream=width,height,codec_name",
                "-of", "json",
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Extract relevant info
            format_info = data.get("format", {})
            stream_info = data.get("streams", [{}])[0]
            
            return {
                "duration": float(format_info.get("duration", 0)),
                "size_bytes": int(format_info.get("size", 0)),
                "width": stream_info.get("width"),
                "height": stream_info.get("height"),
                "codec": stream_info.get("codec_name"),
                "path": video_path
            }
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to get video info: {e}")
            return {"error": str(e)} 
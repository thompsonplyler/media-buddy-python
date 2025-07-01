"""
Video Compositor Service - Advanced FFmpeg video composition and layering.

This service handles complex video composition tasks like:
- Layering videos with cycling images
- Multi-track composition
- Advanced FFmpeg filter graphs
"""

import os
import subprocess
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class VideoCompositor:
    """Service for advanced video composition using FFmpeg."""
    
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

    def get_video_info(self, video_path: str) -> Dict:
        """Get detailed information about a video file."""
        try:
            cmd = [
                self.ffmpeg_path.replace("ffmpeg", "ffprobe"),
                "-v", "quiet",
                "-show_entries", "format=duration:stream=width,height,codec_name,avg_frame_rate,codec_type",
                "-of", "json",
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # DEBUG: Log what we actually got from ffprobe
            logger.info(f"FFprobe raw output: {json.dumps(data, indent=2)}")
            
            # Extract video stream info
            video_stream = None
            streams = data.get("streams", [])
            logger.info(f"Found {len(streams)} streams")
            
            for i, stream in enumerate(streams):
                logger.info(f"Stream {i}: codec_type={stream.get('codec_type')}, codec_name={stream.get('codec_name')}")
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break
            
            if not video_stream:
                # More detailed error with all available streams
                stream_info = [f"Stream {i}: {s.get('codec_type', 'unknown')} ({s.get('codec_name', 'unknown')})" 
                              for i, s in enumerate(streams)]
                raise ValueError(f"No video stream found. Available streams: {', '.join(stream_info) if stream_info else 'none'}")
            
            format_info = data.get("format", {})
            
            return {
                "duration": float(format_info.get("duration", 0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "codec": video_stream.get("codec_name"),
                "fps": self._parse_frame_rate(video_stream.get("avg_frame_rate", "30/1")),
                "path": video_path
            }
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to get video info: {e}")
            raise RuntimeError(f"Could not analyze video: {e}")

    def _parse_frame_rate(self, fps_string: str) -> float:
        """Parse frame rate from FFprobe format like '30/1' or '29.97'."""
        try:
            if '/' in fps_string:
                num, den = fps_string.split('/')
                return float(num) / float(den)
            return float(fps_string)
        except (ValueError, ZeroDivisionError):
            return 30.0  # Default fallback

    def get_image_files(self, directory: str) -> List[str]:
        """Get sorted list of image files from directory."""
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        image_files = []
        
        for file in os.listdir(directory):
            if Path(file).suffix.lower() in image_extensions:
                image_files.append(os.path.join(directory, file))
        
        # Sort numerically (01.png, 02.png, etc.)
        image_files.sort()
        logger.info(f"Found {len(image_files)} images: {[os.path.basename(f) for f in image_files]}")
        
        return image_files

    def create_layered_composition(self, 
                                 input_dir: str, 
                                 output_filename: str = "composed_video.mp4",
                                 target_width: int = 1080,
                                 target_height: int = 1920) -> str:
        """
        Create a layered video composition with cycling images over a base video.
        
        Args:
            input_dir: Directory containing video file and image files
            output_filename: Name of output video file
            target_width: Width of output video (default 1080)
            target_height: Height of output video (default 1920)
            
        Returns:
            Path to created video file
        """
        input_dir = Path(input_dir)
        output_path = input_dir / output_filename
        
        # Find video file (support multiple formats)
        video_extensions = ["*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm"]
        video_files = []
        for ext in video_extensions:
            video_files.extend(input_dir.glob(ext))
        
        if not video_files:
            raise FileNotFoundError(f"No video file found in {input_dir}. Supported formats: {', '.join(video_extensions)}")
        
        video_path = video_files[0]
        logger.info(f"Using video file: {video_path}")
        
        # Get video information
        video_info = self.get_video_info(str(video_path))
        video_duration = video_info["duration"]
        original_width = video_info["width"]
        original_height = video_info["height"]
        
        logger.info(f"Video info: {original_width}x{original_height}, {video_duration:.2f}s")
        
        # Get image files
        image_files = self.get_image_files(str(input_dir))
        if not image_files:
            raise ValueError(f"No image files found in {input_dir}")
        
        # Calculate timing for image cycling
        duration_per_image = video_duration / len(image_files)
        logger.info(f"Will cycle {len(image_files)} images, {duration_per_image:.2f}s per image")
        
        # Calculate video scaling to fit width while maintaining aspect ratio
        scale_factor = target_width / original_width
        scaled_video_height = int(original_height * scale_factor)
        
        logger.info(f"Scaling video from {original_width}x{original_height} to {target_width}x{scaled_video_height}")
        
        # Calculate positioning
        video_y_offset = 0  # Place video at top
        
        # Build complex FFmpeg filter graph for layered composition
        filter_complex = self._build_composition_filter(
            image_files=image_files,
            video_duration=video_duration,
            duration_per_image=duration_per_image,
            target_width=target_width,
            target_height=target_height,
            scaled_video_width=target_width,
            scaled_video_height=scaled_video_height,
            video_y_offset=video_y_offset
        )
        
        # Build FFmpeg command
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output file
        ]
        
        # Add video input
        cmd.extend(["-i", str(video_path)])
        
        # Add image inputs
        for image_file in image_files:
            cmd.extend(["-i", image_file])
        
        # Add filter complex and output settings
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[final_output]",  # Use the final composed video
            "-map", "0:a:0",  # Use first audio stream directly
            "-c:v", "libx264",  # H.264 codec
            "-c:a", "copy",  # Copy AAC audio without re-encoding
            "-pix_fmt", "yuv420p",  # Compatibility format
            "-r", "30",  # Output frame rate
            str(output_path)  # Back to MP4 format
        ])
        
        logger.info(f"Executing FFmpeg composition command...")
        logger.debug(f"Command: {' '.join(cmd)}")
        
        try:
            # Execute FFmpeg command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=600  # 10 minute timeout for complex composition
            )
            
            if result.stderr:
                logger.info(f"FFmpeg output: {result.stderr}")
            
            # Verify output file was created
            if not output_path.exists():
                raise RuntimeError("Output video file was not created")
            
            file_size = output_path.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"✅ Layered composition created: {output_path} ({file_size:.1f} MB)")
            
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg composition failed: {e.stderr}")
            raise RuntimeError(f"Video composition failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg composition timed out")
            raise RuntimeError("Video composition timed out after 10 minutes")

    def _build_composition_filter(self, 
                                image_files: List[str],
                                video_duration: float,
                                duration_per_image: float,
                                target_width: int,
                                target_height: int,
                                scaled_video_width: int,
                                scaled_video_height: int,
                                video_y_offset: int) -> str:
        """Build the complex FFmpeg filter graph for layered composition."""
        
        filters = []
        
        # Scale the base video and position it
        filters.append(f"[0:v]scale={scaled_video_width}:{scaled_video_height}[scaled_video]")
        
        # Create a black background canvas
        filters.append(f"color=black:{target_width}x{target_height}:d={video_duration}[bg]")
        
        # Overlay the scaled video on the background at the top
        filters.append(f"[bg][scaled_video]overlay=0:{video_y_offset}[video_base]")
        
        # Process each image for cycling
        current_base = "video_base"
        
        for i, image_file in enumerate(image_files):
            start_time = i * duration_per_image
            end_time = (i + 1) * duration_per_image
            
            # Scale image to fill the bottom area (below the video)
            available_height = target_height - scaled_video_height  # Space below the video
            image_input_index = i + 1  # Images start at input index 1 (0 is video)
            
            # Scale image to fill the entire bottom area, crop if necessary
            # This ensures no black borders by scaling to cover the full area
            filters.append(f"[{image_input_index}:v]scale={target_width}:{available_height}:force_original_aspect_ratio=increase[img_{i}_scaled]")
            
            # Crop to exact dimensions if image was scaled larger than needed
            filters.append(f"[img_{i}_scaled]crop={target_width}:{available_height}[img_{i}_positioned]")
            
            # Create the image overlay with timing (position at bottom below video)
            if i == len(image_files) - 1:
                # Last image - no end time specified
                overlay_filter = f"[{current_base}][img_{i}_positioned]overlay=0:{scaled_video_height}:enable='gte(t,{start_time})'[final_output]"
            else:
                overlay_filter = f"[{current_base}][img_{i}_positioned]overlay=0:{scaled_video_height}:enable='between(t,{start_time},{end_time})'[img_overlay_{i}]"
                current_base = f"img_overlay_{i}"
            
            filters.append(overlay_filter)
        
        # Join all filters with semicolons
        return ";".join(filters) 
import os
import re
import shutil
import base64
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import httpx
from PIL import Image
from src.models import MediaFrame
from src.config import BASE_DIR

CACHE_DIR = BASE_DIR / "data" / "media_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_ffmpeg_path() -> Optional[str]:
    """Locate ffmpeg binary via imageio_ffmpeg or system PATH."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg
    return None

def file_to_base64(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def resize_image_file(input_path: Path, output_path: Path, max_width: int = 512) -> Path:
    """Resize image to width <= 512 while maintaining aspect ratio."""
    with Image.open(input_path) as im:
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        if im.width > max_width:
            ratio = max_width / float(im.width)
            new_height = max(1, int(float(im.height) * ratio))
            im = im.resize((max_width, new_height), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(output_path, "JPEG", quality=85)
    return output_path

class MediaProcessor:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.ffmpeg_path = get_ffmpeg_path()

    def process_media(
        self,
        post_id: Optional[str] = None,
        media_url: Optional[str] = None,
        media_type: Optional[str] = None,
        local_files: Optional[List[Path]] = None,
        carousel_urls: Optional[List[str]] = None
    ) -> Tuple[List[MediaFrame], bool]:
        """
        Extracts frames for a post video or images in time order.
        Returns (frames_list, context_missing).
        """
        cache_key = post_id or (media_url and Path(media_url).stem) or "uploaded"
        # Sanitize cache key for folder name
        safe_key = re.sub(r'[^a-zA-Z0-9_\-]', '_', cache_key)
        item_cache_dir = self.cache_dir / safe_key
        item_cache_dir.mkdir(parents=True, exist_ok=True)

        # Check existing cached frames
        existing_frames = sorted(item_cache_dir.glob("frame_*.jpg"))
        if existing_frames:
            frames: List[MediaFrame] = []
            for idx, p in enumerate(existing_frames):
                # parse timestamp from filename or index
                m = re.search(r'frame_(\d+)_?([\d\.]*)s?\.jpg', p.name)
                if m and m.group(2):
                    ts = float(m.group(2))
                    lbl = f"t={ts:.1f}s"
                else:
                    ts = float(idx * 2)
                    lbl = f"t={ts:.1f}s" if (media_type or "").lower() == "video" else f"Slide {idx + 1}"
                frames.append(MediaFrame(
                    timestamp=ts,
                    label=lbl,
                    base64_data=file_to_base64(p),
                    mime_type="image/jpeg",
                    file_path=str(p)
                ))
            return frames, False

        # If no local files and no media_url and no carousel_urls -> context missing
        if not local_files and not media_url and not carousel_urls:
            return [], True

        # Process local files (from upload)
        if local_files:
            return self._process_local_files(local_files, item_cache_dir, media_type)

        # Process from URLs
        return self._process_urls(media_url, carousel_urls, item_cache_dir, media_type)

    def _process_local_files(
        self,
        local_files: List[Path],
        target_dir: Path,
        media_type: Optional[str]
    ) -> Tuple[List[MediaFrame], bool]:
        frames: List[MediaFrame] = []
        is_video = False

        if len(local_files) == 1:
            ext = local_files[0].suffix.lower()
            if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
                is_video = True

        if is_video and self.ffmpeg_path:
            return self._extract_video_frames(local_files[0], target_dir)

        # Otherwise treat as images / carousel slides
        for idx, file_path in enumerate(local_files):
            out_file = target_dir / f"frame_{idx:02d}.jpg"
            try:
                resize_image_file(file_path, out_file, max_width=512)
                lbl = f"Slide {idx + 1}" if len(local_files) > 1 else "t=0.0s"
                frames.append(MediaFrame(
                    timestamp=float(idx * 2),
                    label=lbl,
                    base64_data=file_to_base64(out_file),
                    mime_type="image/jpeg",
                    file_path=str(out_file)
                ))
            except Exception as e:
                print(f"Warning: Failed to process image {file_path}: {e}")

        return frames, len(frames) == 0

    def _process_urls(
        self,
        media_url: Optional[str],
        carousel_urls: Optional[List[str]],
        target_dir: Path,
        media_type: Optional[str]
    ) -> Tuple[List[MediaFrame], bool]:
        if carousel_urls and len(carousel_urls) > 0:
            frames: List[MediaFrame] = []
            for idx, url in enumerate(carousel_urls):
                try:
                    resp = httpx.get(url, timeout=10.0)
                    resp.raise_for_status()
                    temp_in = target_dir / f"temp_{idx}.raw"
                    with open(temp_in, "wb") as f:
                        f.write(resp.content)
                    out_file = target_dir / f"frame_{idx:02d}.jpg"
                    resize_image_file(temp_in, out_file, max_width=512)
                    temp_in.unlink(missing_ok=True)
                    frames.append(MediaFrame(
                        timestamp=float(idx * 2),
                        label=f"Slide {idx + 1}",
                        base64_data=file_to_base64(out_file),
                        mime_type="image/jpeg",
                        file_path=str(out_file)
                    ))
                except Exception as e:
                    print(f"Warning: Failed downloading carousel slide {url}: {e}")
            return frames, len(frames) == 0

        if media_url:
            try:
                resp = httpx.get(media_url, timeout=15.0)
                resp.raise_for_status()
                # Detect video vs image
                content_type = resp.headers.get("content-type", "").lower()
                is_video = "video" in content_type or media_url.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
                temp_in = target_dir / ("temp_download.mp4" if is_video else "temp_download.jpg")
                with open(temp_in, "wb") as f:
                    f.write(resp.content)

                if is_video and self.ffmpeg_path:
                    res = self._extract_video_frames(temp_in, target_dir)
                    temp_in.unlink(missing_ok=True)
                    return res
                else:
                    out_file = target_dir / "frame_00.jpg"
                    resize_image_file(temp_in, out_file, max_width=512)
                    temp_in.unlink(missing_ok=True)
                    frame = MediaFrame(
                        timestamp=0.0,
                        label="t=0.0s",
                        base64_data=file_to_base64(out_file),
                        mime_type="image/jpeg",
                        file_path=str(out_file)
                    )
                    return [frame], False
            except Exception as e:
                print(f"Warning: Failed processing media URL {media_url}: {e}")
                return [], True

        return [], True

    def _extract_video_frames(self, video_path: Path, target_dir: Path) -> Tuple[List[MediaFrame], bool]:
        """
        Extract video frames:
        - about 1 frame / 2s
        - max 8 frames
        - plus first (0.0s) and last frame
        - width 512, drop audio
        """
        if not self.ffmpeg_path:
            return [], True

        try:
            # 1. Probe video duration
            duration = self._probe_video_duration(video_path)
            
            # Select target timestamps:
            # First frame: 0.0s
            timestamps = [0.0]
            if duration > 1.0:
                # 1 frame every 2s
                cur = 2.0
                while cur < (duration - 1.0) and len(timestamps) < 7:
                    timestamps.append(cur)
                    cur += 2.0
                # Last frame
                last_ts = max(0.5, duration - 0.2)
                if last_ts not in timestamps:
                    timestamps.append(last_ts)
            else:
                timestamps = [0.0]

            # Ensure max 8 frames total
            if len(timestamps) > 8:
                # Keep first, last, and evenly spaced in-between
                first = timestamps[0]
                last = timestamps[-1]
                mid = timestamps[1:-1]
                step = len(mid) // 6 + 1
                selected_mid = mid[::step][:6]
                timestamps = sorted(list(set([first] + selected_mid + [last])))

            frames: List[MediaFrame] = []
            for idx, ts in enumerate(timestamps):
                out_name = f"frame_{idx:02d}_{ts:.1f}s.jpg"
                out_path = target_dir / out_name
                
                # ffmpeg command: seek to ts, scale to 512 width, drop audio (-an)
                cmd = [
                    self.ffmpeg_path,
                    "-y",
                    "-ss", f"{ts:.2f}",
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-vf", "scale=512:-2",
                    "-an",
                    str(out_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

                if out_path.exists():
                    frames.append(MediaFrame(
                        timestamp=ts,
                        label=f"t={ts:.1f}s",
                        base64_data=file_to_base64(out_path),
                        mime_type="image/jpeg",
                        file_path=str(out_path)
                    ))

            return frames, len(frames) == 0

        except Exception as e:
            print(f"Warning: ffmpeg frame extraction failed: {e}")
            return [], True

    def _probe_video_duration(self, video_path: Path) -> float:
        """Estimate duration using ffmpeg output log."""
        if not self.ffmpeg_path:
            return 10.0
        try:
            cmd = [self.ffmpeg_path, "-i", str(video_path)]
            proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, check=False)
            match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', proc.stderr)
            if match:
                hours = float(match.group(1))
                minutes = float(match.group(2))
                seconds = float(match.group(3))
                return hours * 3600 + minutes * 60 + seconds
        except Exception:
            pass
        return 10.0

_media_processor: Optional[MediaProcessor] = None

def get_media_processor() -> MediaProcessor:
    global _media_processor
    if _media_processor is None:
        _media_processor = MediaProcessor()
    return _media_processor

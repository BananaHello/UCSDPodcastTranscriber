# UCSD Podcast Transcriber

A Python tool specifically designed to download and transcribe UCSD podcasts (which use Kaltura streaming), using OpenAI Whisper for transcription.

## How It Works

UCSD podcasts use Kaltura, a streaming platform that doesn't work with standard downloaders. This tool:

1. **Captures the stream**: Uses Selenium (headless Chrome) to load the podcast page and capture the m3u8 video stream URL from network requests
2. **Downloads audio**: Uses FFmpeg to download and extract audio from the stream
3. **Transcribes**: Uses OpenAI Whisper for accurate speech-to-text

## Installation

### 1. Install System Dependencies

**FFmpeg** (required for audio processing):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**Google Chrome** (required for capturing streams):
- Download from https://www.google.com/chrome/

### 2. Install Python Dependencies

```bash
pip install openai-whisper selenium webdriver-manager
```

## Usage

### Basic Usage

```bash
python ucsd_podcast_transcriber.py "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6"
```

### With Options

```bash
# Higher accuracy model (slower)
python ucsd_podcast_transcriber.py "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6" --model medium

# Custom output file
python ucsd_podcast_transcriber.py "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6" --output lecture.txt

# Keep the downloaded audio file
python ucsd_podcast_transcriber.py "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6" --keep-audio

# Specify language (speeds up transcription)
python ucsd_podcast_transcriber.py "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6" --language en
```

### Using as a Python Module

```python
from ucsd_podcast_transcriber import transcribe_podcast

transcript = transcribe_podcast(
    url="https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6",
    output_path="lecture_notes.txt",
    model="medium",
    language="en",
    keep_audio=True
)

print(transcript)
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `url` | UCSD podcast URL (required) |
| `-o, --output` | Output file path (default: transcript_TIMESTAMP.txt) |
| `-m, --model` | Whisper model: tiny, base, small, medium, large (default: base) |
| `-l, --language` | Language code like 'en' for English (auto-detected if not set) |
| `--keep-audio` | Keep the downloaded MP3 file |

## Whisper Models

| Model | Speed | Accuracy | VRAM |
|-------|-------|----------|------|
| tiny | Fastest | Basic | ~1 GB |
| base | Fast | Good | ~1 GB |
| small | Moderate | Better | ~2 GB |
| medium | Slow | High | ~5 GB |
| large | Slowest | Best | ~10 GB |

**Recommendation**: Start with `base`. Use `medium` for lectures with technical terms.

## Troubleshooting

### "Could not find video stream URL"

This usually means:
1. **Authentication required**: Some podcasts require UCSD login. Try:
   - Log into podcast.ucsd.edu in Chrome first
   - Make sure the URL is correct and the video loads in your browser

2. **Video hasn't loaded**: The tool waits 60 seconds for the video to load. If your connection is slow, the stream might not be captured in time.

### "Chrome driver" errors

```bash
pip install --upgrade webdriver-manager selenium
```

Make sure Google Chrome is installed on your system.

### "FFmpeg not found"

Install FFmpeg using the instructions in the Installation section above.

### Slow transcription

- Use a smaller model: `--model tiny` or `--model base`
- If you have an NVIDIA GPU, Whisper will automatically use it

### Out of memory

Use a smaller Whisper model. `tiny` and `base` work on most machines.

## Example Output

```
============================================================
🎙️  UCSD Podcast Transcriber
============================================================

🌐 Loading podcast page: https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6
   (This uses a headless browser to capture the video stream)
   Waiting for video player to load...
   Clicked play button
   Scanning network requests for video stream...
   ✅ Found video stream!
📥 Downloading audio stream...
✅ Audio downloaded: /tmp/podcast_20240115_143022.mp3
🔄 Loading Whisper model: base
🎙️ Transcribing audio...
✅ Transcription complete!
💾 Transcript saved to: transcript_20240115_143022.txt

============================================================
📝 Transcript Preview (first 500 characters):
============================================================
Welcome to COGS 108. Today we'll be discussing data science...

✨ Done!
```

## Non-UCSD URLs

This tool also works with YouTube, Vimeo, and other platforms (uses yt-dlp as fallback):

```bash
python ucsd_podcast_transcriber.py "https://youtube.com/watch?v=..."
```

## License

MIT License - Feel free to use and modify.

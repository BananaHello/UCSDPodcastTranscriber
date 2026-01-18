#!/usr/bin/env python3
"""
UCSD Podcast Transcriber
========================
A tool to download and transcribe UCSD podcasts using OpenAI Whisper.
Handles UCSD's Kaltura-based video system by capturing m3u8 streams.

Requirements:
    pip install openai-whisper selenium webdriver-manager

Usage:
    python ucsd_podcast_transcriber.py <podcast_url> [options]

Examples:
    python ucsd_podcast_transcriber.py "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6"
    python ucsd_podcast_transcriber.py "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6" --model medium
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []

    # Check for whisper
    try:
        import whisper
    except ImportError:
        missing.append("openai-whisper")

    # Check for selenium
    try:
        from selenium import webdriver
    except ImportError:
        missing.append("selenium")

    # Check for webdriver_manager
    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        missing.append("webdriver-manager")

    # Check for ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  FFmpeg not found. Please install it:")
        print("   macOS: brew install ffmpeg")
        print("   Ubuntu: sudo apt install ffmpeg")
        print("   Windows: Download from https://ffmpeg.org/download.html")
        sys.exit(1)

    if missing:
        print("❌ Missing Python dependencies:")
        for dep in missing:
            print(f"   - {dep}")
        print("\nInstall them with:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)

    return True


def clean_m3u8_url(url: str) -> str:
    """
    Clean up an m3u8 URL by removing JSONP callback parameters.

    Args:
        url: The potentially dirty m3u8 URL

    Returns:
        A clean m3u8 URL that FFmpeg can use
    """
    # Remove JSONP callback parameters that break FFmpeg
    # These are typically: callback=jQuery..., responseFormat=jsonp, _=timestamp
    if "responseFormat=jsonp" in url or "callback=" in url:
        # Parse and rebuild the URL without problematic params
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Remove problematic parameters
        params_to_remove = ['callback', 'responseFormat', '_']
        for param in params_to_remove:
            params.pop(param, None)

        # Rebuild query string (parse_qs returns lists, so flatten them)
        clean_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        clean_query = urlencode(clean_params)

        # Rebuild URL
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_query,
            parsed.fragment
        ))
        return clean_url

    return url


def is_valid_m3u8_url(url: str) -> bool:
    """
    Check if a URL is a valid m3u8 stream URL (not a JSONP request).
    """
    # Skip JSONP callback URLs - they're API requests, not actual streams
    if "callback=" in url and "responseFormat=jsonp" in url:
        return False

    # Must end with .m3u8 or have .m3u8 in path (before query params)
    if ".m3u8" in url:
        return True

    return False


def extract_m3u8_url(url: str, timeout: int = 60) -> str:
    """
    Use Selenium to load the UCSD podcast page and capture the m3u8 stream URL.

    Args:
        url: The UCSD podcast URL
        timeout: Maximum time to wait for the stream URL

    Returns:
        The m3u8 stream URL
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    print(f"🌐 Loading podcast page: {url}")
    print("   (This uses a headless browser to capture the video stream)")

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Enable performance logging to capture network requests
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # Initialize the driver
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"❌ Failed to initialize Chrome driver: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Google Chrome is installed")
        print("2. Try: pip install --upgrade webdriver-manager selenium")
        raise

    m3u8_url = None
    all_m3u8_urls = []  # Collect all candidates

    try:
        driver.get(url)

        # Wait for page to load and video player to initialize
        print("   Waiting for video player to load...")
        time.sleep(5)

        # Try to click play button if it exists
        try:
            play_buttons = driver.find_elements(By.CSS_SELECTOR,
                "[class*='play'], [aria-label*='play'], button[title*='Play'], .playButton, .vjs-play-control, .largePlayBtn, [data-testid='play-button']")
            for btn in play_buttons:
                try:
                    btn.click()
                    print("   Clicked play button")
                    time.sleep(3)
                    break
                except:
                    pass
        except:
            pass

        # Collect performance logs to find m3u8 URL
        print("   Scanning network requests for video stream...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            logs = driver.get_log("performance")

            for log in logs:
                try:
                    message = json.loads(log["message"])["message"]

                    if message["method"] == "Network.requestWillBeSent":
                        request_url = message["params"]["request"]["url"]

                        # Look for m3u8 playlist URLs
                        if ".m3u8" in request_url:
                            # Skip JSONP callback URLs
                            if "callback=" in request_url and "responseFormat=jsonp" in request_url:
                                continue

                            all_m3u8_urls.append(request_url)

                            # Prefer master/index m3u8 files (these are the main playlist)
                            if any(x in request_url.lower() for x in ["master.m3u8", "index.m3u8"]):
                                m3u8_url = request_url
                                print(f"   ✅ Found master playlist!")
                                break
                            # Also look for segment playlists (chunklist, media)
                            elif any(x in request_url.lower() for x in ["chunklist", "media", "segment"]):
                                if not m3u8_url:
                                    m3u8_url = request_url

                except (json.JSONDecodeError, KeyError):
                    pass

            if m3u8_url:
                break

            time.sleep(1)

        # If we didn't find a master playlist, use the first valid m3u8 we found
        if not m3u8_url and all_m3u8_urls:
            m3u8_url = all_m3u8_urls[0]
            print(f"   ✅ Found video stream!")

        if not m3u8_url:
            # Try to find it in page source as a fallback
            page_source = driver.page_source

            # Look for m3u8 URLs in the page source
            m3u8_matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?', page_source)

            # Filter out JSONP URLs
            valid_matches = [u for u in m3u8_matches if is_valid_m3u8_url(u)]

            if valid_matches:
                m3u8_url = valid_matches[0]
                print(f"   ✅ Found video stream in page source!")

    finally:
        driver.quit()

    if not m3u8_url:
        raise ValueError(
            "Could not find video stream URL. The video might require authentication.\n"
            "Try logging into UCSD in your browser first, or check if the podcast URL is correct."
        )

    # Clean the URL before returning
    m3u8_url = clean_m3u8_url(m3u8_url)

    return m3u8_url


def download_with_ffmpeg(m3u8_url: str, output_path: str) -> str:
    """
    Download audio from m3u8 stream using FFmpeg.

    Args:
        m3u8_url: The m3u8 playlist URL
        output_path: Path for the output audio file

    Returns:
        Path to the downloaded audio file
    """
    print(f"📥 Downloading audio stream...")

    cmd = [
        "ffmpeg",
        "-i", m3u8_url,
        "-vn",  # No video
        "-acodec", "libmp3lame",  # MP3 codec
        "-ab", "192k",  # Audio bitrate
        "-y",  # Overwrite output
        output_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            # FFmpeg writes to stderr even on success, check if file exists
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"✅ Audio downloaded: {output_path}")
                return output_path
            else:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

        print(f"✅ Audio downloaded: {output_path}")
        return output_path

    except subprocess.TimeoutExpired:
        raise TimeoutError("Download timed out after 10 minutes")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg error: {e.stderr}")
        raise


def download_audio(url: str, output_dir: str) -> str:
    """
    Download audio from a UCSD podcast URL.

    Args:
        url: The podcast URL
        output_dir: Directory to save the audio

    Returns:
        Path to the downloaded audio file
    """
    # Check if this is a UCSD podcast URL
    if "podcast.ucsd.edu" in url:
        # Use Selenium to extract m3u8 URL
        m3u8_url = extract_m3u8_url(url)

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"podcast_{timestamp}.mp3")

        # Download with FFmpeg
        return download_with_ffmpeg(m3u8_url, output_path)
    else:
        # For non-UCSD URLs, try yt-dlp
        return download_with_ytdlp(url, output_dir)


def download_with_ytdlp(url: str, output_dir: str) -> str:
    """
    Download audio using yt-dlp for non-UCSD URLs.
    """
    print(f"📥 Downloading audio from: {url}")

    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  yt-dlp not found. Install with: pip install yt-dlp")
        raise

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_template = os.path.join(output_dir, f"podcast_{timestamp}.%(ext)s")

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_template,
        "--no-playlist",
        url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    for file in os.listdir(output_dir):
        if file.startswith(f"podcast_{timestamp}"):
            return os.path.join(output_dir, file)

    raise FileNotFoundError("Downloaded audio file not found")


def transcribe_audio(audio_path: str, model_name: str = "base", language: str = None) -> str:
    """
    Transcribe audio using OpenAI Whisper.
    """
    import whisper

    print(f"🔄 Loading Whisper model: {model_name}")
    print("   (First run downloads the model, which may take a few minutes)")

    model = whisper.load_model(model_name)

    print(f"🎙️ Transcribing audio...")
    print(f"   File: {audio_path}")
    print("   This may take a while depending on the audio length...")

    options = {}
    if language:
        options["language"] = language

    result = model.transcribe(audio_path, **options)

    print("✅ Transcription complete!")
    return result["text"]


def clean_transcript(text: str) -> str:
    """
    Clean up Whisper hallucinations from the transcript.

    Whisper tends to hallucinate during silence or low audio, producing:
    - Random non-English text at the beginning (before lecture starts)
    - Repetitive phrases at the end (like "Thank you. Thank you. Thank you.")
    - Random gibberish during silent periods

    Args:
        text: The raw transcript text

    Returns:
        Cleaned transcript text
    """
    print("🧹 Cleaning up transcript...")

    original_length = len(text)

    # First pass: remove obvious non-English characters and gibberish patterns
    # These are common Whisper hallucination patterns
    hallucination_patterns = [
        r'[가-힣]+',  # Korean characters
        r'[一-龯]+',  # Chinese characters
        r'[ぁ-んァ-ン]+',  # Japanese characters
        r'[а-яА-Я]+',  # Cyrillic characters
        r'\b[A-Z]?[a-z]*[äöüáéíóúàèìòùâêîôûãõñ][a-z]*\b',  # Words with accented chars (hallucinations)
        r"\b(sy'n|gyms|gyflen|newidda|roedd|gwilia|gyfly|canyan|ayag|teu|aun)\b",  # Welsh-like gibberish
        r'\bIag\b',  # Common hallucination
    ]

    cleaned_text = text
    for pattern in hallucination_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', cleaned_text)

    def is_coherent_english(s: str) -> bool:
        """Check if a string is coherent English text (not just fragments)."""
        s = s.strip()
        if not s or len(s) < 10:
            return False

        # Common English words - must have several of these
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                       'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                       'could', 'should', 'may', 'might', 'must', 'shall', 'can',
                       'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                       'this', 'that', 'these', 'those', 'it', 'its', 'you', 'your',
                       'we', 'our', 'they', 'their', 'i', 'my', 'me', 'he', 'she',
                       'and', 'or', 'but', 'if', 'so', 'as', 'what', 'which', 'who',
                       'how', 'when', 'where', 'why', 'all', 'each', 'every', 'both',
                       'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not',
                       'only', 'same', 'than', 'too', 'very', 'just', 'also', 'now',
                       'here', 'there', 'then', 'once', 'going', 'want', 'need',
                       'like', 'know', 'think', 'see', 'get', 'make', 'take', 'come',
                       'right', 'okay', 'well', 'yeah', 'yes', 'no', 'so', 'really',
                       'today', 'already', 'use', 'using', 'copy', 'local', 'laptop'}

        words = re.findall(r'\b[a-zA-Z]+\b', s.lower())
        if len(words) < 3:
            return False

        english_word_count = sum(1 for w in words if w in common_words)

        # Need at least 3 common words OR 25% of words to be common
        if english_word_count >= 3:
            return True
        if len(words) > 0 and english_word_count / len(words) >= 0.25:
            return True

        return False

    # Find where real content starts (skip gibberish at beginning)
    # Look for patterns that indicate lecture start - we'll use these to find the exact start point
    lecture_start_patterns = [
        r'(?:okay|alright|so|well|hey|hi|hello)?,?\s*my friends',
        r'(?:okay|alright|so|well)?,?\s*today',
        r'welcome\s+(?:to|back|everyone)',
        r'(?:good\s+)?(?:morning|afternoon|evening)',
        r"let's\s+(?:get\s+started|begin|start|talk|look)",
        r"we're\s+going\s+to",
        r"going\s+to\s+be\s+a",
        r"hello\s+(?:everyone|everybody|class)",
    ]

    start_index = 0
    start_char_offset = 0  # For trimming within the first sentence

    for i, sentence in enumerate(sentences):
        sentence_lower = sentence.lower()

        # Check if this sentence has lecture-start indicators
        for pattern in lecture_start_patterns:
            match = re.search(pattern, sentence_lower)
            if match:
                # Found a lecture start pattern - trim everything before it
                start_index = i
                start_char_offset = match.start()
                break

        if start_char_offset > 0:
            break

        # Fallback: Look for a sentence that's clearly English and substantial
        if is_coherent_english(sentence) and len(sentence) > 50:
            # Verify next couple sentences are also coherent
            if i + 2 < len(sentences):
                if is_coherent_english(sentences[i + 1]) or is_coherent_english(sentences[i + 2]):
                    start_index = i
                    break
            else:
                start_index = i
                break

    # Find where real content ends (remove post-lecture chatter and repetitive endings)
    end_index = len(sentences)

    # Patterns that indicate post-lecture chatter (students asking questions, informal chat)
    # These mark where to STOP, not where the lecture ends
    chatter_patterns = [
        r"^hey\.?$",  # Just "Hey." by itself
        r"am i allowed to",
        r"can i (?:ask|get)",
        r"i love to have",
        r"this is like doing",
        r"^okay\.?$",  # Just "Okay." by itself at end
        r"^yeah\.?$",  # Just "Yeah." by itself
        r"^right\.?$",  # Just "Right." by itself
        r"^sure\.?$",  # Just "Sure." by itself
    ]

    # Find where chatter begins (scan from end backwards)
    chatter_start_index = None
    for i in range(len(sentences) - 1, max(0, len(sentences) - 30), -1):
        sentence_lower = sentences[i].strip().lower()
        for pattern in chatter_patterns:
            if re.search(pattern, sentence_lower):
                chatter_start_index = i
                break
        if chatter_start_index:
            # Keep scanning backwards to find where chatter really starts
            continue

    if chatter_start_index:
        end_index = chatter_start_index

    # Remove trailing "Thank you" repetitions and short filler phrases
    thank_you_variants = {'thank you.', 'thank you', 'thanks.', 'thanks',
                         'thank you!', 'thanks!', 'bye.', 'bye', 'goodbye.',
                         'goodbye', 'see you.', 'see you', 'okay.', 'okay',
                         'alright.', 'alright', 'hey.', 'hey', 'yeah.', 'yeah'}

    # Also remove short informal sentences at the end (post-lecture chatter)
    while end_index > start_index:
        last_sentence = sentences[end_index - 1].strip().lower()

        # Remove known filler phrases
        if last_sentence in thank_you_variants:
            end_index -= 1
            continue

        # Remove very short sentences (likely chatter)
        if len(last_sentence) < 15:
            end_index -= 1
            continue

        # Remove sentences that are mostly informal/filler words
        informal_indicators = ['okay', 'alright', 'hey', 'yeah', 'um', 'uh',
                              'like', 'i mean', 'you know', 'right']
        word_count = len(last_sentence.split())
        informal_count = sum(1 for ind in informal_indicators if ind in last_sentence)
        if word_count < 10 and informal_count >= 2:
            end_index -= 1
            continue

        break

    # Check for repetitive patterns at the end
    if end_index > start_index + 5:
        for i in range(end_index - 1, max(end_index - 15, start_index), -1):
            remaining = [s.strip().lower() for s in sentences[i:end_index]]
            if len(remaining) >= 3:
                # Check if most are the same
                from collections import Counter
                counts = Counter(remaining)
                most_common, count = counts.most_common(1)[0]
                if count >= len(remaining) * 0.6:
                    end_index = i
                    break

    # Reconstruct the cleaned transcript
    cleaned_sentences = sentences[start_index:end_index]

    # Apply the character offset to trim gibberish from the start of the first sentence
    if start_char_offset > 0 and cleaned_sentences:
        cleaned_sentences[0] = cleaned_sentences[0][start_char_offset:].lstrip()

    cleaned_text = ' '.join(cleaned_sentences)

    # Final cleanup: extra whitespace and leading punctuation
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    cleaned_text = re.sub(r'^[,.\s]+', '', cleaned_text)  # Remove leading commas/periods

    removed_chars = original_length - len(cleaned_text)
    if removed_chars > 0:
        print(f"   Removed {removed_chars} characters of gibberish/repetition")
    else:
        print("   No significant cleanup needed")

    return cleaned_text


def save_transcript(text: str, output_path: str) -> str:
    """Save the transcript to a text file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"💾 Transcript saved to: {output_path}")
    return output_path


def transcribe_podcast(
    url: str,
    output_path: str = None,
    model: str = "base",
    language: str = None,
    keep_audio: bool = False
) -> str:
    """
    Main function to download and transcribe a podcast.
    """
    check_dependencies()

    with tempfile.TemporaryDirectory() as temp_dir:
        if keep_audio:
            audio_dir = os.getcwd()
        else:
            audio_dir = temp_dir

        # Download audio
        audio_path = download_audio(url, audio_dir)

        # Transcribe
        transcript = transcribe_audio(audio_path, model, language)

        # Clean up hallucinations and gibberish
        transcript = clean_transcript(transcript)

        # Generate output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/Users/atjon/Desktop/Code/COGS108Lectures/transcript_{timestamp}.txt"

        # Save transcript
        save_transcript(transcript, output_path)

        if not keep_audio and audio_dir != temp_dir:
            os.remove(audio_path)
            print("🧹 Cleaned up temporary audio file")
        elif keep_audio:
            print(f"🎵 Audio file kept at: {audio_path}")

        return transcript


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Transcribe UCSD podcasts using OpenAI Whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6"
  %(prog)s "https://podcast.ucsd.edu/watch/wi26/cogs108_b00/6" --model medium
  %(prog)s "https://youtube.com/watch?v=xxx" -o my_transcript.txt

Whisper Models:
  tiny    - Fastest, least accurate (~1GB VRAM)
  base    - Good balance (default) (~1GB VRAM)
  small   - Better accuracy (~2GB VRAM)
  medium  - High accuracy (~5GB VRAM)
  large   - Best accuracy, slowest (~10GB VRAM)
        """
    )

    parser.add_argument("url", help="URL of the podcast to transcribe")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-m", "--model", default="base",
                       choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("-l", "--language", help="Language code (e.g., 'en')")
    parser.add_argument("--keep-audio", action="store_true",
                       help="Keep the downloaded audio file")

    args = parser.parse_args()

    print("=" * 60)
    print("🎙️  UCSD Podcast Transcriber")
    print("=" * 60)
    print()

    try:
        transcript = transcribe_podcast(
            url=args.url,
            output_path=args.output,
            model=args.model,
            language=args.language,
            keep_audio=args.keep_audio
        )

        print()
        print("=" * 60)
        print("📝 Transcript Preview (first 500 characters):")
        print("=" * 60)
        print(transcript[:500] + "..." if len(transcript) > 500 else transcript)
        print()
        print("✨ Done!")

    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

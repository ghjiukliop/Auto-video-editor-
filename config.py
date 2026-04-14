from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

INPUT_FOLDER = BASE_DIR / "input_videos"
OUTPUT_FOLDER = BASE_DIR / "output_videos"
TEMP_FOLDER = BASE_DIR / "temp"

# CPU: "medium" on long videos can take many hours with no UI feedback. "small" is a
# practical default; override with: python main.py --model medium
WHISPER_MODEL = "small" 
TTS_VOICE = "vi-VN-HoaiMyNeural"
TTS_RATE = "0%"   
TTS_PITCH = "+0Hz"

BGM_VOLUME = 0
VOICE_VOLUME = 1.0

DEMUC_MODEL = "htdemucs"

# ============================================================================
# OLLAMA CONFIGURATION (Local LLM)
# ============================================================================
OLLAMA_MODEL = "qwen2.5:7b"  # Model to use (change to your preferred model)
OLLAMA_HOST = "http://localhost:11434"  # Default Ollama host
OLLAMA_BATCH_SIZE = 100  # Number of lines per batch (optimize for RAM/VRAM) - reduced from 500


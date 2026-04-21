#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration cho YouTube Automation Pipeline
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv(Path(__file__).parent / "Key" / "allkey.env")

# ============ GEMINI CONFIG ============
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BATCH_SIZE = 10
GEMINI_TEMPERATURE = 0.7
GEMINI_MAX_RETRIES = 3

# ============ FOLDER PATHS ============
PROJECT_ROOT = Path(__file__).parent
INPUT_VIDEO_DIR = PROJECT_ROOT / "input" / "VideoInput"
INPUT_AUDIO_DIR = PROJECT_ROOT / "input" / "AudioInput"
INPUT_SRT_DIR = PROJECT_ROOT / "input" / "SrtInput"
OUTPUT_SRT_DIR = PROJECT_ROOT / "output" / "SrtOutput"
OUTPUT_AUDIO_DIR = PROJECT_ROOT / "output" / "AudioOutput"
OUTPUT_VIDEO_DIR = PROJECT_ROOT / "output_videos"
TEMP_DIR = PROJECT_ROOT / "temp"

# ============ TTS CONFIG ============
TTS_ENGINE = os.getenv("TTS_ENGINE", "gtts")  # gtts, google_cloud, pyttsx3
TTS_LANGUAGE = "vi"  # Vietnamese

# ============ WHISPER CONFIG ============
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large

# ============ DEBUG ============
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

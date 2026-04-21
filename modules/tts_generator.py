"""
TTS Generator: Tạo giọng AI từ text
Hỗ trợ:
- gTTS (Google Text-to-Speech) - chất lượng cao, miễn phí
- edge-tts (Microsoft Edge TTS fallback) - nhanh, miễn phí, không hang
- Google Cloud TTS (backup, chất lượng cao)
- pyttsx3 (local fallback) - cuối cùng

OPTIMIZED: Auto-fallback + Retry logic with timeout
"""

import os
import json
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

try:
    from google.cloud import texttospeech
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


class TTSGenerator:
    """Tạo audio từ text với nhiều engine khác nhau"""
    
    def __init__(self, service="gtts", output_dir="output/AudioOutput", language="vi"):
        """
        service: "google_cloud" | "gtts" | "pyttsx3"
        output_dir: thư mục lưu audio
        language: mã ngôn ngữ ("vi" = Việt, "en" = English)
        """
        self.service = service
        self.output_dir = Path(output_dir)
        self.language = language
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎙️ TTS Generator initialized: {service} (Language: {language})")
        
        # Init Google Cloud TTS nếu cần
        if service == "google_cloud" and GOOGLE_TTS_AVAILABLE:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(
                Path(__file__).parent.parent / "Key" / "google_tts_key.json"
            )
            self.client = texttospeech.TextToSpeechClient()
            self.voice = texttospeech.VoiceSelectionParams(
                language_code=self._get_language_code(),
                name="vi-VN-Standard-A" if language == "vi" else "en-US-Standard-A"
            )
        
        # Init pyttsx3 - will be recreated per file to avoid Windows hang bug
        self.engine = None
        self.pyttsx3_count = 0  # Track restarts
    
    def _get_language_code(self):
        """Map language to code"""
        codes = {
            "vi": "vi-VN",
            "en": "en-US",
            "zh": "zh-CN",
            "ja": "ja-JP",
        }
        return codes.get(self.language, "vi-VN")
    
    def generate(self, text, output_filename, speed=1.0, verbose=False):
        """
        Tạo audio từ text
        text: lời thoại
        output_filename: tên file output (ví dụ: "0001.wav")
        speed: tốc độ phát âm (1.0 = bình thường, 1.5 = nhanh hơn)
        verbose: In log chi tiết (False trong batch_generate)
        """
        output_path = self.output_dir / output_filename
        
        try:
            if self.service == "google_cloud" and GOOGLE_TTS_AVAILABLE:
                return self._generate_google_cloud(text, output_path, speed, verbose)
            elif self.service == "gtts" and GTTS_AVAILABLE:
                return self._generate_gtts(text, output_path, speed, verbose)
            elif self.service == "pyttsx3" and PYTTSX3_AVAILABLE:
                return self._generate_pyttsx3(text, output_path, speed, verbose)
            else:
                if verbose:
                    print(f"❌ Service {self.service} không khả dụng!")
                return None
        except Exception as e:
            if verbose:
                print(f"❌ Lỗi TTS: {str(e)[:100]}")
            return None
    
    def _generate_google_cloud(self, text, output_path, speed, verbose=False):
        """Google Cloud TTS - chất lượng cao nhất"""
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=speed
            )
            
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=audio_config
            )
            
            with open(output_path, "wb") as f:
                f.write(response.audio_content)
            
            if verbose:
                print(f"✅ Google Cloud TTS: {output_path.name}")
            return output_path
        except Exception as e:
            if verbose:
                print(f"❌ Google Cloud TTS lỗi: {e}")
            return None
    
    def _generate_gtts(self, text, output_path, speed, verbose=False):
        """gTTS - miễn phí, nhanh"""
        try:
            # gTTS không hỗ trợ speed trực tiếp, nhưng chất lượng vẫn tốt
            tts = gTTS(text=text, lang=self.language, slow=False)
            tts.save(str(output_path))
            
            if verbose:
                print(f"✅ gTTS: {output_path.name}")
            return output_path
        except Exception as e:
            if verbose:
                print(f"❌ gTTS lỗi: {e}")
            return None
    
    def _generate_pyttsx3(self, text, output_path, speed, verbose=False):
        """pyttsx3 - local, không cần internet
        
        NOTE: On Windows, pyttsx3 can hang on runAndWait() after first call.
        Workaround: Create fresh engine for each file to avoid the hang.
        """
        try:
            if not PYTTSX3_AVAILABLE:
                if verbose:
                    print(f"❌ pyttsx3 not available")
                return None
            
            # Create fresh engine for this file (Windows workaround)
            engine = pyttsx3.init()
            engine.setProperty('rate', int(150 * speed))
            engine.save_to_file(text, str(output_path))
            
            # This can sometimes hang on Windows - minimal wait
            engine.runAndWait()
            
            # Clean up engine
            try:
                engine.stop()
            except:
                pass
            
            if verbose:
                print(f"✅ pyttsx3: {output_path.name}")
            return output_path
        except Exception as e:
            if verbose:
                print(f"❌ pyttsx3 lỗi: {e}")
            return None
    
    def _generate_edge_tts(self, text, output_path, speed, verbose=False):
        """edge-tts - Microsoft Edge TTS (free, fast, no hang issues)
        
        NOTE: edge-tts saves output as WebM/MP3. We save as MP3 for compatibility.
        """
        try:
            if not EDGE_TTS_AVAILABLE:
                if verbose:
                    print(f"❌ edge-tts not available")
                return None
            
            # Get voice for language
            voice_map = {
                "vi": "vi-VN-HoaiMyNeural",  # Vietnamese female
                "en": "en-US-AriaNeural",     # English female
            }
            voice = voice_map.get(self.language, "vi-VN-HoaiMyNeural")
            
            # Change output path to MP3 (edge-tts works better with MP3)
            output_path = Path(output_path)
            mp3_path = output_path.parent / f"{output_path.stem}.mp3"
            
            # Generate with edge-tts
            async def _generate():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(mp3_path))
            
            # Run async in event loop
            try:
                asyncio.run(_generate())
            except RuntimeError:
                # Event loop already running, use new loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_generate())
                loop.close()
            
            # Verify file was created
            if mp3_path.exists() and mp3_path.stat().st_size > 1000:
                if verbose:
                    print(f"✅ edge-tts: {mp3_path.name}")
                return mp3_path
            else:
                if verbose:
                    print(f"❌ edge-tts: File not created or empty")
                return None
        except Exception as e:
            if verbose:
                print(f"❌ edge-tts lỗi: {e}")
            return None
    
    def batch_generate(self, items, show_progress=True, max_workers=4, max_retries=2):
        """
        Tạo audio hàng loạt - với FALLBACK SERVICES
        
        items: [{"text": "...", "filename": "0001.wav", "speed": 1.0}, ...]
        
        Chiến lược:
        1. Thử gTTS (Google, chất lượng cao)
        2. Nếu fail → thử edge-tts (Microsoft, nhanh, miễn phí)
        3. Nếu fail → thử pyttsx3 (local, offline)
        4. AUTO-SWITCH: Nếu gTTS fail 2 lần → dùng edge-tts cho tất cả files còn lại
        """
        results = []
        skip_count = 0
        failed = []
        
        print(f"🎙️ TTS: Bắt đầu quét cache...")
        
        # Lọc: bỏ cached files (check for both .wav and .mp3)
        items_to_process = []
        for item in items:
            filename = item.get("filename")
            output_path = self.output_dir / filename
            
            # Check if file already exists (WAV or MP3)
            file_exists = output_path.exists() and output_path.stat().st_size > 1000
            
            # Also check for MP3 version if looking for WAV
            if not file_exists and output_path.suffix.lower() == '.wav':
                mp3_path = output_path.parent / f"{output_path.stem}.mp3"
                file_exists = mp3_path.exists() and mp3_path.stat().st_size > 1000
                if file_exists:
                    results.append(mp3_path)
                    skip_count += 1
                    continue
            
            if file_exists:
                skip_count += 1
                results.append(output_path)
            else:
                items_to_process.append(item)
        
        total = len(items)
        print(f"✅ Cache: {skip_count} files, Cần tạo: {len(items_to_process)} files")
        
        if not items_to_process:
            print(f"✅ Tất cả đã tạo xong! {len(results)}/{total}")
            return results
        
        # Tạo sequential với fallback
        print(f"⚡ Tạo audio {len(items_to_process)} files (with fallback)...\n")
        start_time = time.time()
        
        # Track failures to auto-switch to fallback
        consecutive_gtts_failures = 0
        force_pyttsx3 = False
        pyttsx3_engine_ready = False  # Only create once
        
        for i, item in enumerate(items_to_process, 1):
            text = item.get("text", "")
            filename = item.get("filename")
            speed = item.get("speed", 1.0)
            
            output_path = self.output_dir / filename
            
            success = False
            error_msg = ""
            
            # Decision: use gTTS or fallback?
            use_gtts_first = (self.service == "gtts" and GTTS_AVAILABLE and not force_pyttsx3)
            
            for attempt in range(1, max_retries + 1):
                try:
                    if use_gtts_first:
                        # Try gTTS first
                        tts = gTTS(text=text, lang=self.language, slow=False)
                        tts.save(str(output_path))
                        consecutive_gtts_failures = 0  # Reset on success
                        success = True
                        break
                    else:
                        # Use edge-tts (primary fallback - faster, no hang issues)
                        if EDGE_TTS_AVAILABLE:
                            result = self._generate_edge_tts(text, output_path, speed, verbose=False)
                            if result:
                                success = True
                                break
                        
                        # Fallback to pyttsx3 if edge-tts not available
                        if PYTTSX3_AVAILABLE and not success:
                            result = self._generate_pyttsx3(text, output_path, speed, verbose=False)
                            if result:
                                success = True
                                break
                        
                        if not success:
                            error_msg = "No fallback services available"
                
                except Exception as e:
                    error_msg = str(e)[:50]
                    
                    # gTTS failed - try edge-tts fallback
                    if use_gtts_first:
                        consecutive_gtts_failures += 1
                        
                        # If 2 failures in a row, force edge-tts for all remaining files
                        if consecutive_gtts_failures >= 2 and not force_pyttsx3:
                            print(f"\n   ⚠️ gTTS failed {consecutive_gtts_failures}x → Switching to edge-tts for all")
                            force_pyttsx3 = True  # Use as flag for "use fallback"
                        
                        try:
                            if EDGE_TTS_AVAILABLE:
                                result = self._generate_edge_tts(text, output_path, speed, verbose=False)
                                if result:
                                    success = True
                                    break
                            elif PYTTSX3_AVAILABLE:
                                result = self._generate_pyttsx3(text, output_path, speed, verbose=False)
                                if result:
                                    success = True
                                    break
                        except Exception as fb_err:
                            error_msg = f"Fallback failed: {str(fb_err)[:30]}"
                    
                    # Light backoff
                    if attempt < max_retries:
                        time.sleep(0.05)
            
            if success:
                results.append(output_path)
            else:
                failed.append((filename, error_msg))
            
            # Progress - more frequent updates (every 10 files or at key points)
            processed = skip_count + i
            elapsed = time.time() - start_time
            
            if show_progress:
                # Print every 10 files OR every second
                should_print = (i % 10 == 0) or (elapsed - getattr(self, '_last_progress_time', 0) >= 1)
                
                if should_print:
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (len(items_to_process) - i) / (rate + 0.001) if rate > 0 else 0
                    if force_pyttsx3:
                        service = "edge-tts"
                    else:
                        service = "gtts"
                    print(f"  [{processed}/{total}] ({rate:.1f} f/s) {service:10s} | ETA: {int(eta):4d}s")
                    self._last_progress_time = elapsed
        
        elapsed = time.time() - start_time
        print(f"\n✅ TTS xong: {len(results)}/{total} files ({int(elapsed)}s)")
        if failed:
            print(f"⚠️ Thất bại: {len(failed)}")
            for fname, err in failed[:5]:
                print(f"   - {fname}: {err}")
        
        return results


# ==========================================
# STANDALONE USAGE
# ==========================================
if __name__ == "__main__":
    # Test
    tts = TTSGenerator(service="gtts", language="vi")
    
    # Single generate
    tts.generate("Xin chào, tôi là Du Vũ", "test_001.wav")
    
    # Batch generate
    items = [
        {"text": "Xin chào", "filename": "0001.wav", "speed": 1.0},
        {"text": "Đây là test TTS", "filename": "0002.wav", "speed": 1.0},
        {"text": "Kết thúc test", "filename": "0003.wav", "speed": 0.9},
    ]
    tts.batch_generate(items)

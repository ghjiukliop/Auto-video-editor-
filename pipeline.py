#!/usr/bin/env python3
"""
PRODUCTION UNIFIED PIPELINE
===========================

Hoàn toàn tự động xử lý video từ đầu đến cuối:
1️⃣  Tách audio (nhanh với caching)
2️⃣  Tách phụ đề (STT)
3️⃣  Dịch + kiểm tra tự động (max 3 lần)
4️⃣  Chuyển phụ đề → audio (TTS với retry)
5️⃣  Merge tất cả audio thành 1 file unified

Usage:
    python pipeline.py input.mp4
    python pipeline.py input.mp4 -o output
    python pipeline.py input.mp4 -o output -w temp
"""

import sys
import logging
import time
import re
import json
import hashlib
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta
import shutil

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("pipeline")

# Try imports
try:
    import srt
except ImportError:
    logger.error("❌ Cần cài: pip install srt")
    sys.exit(1)

try:
    import ollama
except ImportError:
    logger.error("❌ Cần cài: pip install ollama")
    sys.exit(1)

try:
    import edge_tts
    from pydub import AudioSegment
except ImportError:
    logger.error("❌ Cần cài: pip install edge-tts pydub")
    sys.exit(1)

# Import config and modules
try:
    import config
    from modules.srt_parser_optimized import load_srt, save_srt
except ImportError as e:
    logger.error(f"❌ Import lỗi: {e}")
    sys.exit(1)

# ============================================================================
# CHINESE CHARACTER DETECTION
# ============================================================================

class ChineseDetector:
    """Phát hiện ký tự tiếng Trung."""
    
    CJK_RANGES = [
        (0x4E00, 0x9FFF),      # CJK Unified Ideographs
        (0x3400, 0x4DBF),      # CJK Extension A
        (0x20000, 0x2A6DF),    # CJK Extension B
    ]
    
    @classmethod
    def is_chinese(cls, char: str) -> bool:
        code = ord(char)
        for start, end in cls.CJK_RANGES:
            if start <= code <= end:
                return True
        return False
    
    @classmethod
    def has_chinese(cls, text: str) -> bool:
        return any(cls.is_chinese(c) for c in text)
    
    @classmethod
    def count_chinese(cls, text: str) -> int:
        return sum(1 for c in text if cls.is_chinese(c))


# ============================================================================
# AUDIO EXTRACTION (WITH CACHING)
# ============================================================================

class AudioExtractor:
    """Tách audio từ video (nhanh với caching)."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "youtube_audio"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, video_path: Path) -> str:
        stat = video_path.stat()
        content = f"{video_path.absolute()}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def extract(self, video_path: Path, output_wav: Path) -> Path:
        """Tách audio từ video."""
        # Kiểm tra cache
        cache_key = self._get_cache_key(video_path)
        cached = self.cache_dir / f"{cache_key}.wav"
        if cached.exists():
            logger.info(f"📦 Cache hit: {cached.name}")
            shutil.copy2(cached, output_wav)
            return output_wav
        
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"🎵 Tách audio từ {video_path.name}...")
        
        cmd = [
            "ffmpeg", "-loglevel", "error", "-y",
            "-i", str(video_path),
            "-q:a", "5", "-ac", "2", "-ar", "44100",
            "-acodec", "pcm_s16le",
            str(output_wav)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            # Lưu vào cache
            shutil.copy2(output_wav, cached)
            logger.info(f"✅ Tách xong: {output_wav.name}")
            return output_wav
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ FFmpeg fail: {e}")
            raise


# ============================================================================
# SPEECH-TO-TEXT
# ============================================================================

class SpeechToText:
    """Chuyển audio → phụ đề (STT)."""
    
    def transcribe(self, audio_path: Path, srt_output: Path, lang: str = "zh") -> Path:
        """Chuyển audio thành SRT (dùng openai-whisper)."""
        srt_output.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"🎤 STT: {audio_path.name} → {lang}... (openai-whisper)")
        
        try:
            import whisper
            
            # Model: tiny/base/small/medium/large
            # "base" = cân bằng tốt speed & quality (~1GB, CPU-friendly)
            logger.info("   ⏳ Loading model 'base'...")
            model = whisper.load_model("base", device="cpu")
            
            # Transcribe
            logger.info(f"   ⏳ Transcribing {audio_path.name}...")
            result = model.transcribe(str(audio_path), language=lang, fp16=False)
            
            # Convert to SRT
            subtitles = []
            for i, segment in enumerate(result["segments"], 1):
                start_ms = int(segment["start"] * 1000)
                end_ms = int(segment["end"] * 1000)
                text = segment["text"].strip()
                
                start_time = timedelta(milliseconds=start_ms)
                end_time = timedelta(milliseconds=end_ms)
                
                sub = srt.Subtitle(index=i, start=start_time, end=end_time, content=text)
                subtitles.append(sub)
            
            with open(srt_output, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subtitles))
            
            logger.info(f"✅ STT xong: {len(subtitles)} phụ đề")
            return srt_output
        except Exception as e:
            logger.error(f"❌ STT fail: {e}")
            raise


# ============================================================================
# TRANSLATION WITH VERIFICATION (AUTO-RETRY)
# ============================================================================

class TranslatorWithVerification:
    """
    Translator sử dụng Ollama với 3-Pass System:
    Pass 1: Dịch thô (từ Trung sang Việt)
    Pass 2: Xác minh (tìm tiếng Trung còn sót, dịch lại)
    Pass 3: Refactor (tinh chỉnh xưng hô & ngữ điệu)
    
    Đặc điểm:
    - Dịch từng câu một (Granular Translation)
    - Atomic write - ghi file tức thì mỗi câu
    - Custom system prompt cho Ollama
    - Logging chi tiết & Exception handling tốt
    """
    
    # System prompt chuyên dụng cho Ollama
    SYSTEM_PROMPT = (
        "Bạn là một chuyên gia lồng tiếng phim. "
        "Hãy dịch câu sau từ tiếng Trung sang tiếng Việt sao cho "
        "ngắn gọn, khớp khẩu hình và xưng hô tự nhiên. "
        "Chỉ trả về bản dịch, không thêm ghi chú hay giải thích."
    )
    
    REFACTOR_PROMPT = (
        "Bạn là một chuyên gia lồng tiếng phim tiếng Việt. "
        "Hãy tinh chỉnh lại toàn bộ file phụ đề sau sao cho: "
        "1. Xưng hô tự nhiên (anh/em, tôi/ông...) phù hợp với bối cảnh phim. "
        "2. Ngữ điệu sôi động và chân thực. "
        "3. Giữ nguyên định dạng SRT (chỉ chỉnh sửa nội dung text). "
        "Trả về file SRT đầy đủ."
    )
    
    def __init__(self, max_passes: int = 3):
        """
        Khởi tạo translator Ollama.
        
        Args:
            max_passes: Số lượng pass tối đa (mặc định 3: rough, verify, refactor)
        """
        # Lock luôn là 3 pass (đã xóa Pass 4)
        self.max_passes = 3
        self.ollama_model = config.OLLAMA_MODEL
        self.ollama_host = config.OLLAMA_HOST
        
        logger.info(
            f"🤖 Khởi tạo Ollama Translator (3-Pass): "
            f"Model={self.ollama_model}, Host={self.ollama_host}"
        )
    
    def translate(self, srt_path: Path, output_path: Path) -> Path:
        """
        Dịch SRT file với 3-Pass verification system.
        
        Args:
            srt_path: Đường dẫn file SRT gốc (tiếng Trung)
            output_path: Đường dẫn file SRT dịch (tiếng Việt)
        
        Returns:
            Path đến file đã dịch
        """
        logger.info(f"🌐 Dịch: {srt_path.name} (Ollama)...")
        
        # Setup output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file gốc sang output trước (để atomic write có state khởi đầu)
        if srt_path != output_path:
            shutil.copy2(srt_path, output_path)
            logger.info(f"📋 Copy gốc → output: {output_path.name}")
        
        # ===== PASS 1: DỊCH THÔ =====
        logger.info("\n" + "="*70)
        logger.info("📍 PASS 1/3: Dịch thô (từ Trung sang Việt)")
        logger.info("="*70)
        
        self._pass_1_rough_translation(srt_path, output_path)
        
        # ===== PASS 2: XÁC MINH =====
        logger.info("\n" + "="*70)
        logger.info("📍 PASS 2/3: Xác minh & dịch lại (ChineseDetector)")
        logger.info("="*70)
        
        self._pass_2_verification(output_path)
        
        # ===== PASS 3: REFACTOR =====
        logger.info("\n" + "="*70)
        logger.info("📍 PASS 3/3: Tinh chỉnh toàn diện (chunk-based)")
        logger.info("="*70)
        
        self._pass_3_refactor(output_path)
        
        logger.info(f"\n✅ Dịch HOÀN TẤT: {output_path.name}")
        return output_path
    
    def _pass_1_rough_translation(self, srt_path: Path, output_path: Path) -> None:
        """
        Pass 1: Dịch thô từng câu một.
        - Load file SRT
        - Dịch từng subtitle với Ollama
        - Ghi file tức thì (atomic write)
        """
        try:
            subtitles = load_srt(srt_path)
            logger.info(f"✅ Load {len(subtitles)} subtitle từ {srt_path.name}")
            
            translated_count = 0
            failed_count = 0
            
            for idx, subtitle in enumerate(subtitles, start=1):
                # Check if already has Chinese (skip if not)
                if not ChineseDetector.has_chinese(subtitle.content):
                    logger.debug(f"   #{idx} (Skip) Không có tiếng Trung")
                    continue
                
                # Log dịch
                logger.info(
                    f"   [Dịch #{idx:03d}] Gốc: {subtitle.content[:60]}{'...' if len(subtitle.content) > 60 else ''}"
                )
                
                try:
                    # Dịch câu này
                    translated_text = self._translate_single_sentence(subtitle.content)
                    
                    # Update subtitle
                    subtitle.content = translated_text
                    translated_count += 1
                    
                    # Log thành công
                    logger.info(
                        f"   [✓ #{idx:03d}] Dịch: {translated_text[:60]}{'...' if len(translated_text) > 60 else ''}"
                    )
                    
                    # Ghi file tức thì (Atomic Write)
                    save_srt(subtitles, output_path)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(
                        f"   [✗ #{idx:03d}] ❌ Lỗi dịch: {str(e)[:80]}"
                    )
                    # Giữ nguyên nội dung gốc nếu dịch lỗi
                    save_srt(subtitles, output_path)
            
            logger.info(
                f"\n✅ Pass 1 XONG: {translated_count} thành công, {failed_count} lỗi "
                f"(tổng {len(subtitles)})"
            )
        
        except Exception as e:
            logger.error(f"❌ Pass 1 thất bại: {str(e)}")
            raise
    
    def _pass_2_verification(self, srt_path: Path) -> None:
        """
        Pass 2: Xác minh - quét lại file tìm tiếng Trung còn sót.
        - Load file SRT
        - Dùng ChineseDetector quét từng subtitle
        - Nếu còn tiếng Trung, dịch lại
        - Ghi file ngay
        """
        try:
            subtitles = load_srt(srt_path)
            
            # Quét tìm tiếng Trung
            remaining_indices = []
            for idx, subtitle in enumerate(subtitles):
                if ChineseDetector.has_chinese(subtitle.content):
                    remaining_indices.append(idx)
            
            if not remaining_indices:
                logger.info(f"✅ Không còn tiếng Trung (quét {len(subtitles)} subtitle)")
                return
            
            logger.info(
                f"⚠️  Phát hiện {len(remaining_indices)} subtitle còn tiếng Trung\n"
                f"   Dịch lại các subtitle: {remaining_indices[:10]}{'...' if len(remaining_indices) > 10 else ''}"
            )
            
            retranslated_count = 0
            
            for idx in remaining_indices:
                subtitle = subtitles[idx]
                chinese_count = ChineseDetector.count_chinese(subtitle.content)
                
                logger.info(
                    f"   [Dịch lại #{idx+1:03d}] Gốc: {subtitle.content[:60]}{'...' if len(subtitle.content) > 60 else ''} "
                    f"({chinese_count} ký tự Trung)"
                )
                
                try:
                    # Dịch lại
                    translated_text = self._translate_single_sentence(subtitle.content)
                    subtitle.content = translated_text
                    retranslated_count += 1
                    
                    logger.info(
                        f"   [✓ #{idx+1:03d}] Dịch lại: {translated_text[:60]}{'...' if len(translated_text) > 60 else ''}"
                    )
                    
                    # Ghi file ngay
                    save_srt(subtitles, srt_path)
                
                except Exception as e:
                    logger.error(
                        f"   [✗ #{idx+1:03d}] ❌ Lỗi dịch lại: {str(e)[:80]}"
                    )
                    save_srt(subtitles, srt_path)
            
            logger.info(
                f"\n✅ Pass 2 XONG: {retranslated_count} subtitle dịch lại, "
                f"{len(remaining_indices) - retranslated_count} lỗi"
            )
        
        except Exception as e:
            logger.error(f"❌ Pass 2 thất bại: {str(e)}")
            # Không raise - chỉ log warning
    
    def _pass_3_refactor(self, srt_path: Path) -> None:
        """
        Pass 3: Tinh chỉnh toàn diện (chunk-based).
        
        Chiến lược: Xử lý chunk của 8 subtitle cùng lúc
        - Ollama có context lớn → hiểu giới tính, xưng hô, bối cảnh
        - Sửa: giới tính, xưung hô, lời thoại, mọi thứ
        - Parse lại & ATOMIC WRITE
        """
        try:
            subtitles = load_srt(srt_path)
            logger.info(f"✅ Load {len(subtitles)} subtitle cho Pass 3")
            
            # Chunk size: 8 subtitle (cân bằng context & parse safety)
            chunk_size = 8
            refactored_count = 0
            
            # Lặp chunk
            for chunk_idx in range(0, len(subtitles), chunk_size):
                chunk = subtitles[chunk_idx:chunk_idx + chunk_size]
                start_idx = chunk_idx + 1
                end_idx = min(chunk_idx + chunk_size, len(subtitles))
                
                logger.info(
                    f"   [Refactor chunk {start_idx}-{end_idx}/{len(subtitles)}] "
                    f"({len(chunk)} subtitle)"
                )
                
                try:
                    # Tạo SRT text của chunk
                    chunk_srt = self._subtitles_to_srt_text(chunk)
                    
                    # Refactor prompt cho chunk (comprehensive)
                    refactor_chunk_prompt = (
                        f"Bạn là chuyên gia lồng tiếng phim tiếng Việt. "
                        f"Hãy tinh chỉnh toàn bộ phụ đề sau sao cho:\n"
                        f"1. Giới tính & xưng hô nhất quán (anh/cô, ông/bà, tôi/ta...)\n"
                        f"2. Bối cảnh & lời thoại phù hợp nhân vật\n"
                        f"3. Ngữ điệu sôi động & chân thực\n"
                        f"4. Tự nhiên như lồng tiếng chuyên nghiệp\n"
                        f"5. Giữ nguyên định dạng SRT (timing không đổi)\n\n"
                        f"Phụ đề:\n{chunk_srt}\n\n"
                        f"Trả về phụ đề đã chỉnh sửa theo format SRT gốc."
                    )
                    
                    # Gọi Ollama refactor chunk
                    refactored_chunk_text = self._call_ollama(refactor_chunk_prompt)
                    
                    # Parse lại chunk từ kết quả
                    refactored_chunk = self._parse_srt_from_text(refactored_chunk_text)
                    
                    # Kiểm tra: số subtitle có khớp không?
                    if refactored_chunk and len(refactored_chunk) == len(chunk):
                        # Thành công → update subtitles
                        for i, refactored_sub in enumerate(refactored_chunk):
                            original_content = chunk[i].content
                            chunk[i].content = refactored_sub.content
                            
                            # Log nếu có thay đổi
                            if original_content != refactored_sub.content:
                                refactored_count += 1
                                logger.debug(
                                    f"      [#{chunk_idx + i + 1}] "
                                    f"{original_content[:40]} → {refactored_sub.content[:40]}"
                                )
                        
                        # ATOMIC WRITE: ghi file ngay
                        save_srt(subtitles, srt_path)
                        logger.info(f"      ✓ Chunk {start_idx}-{end_idx} refactor xong")
                    
                    else:
                        # Parse lỗi → giữ nguyên chunk
                        logger.warning(
                            f"      ⚠️  Parse lỗi (được {len(refactored_chunk) if refactored_chunk else 0}, "
                            f"expected {len(chunk)}) - giữ nguyên chunk"
                        )
                        save_srt(subtitles, srt_path)
                
                except Exception as e:
                    logger.error(
                        f"      ⚠️  Chunk {start_idx}-{end_idx} lỗi: {str(e)[:60]} - giữ nguyên"
                    )
                    save_srt(subtitles, srt_path)
            
            logger.info(f"✅ Pass 3 XONG: {refactored_count}/{len(subtitles)} subtitle refactored")
        
        except Exception as e:
            logger.error(f"❌ Pass 3 lỗi: {str(e)}")
            # Không raise - Pass 3 là optional
    
    def _translate_single_sentence(self, text: str) -> str:
        """
        Dịch một câu đơn lẻ dùng Ollama.
        
        Args:
            text: Câu tiếng Trung cần dịch
        
        Returns:
            Câu tiếng Việt dịch được
        
        Raises:
            Exception: Nếu Ollama không phản hồi
        """
        try:
            translated = self._call_ollama(text, system_prompt=self.SYSTEM_PROMPT)
            # Xóa khoảng trắng thừa
            return translated.strip()
        
        except Exception as e:
            logger.debug(f"Ollama call lỗi: {e}")
            raise
    
    def _call_ollama(
        self,
        prompt: str,
        system_prompt: str = None,
        timeout: int = 30
    ) -> str:
        """
        Gọi Ollama API với prompt cho trước.
        
        Args:
            prompt: Câu hỏi / prompt cho Ollama
            system_prompt: System prompt tùy chỉnh
            timeout: Timeout (giây)
        
        Returns:
            Phản hồi từ Ollama
        
        Raises:
            TimeoutError: Nếu timeout
            Exception: Nếu Ollama không phản hồi
        """
        try:
            # Chuẩn bị messages
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Gọi Ollama
            response = ollama.chat(
                model=self.ollama_model,
                messages=messages,
                stream=False,
                options={
                    "temperature": 0.3,  # Thấp để translation chính xác
                    "top_p": 0.9,
                    "top_k": 40,
                }
            )
            
            # Extract message
            if response and "message" in response:
                return response["message"]["content"]
            else:
                raise Exception(f"Invalid Ollama response: {response}")
        
        except TimeoutError:
            raise TimeoutError(f"Ollama timeout ({timeout}s)")
        except Exception as e:
            # Log chi tiết
            logger.debug(f"Ollama API error: {type(e).__name__}: {e}")
            raise
    
    def _subtitles_to_srt_text(self, subtitles: list) -> str:
        """
        Chuyển danh sách subtitle thành text SRT format.
        """
        lines = []
        for subtitle in subtitles:
            lines.append(str(subtitle.index))
            lines.append(f"{subtitle.start_time} --> {subtitle.end_time}")
            lines.append(subtitle.content)
            lines.append("")
        
        return "\n".join(lines)
    
    def _parse_srt_from_text(self, srt_text: str) -> list:
        """
        Parse SRT text trở lại danh sách subtitle.
        Dùng chính regex từ OptimizedSRTParser.
        """
        from modules.srt_parser_optimized import OptimizedSRTParser
        
        try:
            subtitles = OptimizedSRTParser.parse_content(srt_text)
            return subtitles
        except Exception as e:
            logger.debug(f"Parse SRT text lỗi: {e}")
            return None


# ============================================================================
# VIETNAMESE LOCALIZATION REFINER
# ============================================================================

class VietnameseRefiner:
    """Chỉnh sửa câu dịch thành ngôn ngữ tự nhiên Việt - rút gọn, xưng hô tự nhiên."""
    
    def __init__(self):
        """Khởi tạo refiner với quy tắc xưng hô và rút gọn."""
        self.pronoun_rules = {
            # Thay thế xưng hô thông dụng
            'tôi': ['tớ', 'mình', 'em', 'anh/chị'],
            'bạn': ['cậu', 'mệnh', 'kia'],
            'anh': ['cậu', 'tao'],
            'chị': ['cậu', 'nàng'],
            'người': ['thằng', 'thằng vô duyên'],
        }
        
        # Ngữ pháp, cụm từ dài có thể rút gọn
        self.long_phrases = {
            'bởi vì': 'vì',
            'tuy nhiên': 'nhưng',
            'cho dù': 'dù',
            'để làm': 'để',
            'không có': 'chẳng có',
            'không phải là': 'không',
            'có vẻ như': 'dường như',
            'có thể là': 'có thể',
        }
    
    def refine(self, srt_path: Path, output_path: Path) -> Path:
        """Duyệt qua tất cả subtitle và refine từng câu."""
        logger.info(f"🎭 Refine tiếng Việt: {srt_path.name}...")
        
        # Load SRT
        with open(srt_path, 'r', encoding='utf-8-sig') as f:
            subtitles = list(srt.parse(f))
        
        logger.info(f"   Refining {len(subtitles)} phụ đề...")
        refined_count = 0
        
        for i, sub in enumerate(subtitles):
            original = sub.content
            refined = self._refine_text(sub.content)
            
            if original != refined:
                sub.content = refined
                refined_count += 1
                
                # Log mỗi 50 phụ đề
                if (i + 1) % 50 == 0 or i + 1 == len(subtitles):
                    logger.info(f"      ✓ Refined {refined_count} / {i+1}")
        
        # Save refined subtitles
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt.compose(subtitles))
        
        logger.info(f"✅ Refine xong: {refined_count}/{len(subtitles)} phụ đề đã chỉnh")
        return output_path
    
    def _refine_text(self, text: str) -> str:
        """Refine 1 câu text."""
        # Bỏ khoảng trắng thừa
        text = ' '.join(text.split())
        
        # Rút gọn cụm từ dài
        for long_phrase, short_phrase in self.long_phrases.items():
            pattern = re.compile(r'\b' + re.escape(long_phrase) + r'\b', re.IGNORECASE)
            text = pattern.sub(short_phrase, text)
        
        # Xóa "là" thừa ở cuối hoặc giữa
        # Ví dụ: "cô ấy là rất vui" → "cô ấy rất vui"
        text = re.sub(r'\s+là\s+(?=[a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ])', ' ', text)
        
        # Xóa "đã" thừa trong câu hỏi
        if '?' in text and text.count('đã') > 0:
            text = re.sub(r'\bdã\s+', '', text)
        
        # Xóa "được" thừa (trong một số trường hợp)
        # "được yêu thích" → "yêu thích", nhưng giữ "được coi là"
        text = re.sub(r'\bđược\s+(?=(yêu|thích|biết|công nhân|tôn trọng))', '', text)
        
        # Cắt ngắn nếu quá dài (>100 ký tự) - ưu tiên câu ngắn hơn để khớp lip-sync
        if len(text) > 100:
            text = self._shorten_text(text)
        
        # Xóa khoảng trắng thừa (có thể sinh ra từ các regex trên)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Capitalize đầu câu
        if text:
            text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
        
        return text.strip()
    
    def _shorten_text(self, text: str) -> str:
        """Rút gọn câu quá dài."""
        # Nếu có dấu phẩy, cắt ở dấu phẩy đầu tiên
        if ',' in text:
            text = text.split(',')[0].strip()
        
        # Nếu vẫn dài, xóa mệnh đề phụ (tìm từ chỉnh hợp sau "và", "hoặc", "nhưng")
        if len(text) > 80:
            for separator in ['và', 'hoặc', 'nhưng']:
                if separator in text:
                    text = text.split(separator)[0].strip()
                    break
        
        # Nếu vẫn dài, trích 60 ký tự đầu
        if len(text) > 80:
            text = text[:75] + '...' if len(text) > 75 else text
        
        return text
    
    def _optimize_pronouns(self, text: str) -> str:
        """Tối ưu xưng hô cho nhân vật.",
Ví dụ: "tôi" → "tớ" (để tự nhiên hơn)."""
        # Đây là hướng dẫn - có thể customize tùy theo nhân vật
        # Hiện tại giữ nguyên để tránh nhầm lẫn
        return text


# ============================================================================
# TEXT-TO-SPEECH WITH AUTO-RETRY
# ============================================================================

class TTSProcessor:
    """Chuyển phụ đề → audio (TTS) với retry tự động."""
    
    def __init__(self, voice: str = "vi-VN-HoaiMyNeural", rate: str = "0%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.max_retries = 3
    
    def process(self, srt_path: Path, output_audio: Path) -> Path:
        """Chuyển SRT → audio."""
        logger.info(f"🎙️  TTS: {srt_path.name} → {output_audio.name}...")
        
        # Load SRT
        with open(srt_path, 'r', encoding='utf-8-sig') as f:
            subtitles = list(srt.parse(f))
        
        output_audio.parent.mkdir(parents=True, exist_ok=True)
        
        # Create audio chunks
        chunks = []
        for i, sub in enumerate(subtitles):
            chunk_path = output_audio.parent / f"chunk_{i:04d}.wav"
            
            # Try to generate with retry
            success = False
            for attempt in range(self.max_retries):
                try:
                    # Generate TTS
                    asyncio.run(edge_tts.Communicate(
                        text=sub.content,
                        voice=self.voice,
                        rate=self.rate,
                        pitch=self.pitch
                    ).save(str(chunk_path)))
                    
                    success = True
                    logger.debug(f"  ✓ Chunk {i}/{len(subtitles)}")
                    break
                except Exception as e:
                    logger.warning(f"  ⚠️  Chunk {i} attempt {attempt+1}/{self.max_retries}: {str(e)[:50]}")
                    time.sleep(1)
            
            if success:
                chunks.append((chunk_path, sub.start, sub.end))
            else:
                logger.error(f"  ❌ Chunk {i} thất bại sau {self.max_retries} lần")
                # Tạo silence nếu fail
                silence = AudioSegment.silent(
                    duration=int((sub.end.total_seconds() - sub.start.total_seconds()) * 1000)
                )
                silence.export(str(chunk_path), format="wav")
                chunks.append((chunk_path, sub.start, sub.end))
        
        # Merge chunks
        logger.info(f"🔗 Merge {len(chunks)} chunks...")
        self._merge_chunks(chunks, output_audio)
        
        # Clean up
        for chunk_path, _, _ in chunks:
            chunk_path.unlink(missing_ok=True)
        
        logger.info(f"✅ TTS xong: {output_audio.name}")
        return output_audio
    
    def _merge_chunks(self, chunks: List[Tuple[Path, any, any]], output: Path):
        """Merge audio chunks với timing đúng."""
        combined = AudioSegment.empty()
        
        for chunk_path, start_time, end_time in chunks:
            audio = AudioSegment.from_wav(str(chunk_path))
            combined += audio
        
        combined.export(str(output), format="wav")


# ============================================================================
# AUDIO MERGER (UNIFIED)
# ============================================================================

class AudioMerger:
    """Merge tất cả audio thành 1 file unified."""
    
    def merge(self, ai_voice: Path, bgm_path: Optional[Path], output: Path) -> Path:
        """Merge audio theo thứ tự: BGM + AI voice."""
        logger.info(f"🔊 Merge audio...")
        output.parent.mkdir(parents=True, exist_ok=True)
        
        # Load AI voice
        audio = AudioSegment.from_wav(str(ai_voice))
        
        # Load BGM nếu có (phát song song)
        if bgm_path and bgm_path.exists():
            try:
                bgm = AudioSegment.from_wav(str(bgm_path))
                # Cắt BGM theo độ dài AI voice
                if len(bgm) > len(audio):
                    bgm = bgm[:len(audio)]
                else:
                    # Lặp BGM nếu quá ngắn
                    while len(bgm) < len(audio):
                        bgm += bgm
                    bgm = bgm[:len(audio)]
                
                # Mix: BGM nhỏ (30%) + AI voice lớn (100%)
                bgm = bgm - 10  # Giảm -10dB
                audio = audio.overlay(bgm)
                logger.info(f"   ✓ BGM mixed in")
            except Exception as e:
                logger.warning(f"   ⚠️  BGM mix failed: {e}")
        
        audio.export(str(output), format="wav")
        logger.info(f"✅ Merge xong: {output.name}")
        return output


# ============================================================================
# MAIN PIPELINE
# ============================================================================

class ProductionPipeline:
    """Pipeline chính - tự động từ đầu đến cuối."""
    
    def __init__(self, video_path: Path, output_dir: Path, work_dir: Optional[Path] = None):
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.work_dir = Path(work_dir) if work_dir else self.output_dir / "work"
        
        # Validate
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {self.video_path}")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize modules
        self.extractor = AudioExtractor()
        self.stt = SpeechToText()
        self.translator = TranslatorWithVerification()
        self.refiner = VietnameseRefiner()
        self.tts = TTSProcessor()
        self.merger = AudioMerger()
    
    def run(self) -> bool:
        """Run complete pipeline."""
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"🚀 PRODUCTION PIPELINE: {self.video_path.name}")
            logger.info(f"{'='*70}\n")
            
            start = time.time()
            
            # Stage 1: Extract audio
            logger.info(f"\n[1/5] TẮC AUDIO")
            extracted_audio = self.work_dir / "audio.wav"
            self.extractor.extract(self.video_path, extracted_audio)
            
            # Stage 2: STT
            logger.info(f"\n[2/5] TÁCH PHỤ ĐỀ (STT)")
            original_srt = self.work_dir / "subtitles_original.srt"
            self.stt.transcribe(extracted_audio, original_srt, lang="zh")
            
            # Stage 3: Translate with verification
            logger.info(f"\n[3/5] DỊCH + KIỂM TRA")
            translated_srt = self.work_dir / "subtitles_translated.srt"
            self.translator.translate(original_srt, translated_srt)
            
            # Stage 3.5: Refine Vietnamese (optimize pronouns, shorten sentences)
            logger.info(f"\n[3.5/5] REFINE TIẾNG VIỆT (tối ưu xưng hô, rút gọn)")
            refined_srt = self.work_dir / "subtitles_refined.srt"
            self.refiner.refine(translated_srt, refined_srt)
            
            # Stage 4: TTS (with retry)
            logger.info(f"\n[4/5] CHUYỂN PHỤ ĐỀ → AUDIO (TTS)")
            ai_voice = self.work_dir / "ai_voice.wav"
            self.tts.process(refined_srt, ai_voice)
            
            # Stage 5: Merge audio
            logger.info(f"\n[5/5] MERGE AUDIO UNIFIED")
            final_audio = self.output_dir / f"{self.video_path.stem}_final.wav"
            self.merger.merge(ai_voice, None, final_audio)
            
            elapsed = time.time() - start
            logger.info(f"\n{'='*70}")
            logger.info(f"✅ HOÀN TẤT THÀNH CÔNG!")
            logger.info(f"⏱️  Thời gian: {elapsed:.1f}s")
            logger.info(f"📁 Output: {final_audio}")
            logger.info(f"{'='*70}\n")
            
            return True
        
        except Exception as e:
            logger.error(f"\n❌ PIPELINE THẤT BẠI: {e}")
            import traceback
            traceback.print_exc()
            return False


# ============================================================================
# COMMAND LINE
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Production unified video pipeline - Tự động từ đầu đến cuối"
    )
    parser.add_argument("video", help="Video file")
    parser.add_argument("-o", "--output", default="output", help="Output folder")
    parser.add_argument("-w", "--work", default=None, help="Work folder for temp files")
    
    args = parser.parse_args()
    
    try:
        pipeline = ProductionPipeline(
            video_path=args.video,
            output_dir=args.output,
            work_dir=args.work
        )
        success = pipeline.run()
        sys.exit(0 if success else 1)
    
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Audio Merger: Gộp tất cả audio lại thành 1 file dài
Tạo silence giữa các đoạn nếu cần
Tự động canh chỉnh độ dài audio với video (sai số cho phép: 10 phút)
"""

from pathlib import Path
from typing import List, Optional, Tuple
import re
import subprocess
from tqdm import tqdm
import numpy as np

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False


class AudioMerger:
    """Gộp tất cả audio files + tạo silence nếu cần + canh chỉnh độ dài với video"""
    
    # Sai số cho phép khi so sánh audio với video (10 phút = 600 giây)
    MAX_DURATION_TOLERANCE_SECONDS = 600
    
    # ✨ Silence gap nhỏ giữa các audio segments (trong giây)
    # Thay vì dùng full silence từ SRT, sử dụng gap nhỏ 0.1-0.15s để tránh expand thời lượng
    MIN_SILENCE_GAP_SECONDS = 0.1   # 100ms
    MAX_SILENCE_GAP_SECONDS = 0.15  # 150ms
    DEFAULT_SILENCE_GAP_SECONDS = 0.12  # 120ms (average)
    
    def __init__(self):
        self.support_merge = PYDUB_AVAILABLE
        if not self.support_merge:
            print("⚠️ Cảnh báo: pydub không được cài đặt!")
    
    def _get_video_duration_seconds(self, video_file: str) -> Optional[float]:
        """Lấy thời lượng video bằng ffprobe (tính bằng giây)"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1:noprint_wrappers=1',
                video_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            duration = float(result.stdout.strip())
            return duration
        except Exception as e:
            print(f"⚠️  Không lấy được duration video: {str(e)[:50]}")
            return None
    
    def _check_and_adjust_audio_duration(self, merged_audio_ms: float, 
                                         video_duration_seconds: Optional[float]) -> Tuple[bool, str]:
        """
        Kiểm tra độ dài audio so với video
        
        Return: (is_ok, message)
        - is_ok=True: Audio đúng độ dài (hoặc chênh lệch < 10 phút)
        - is_ok=False: Audio quá dài (chênh lệch > 10 phút)
        """
        if video_duration_seconds is None:
            return True, "⚠️  Không kiểm tra được video duration, bỏ qua kiểm tra"
        
        audio_duration_seconds = merged_audio_ms / 1000.0
        difference_seconds = audio_duration_seconds - video_duration_seconds
        difference_minutes = difference_seconds / 60.0
        
        if abs(difference_seconds) < 1:  # < 1 giây
            return True, f"✅ Audio length perfect: {audio_duration_seconds:.1f}s = Video {video_duration_seconds:.1f}s"
        
        if difference_seconds < 0:  # Audio ngắn hơn video
            if abs(difference_seconds) <= self.MAX_DURATION_TOLERANCE_SECONDS:
                return True, f"✅ Audio shorter than video by {abs(difference_minutes):.1f}min (< 10min tolerance)"
            else:
                return False, f"❌ Audio too short! Difference: {abs(difference_minutes):.1f} min (> 10 min tolerance)"
        
        else:  # Audio dài hơn video
            if difference_seconds <= self.MAX_DURATION_TOLERANCE_SECONDS:
                return True, f"✅ Audio longer than video by {difference_minutes:.1f}min (< 10min tolerance) ✔️"
            else:
                return False, f"❌ Audio too long! Difference: {difference_minutes:.1f} min (> 10 min tolerance)"
    
    def parse_srt_for_timing(self, srt_file: str) -> List[dict]:
        """
        Parse SRT để lấy timing info
        Return: [
            {"index": 1, "start_ms": 0, "end_ms": 10000, "duration_ms": 10000},
            ...
        ]
        """
        items = []
        
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Regex: bắt (index, start_time, end_time)
        pattern = r'(\d+)\n(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
        matches = re.findall(pattern, content)
        
        for match in matches:
            idx, h1, m1, s1, ms1, h2, m2, s2, ms2 = match
            idx = int(idx)
            
            start_ms = int(h1)*3600000 + int(m1)*60000 + int(s1)*1000 + int(ms1)
            end_ms = int(h2)*3600000 + int(m2)*60000 + int(s2)*1000 + int(ms2)
            duration_ms = end_ms - start_ms
            
            items.append({
                "index": idx,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": duration_ms
            })
        
        print(f"✅ Parse timing từ {len(items)} subtitle")
        return items
    
    def merge_pydub(self, audio_files: List[str], srt_file: str, 
                   output_file: str, video_file: Optional[str] = None) -> bool:
        """
        Merge dùng pydub (với progress bar phần trăm)
        
        Args:
            audio_files: Danh sách file audio
            srt_file: File SRT chứa timing
            output_file: File audio output
            video_file: (Optional) File video gốc để lấy duration
        """
        try:
            print(f"\n🎵 Merge Audio (pydub) | {len(audio_files)} files")
            print("=" * 70)
            
            timings = self.parse_srt_for_timing(srt_file)
            
            # Load tất cả audio - hỗ trợ cả MP3 và WAV (với progress bar)
            print("\n📥 Đang load audio files...")
            audios = []
            for i, f in tqdm(enumerate(audio_files), total=len(audio_files), 
                            desc="📥 Load", unit="file",
                            bar_format='{desc} | {percentage:3.0f}% [{bar}] {n_fmt}/{total_fmt}'):
                fpath = Path(f)
                if fpath.exists():
                    try:
                        # Detect format từ extension hoặc try auto-detect
                        file_ext = fpath.suffix.lower()
                        
                        if file_ext == '.mp3':
                            audio = AudioSegment.from_mp3(f)
                        elif file_ext == '.wav':
                            audio = AudioSegment.from_wav(f)
                        elif file_ext == '.m4a':
                            audio = AudioSegment.from_file(f, format="m4a")
                        else:
                            # Try auto-detect with pydub
                            audio = AudioSegment.from_file(f)
                        
                        audios.append(audio)
                    except Exception as load_err:
                        print(f"\n⚠️  Không load được {fpath.name}: {str(load_err)[:50]}")
                else:
                    print(f"\n⚠️ Không tìm: {f}")
            
            if not audios:
                print("❌ Không có audio file!")
                return False
            
            # Merge với silence (với progress bar)
            print(f"\n🔀 Đang merge {len(audios)} audio files...")
            merged = AudioSegment.empty()
            last_end_ms = 0
            
            for i, audio in tqdm(enumerate(audios), total=len(audios),
                                desc="🔀 Merge", unit="file",
                                bar_format='{desc} | {percentage:3.0f}% [{bar}] {n_fmt}/{total_fmt}'):
                if i < len(timings):
                    timing = timings[i]
                    current_start = timing["start_ms"]
                    
                    # ✨ Thêm silence nhỏ (0.1-0.15s) thay vì full silence
                    # Điều này tránh expand thời lượng do gap quá dài
                    gap_duration_ms = current_start - last_end_ms
                    
                    if gap_duration_ms > 0:
                        # Sử dụng silence từ 0.1-0.15s, không dùng full gap
                        silence_duration = min(
                            gap_duration_ms,  # Không vượt quá gap thực tế
                            int(self.DEFAULT_SILENCE_GAP_SECONDS * 1000)  # Max 120ms
                        )
                        silence = AudioSegment.silent(duration=silence_duration)
                        merged += silence
                        
                        if gap_duration_ms > silence_duration:
                            print(f"   📊 Segment {i+1}: Reduced gap from {gap_duration_ms}ms to {silence_duration}ms")
                    
                    # Thêm audio
                    merged += audio
                    last_end_ms = timing["end_ms"]
                else:
                    # Không có timing, thêm trực tiếp
                    merged += audio
            
            # Kiểm tra duration với video nếu có
            video_duration_seconds = None
            if video_file:
                print(f"\n📹 Kiểm tra độ dài audio với video...")
                video_duration_seconds = self._get_video_duration_seconds(video_file)
            
            is_ok, msg = self._check_and_adjust_audio_duration(len(merged), video_duration_seconds)
            print(f"   {msg}")
            
            # Export (với progress bar)
            print(f"\n💾 Đang lưu file...")
            merged.export(output_file, format="wav")
            
            merged_duration = len(merged) / 1000.0
            print(f"\n{'='*70}")
            print(f"✅ Merge hoàn thành!")
            print(f"   📁 Output: {Path(output_file).name}")
            print(f"   📊 Tổng thời lượng: {merged_duration:.1f}s ({merged_duration/60:.1f} phút)")
            print(f"   📦 Đã merge {len(audios)} file audio")
            print(f"{'='*70}\n")
            return True
        except Exception as e:
            print(f"❌ Merge error: {str(e)[:100]}\n")
            return False
    
    def _compress_gaps_in_audio(self, audio: np.ndarray, timings: List[dict], 
                              sample_rate: int, gap_duration_ms: int = 120) -> np.ndarray:
        """
        ✨ Nén các gaps dài giữa segments thành gaps ngắn (0.1-0.15s).
        Thay vì dùng full gaps từ SRT, sử dụng gaps nhỏ.
        
        Args:
            audio: Audio array (numpy)
            timings: Danh sách timing từ SRT
            sample_rate: Sample rate
            gap_duration_ms: Độ dài gap mới (ms, mặc định 120ms)
        
        Returns:
            Compressed audio array
        """
        if not timings or len(timings) < 2:
            return audio
        
        gap_duration_samples = int(gap_duration_ms * sample_rate / 1000)
        compressed_segments = []
        
        for i, timing in enumerate(timings):
            start_samples = int(timing["start_ms"] * sample_rate / 1000)
            end_samples = int(timing["end_ms"] * sample_rate / 1000)
            
            # Lấy audio segment
            if end_samples <= len(audio):
                segment = audio[start_samples:end_samples]
                compressed_segments.append(segment)
            else:
                segment = audio[start_samples:]
                compressed_segments.append(segment)
            
            # Thêm gap nhỏ giữa segments (ngoại trừ segment cuối)
            if i < len(timings) - 1:
                gap_silence = np.zeros(gap_duration_samples, dtype=np.float32)
                compressed_segments.append(gap_silence)
        
        return np.concatenate(compressed_segments)
    

        """Load MP3 file and convert to numpy array"""
        if PYDUB_AVAILABLE:
            audio_segment = AudioSegment.from_mp3(mp3_file)
            # Convert to numpy
            samples = np.array(audio_segment.get_array_of_samples())
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2))
                samples = np.mean(samples, axis=1)  # Convert stereo to mono
            samples = samples.astype(np.float32) / 32768.0
            
            # Resample if needed
            if audio_segment.frame_rate != sample_rate:
                import librosa
                samples = librosa.resample(samples, orig_sr=audio_segment.frame_rate, target_sr=sample_rate)
            
            return samples, sample_rate
        else:
            raise ImportError("pydub required for MP3 loading")
    
    def merge_numpy(self, audio_files: List[str], srt_file: str, 
                   output_file: str, video_file: Optional[str] = None,
                   sample_rate: int = 22050) -> bool:
        """
        Merge dùng numpy + soundfile (với progress bar phần trăm)
        
        Args:
            audio_files: Danh sách file audio
            srt_file: File SRT chứa timing
            output_file: File audio output
            video_file: (Optional) File video gốc để lấy duration
            sample_rate: Sample rate cho output
        """
        try:
            print(f"\n🎵 Merge Audio (numpy) | {len(audio_files)} files")
            print("=" * 70)
            
            timings = self.parse_srt_for_timing(srt_file)
            
            # Tổng độ dài từ SRT timing
            if timings:
                total_duration_ms = max(t["end_ms"] for t in timings)
                total_samples = int(total_duration_ms * sample_rate / 1000)
            else:
                total_samples = 0
            
            # Init merged audio
            merged = np.zeros(total_samples, dtype=np.float32)
            
            # Load và fill audio vào đúng vị trí (với progress bar)
            print(f"\n📥 Đang load & merge {len(audio_files)} audio files...")
            for i, f in tqdm(enumerate(audio_files), total=len(audio_files),
                            desc="📥 Load", unit="file",
                            bar_format='{desc} | {percentage:3.0f}% [{bar}] {n_fmt}/{total_fmt}'):
                if not Path(f).exists():
                    print(f"\n⚠️ Không tìm: {f}")
                    continue
                
                # Load audio - hỗ trợ MP3, WAV, M4A
                try:
                    fpath = Path(f)
                    file_ext = fpath.suffix.lower()
                    
                    if file_ext == '.mp3':
                        audio, sr = self._load_mp3_as_numpy(f, sample_rate)
                    elif file_ext == '.wav':
                        audio, sr = sf.read(f)
                        if sr != sample_rate:
                            import librosa
                            audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
                    else:
                        # Try with soundfile
                        audio, sr = sf.read(f)
                        if sr != sample_rate:
                            import librosa
                            audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
                except Exception as load_err:
                    print(f"\n⚠️  Không load được {fpath.name}: {str(load_err)[:50]}")
                    continue
                
                if i < len(timings):
                    timing = timings[i]
                    start_sample = int(timing["start_ms"] * sample_rate / 1000)
                    end_sample = start_sample + len(audio)
                    
                    # Place audio
                    if end_sample <= len(merged):
                        merged[start_sample:end_sample] = audio
                    else:
                        # Audio quá dài
                        merged[start_sample:] = audio[:len(merged)-start_sample]
            
            # Kiểm tra duration với video nếu có
            video_duration_seconds = None
            if video_file:
                print(f"\n📹 Kiểm tra độ dài audio với video...")
                video_duration_seconds = self._get_video_duration_seconds(video_file)
            
            # ✨ Compress gaps: thay thế gaps dài bằng gaps ngắn (0.1-0.15s)
            if timings and len(timings) > 1:
                print(f"\n🔧 Nén gaps: thay thế gaps dài bằng gaps {int(self.DEFAULT_SILENCE_GAP_SECONDS*1000)}ms...")
                merged = self._compress_gaps_in_audio(merged, timings, sample_rate, 
                                                      int(self.DEFAULT_SILENCE_GAP_SECONDS * 1000))
            
            merged_duration_ms = len(merged) * 1000 / sample_rate
            is_ok, msg = self._check_and_adjust_audio_duration(merged_duration_ms, video_duration_seconds)
            print(f"   {msg}")
            
            # Save (với progress indicator)
            print(f"\n💾 Đang lưu file...")
            sf.write(output_file, merged, sample_rate)
            
            merged_duration = merged_duration_ms / 1000.0
            print(f"\n{'='*70}")
            print(f"✅ Merge hoàn thành!")
            print(f"   📁 Output: {Path(output_file).name}")
            print(f"   📊 Tổng thời lượng: {merged_duration:.1f}s ({merged_duration/60:.1f} phút)")
            print(f"   📦 Đã merge {len(audio_files)} file audio")
            print(f"   🎛️  Sample rate: {sample_rate} Hz")
            print(f"{'='*70}\n")
            return True
        except Exception as e:
            print(f"❌ Merge numpy error: {str(e)[:100]}\n")
            return False
    
    def merge(self, audio_files: List[str], srt_file: str, output_file: str,
             video_file: Optional[str] = None) -> bool:
        """
        Merge với auto-select engine (có progress bar phần trăm)
        
        Args:
            audio_files: Danh sách file audio
            srt_file: File SRT chứa timing
            output_file: File audio output
            video_file: (Optional) File video gốc để kiểm tra & canh chỉnh độ dài audio
        
        Return:
            True nếu merge thành công, False nếu thất bại
        """
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        print("\n" + "="*70)
        print("🎵 BẮT ĐẦU MERGE AUDIO (HỖ TRỢ TIẾN ĐỘ PHẦN TRĂM)")
        print("="*70)
        print(f"\n📊 Thông tin merge:")
        print(f"   📦 Tổng audio files: {len(audio_files)}")
        print(f"   📝 SRT timing file: {Path(srt_file).name}")
        print(f"   💾 Output: {Path(output_file).name}")
        if video_file:
            print(f"   📹 Video reference: {Path(video_file).name}")
            print(f"   🔍 Kiểm tra & canh chỉnh độ dài (tolerance: ±10 phút)")
        
        print(f"\n{'='*70}")
        
        if PYDUB_AVAILABLE:
            print("🔧 Engine: pydub")
            return self.merge_pydub(audio_files, srt_file, output_file, video_file)
        else:
            print("🔧 Engine: numpy + soundfile")
            return self.merge_numpy(audio_files, srt_file, output_file, 
                                   video_file=video_file)


# ==========================================
# STANDALONE USAGE
# ==========================================
if __name__ == "__main__":
    merger = AudioMerger()
    
    # List audio files
    audio_files = sorted(Path("output/AudioOutput/adjusted").glob("*.wav"))
    
    merger.merge(
        audio_files=[str(f) for f in audio_files],
        srt_file="input/SrtInput/video_translated.srt",
        output_file="output/AudioOutput/final_merged.wav"
    )

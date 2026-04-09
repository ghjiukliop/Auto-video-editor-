import re
from dataclasses import dataclass
from typing import List


@dataclass
class SRTSegment:
    index: int
    start_ms: int
    end_ms: int
    text: str


def ms_to_srt_time(ms: int) -> str:
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1_000
    milliseconds = ms % 1_000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def srt_time_to_ms(time_str: str) -> int:
    cleaned = time_str.replace(".", ",")
    match = re.match(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$", cleaned)
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {time_str}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def segments_to_srt(segments: List[dict]) -> str:
    lines: List[str] = []
    for i, seg in enumerate(segments, start=1):
        start_ms = int(float(seg["start"]) * 1000)
        end_ms = int(float(seg["end"]) * 1000)
        text = str(seg["text"]).strip()
        if not text:
            continue
        lines.extend(
            [
                str(i),
                f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}",
                text,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def parse_srt(srt_text: str) -> List[SRTSegment]:
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n"
        r"(.*?)(?=\n{2,}|\Z)",
        flags=re.DOTALL,
    )
    segments: List[SRTSegment] = []
    for match in pattern.finditer(srt_text.strip()):
        idx = int(match.group(1))
        start_ms = srt_time_to_ms(match.group(2))
        end_ms = srt_time_to_ms(match.group(3))
        text = re.sub(r"\s+", " ", match.group(4)).strip()
        if not text or end_ms <= start_ms:
            continue
        segments.append(SRTSegment(index=idx, start_ms=start_ms, end_ms=end_ms, text=text))
    return segments

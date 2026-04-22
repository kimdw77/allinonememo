"""
services/transcriber.py — 음성 파일 텍스트 변환 (OpenAI Whisper API)
"""
import io
import logging

logger = logging.getLogger(__name__)


def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """
    음성 파일을 텍스트로 변환 (OpenAI Whisper API).
    OPENAI_API_KEY 미설정 시 빈 문자열 반환.
    """
    from config import settings
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY 미설정 — 음성 인식 건너뜀")
        return ""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "ogg"
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=(f"voice.{ext}", io.BytesIO(audio_bytes)),
            language="ko",
        )
        text = transcript.text.strip()
        logger.info("Whisper 변환 완료: %d자", len(text))
        return text

    except Exception as e:
        logger.error("Whisper 음성 인식 실패: %s", e)
        return ""

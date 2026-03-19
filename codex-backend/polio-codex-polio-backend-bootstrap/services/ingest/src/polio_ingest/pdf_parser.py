from __future__ import annotations

from pathlib import Path
import re

from pypdf import PdfReader

from polio_ingest.models import ParsedChunkPayload, ParsedDocumentPayload

TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = {".pdf", *TEXT_EXTENSIONS}


def _apply_neis_masking(text: str) -> str:
    """
    나이스 생기부(학교생활기록부 II)의 민감 정보(PII)를 비식별화합니다.
    (블라인드 평가 기준 준수)
    """
    if not text:
        return text

    # 1. 주민등록번호 (000000-0000000)
    text = re.sub(r"\b\d{6}\s*[-]?\s*[1-4]\d{6}\b", "[주민번호_MASKED]", text)
    
    # 2. 성명 (생기부 특성상 띄어쓰기가 포함된 경우가 많음 "성 명 : 홍 길 동")
    # '성명'이라는 단어 근처에 있는 2~5글자의 한글을 블라인드 처리
    text = re.sub(r"(성\s*명\s*[:]?\s*)([가-힣\s]{2,8})(?=\n|\s|$)", r"\1[이름_MASKED]", text)
    
    # 3. 학교명 (출신 고등학교 노출 방지 - OO고, OO고등학교)
    text = re.sub(r"[가-힣]{2,10}(고등학교|과학고|외국어고|국제고|영재고|마이스터고|예술고|체육고)\b", "[학교명_MASKED]", text)
    
    # 4. 가족 이름 및 인적사항
    text = re.sub(r"(부|모|보호자)\s*[:]?\s*([가-힣\s]{2,8})(?=\n|\s|$)", r"\1[가족이름_MASKED]", text)
    
    # 5. 연락처 (휴대전화, 일반전화)
    text = re.sub(r"\b01[016789]\s*[-]?\s*\d{3,4}\s*[-]?\s*\d{4}\b", "[전화번호_MASKED]", text)
    text = re.sub(r"\b0[2-9]\s*[-]?\s*\d{3,4}\s*[-]?\s*\d{4}\b", "[일반전화_MASKED]", text)
    
    # 6. 사진 데이터 제거 (pypdf는 텍스트만 뽑지만, 캡션 등으로 남을 경우 대비)
    text = re.sub(r"(증명사진|사진란)", "[사진_제거됨]", text)

    return text


def parse_uploaded_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
) -> ParsedDocumentPayload:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf_document(
            file_path,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
        )
    if suffix in TEXT_EXTENSIONS:
        return parse_text_document(
            file_path,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
        )
    raise ValueError(f"Unsupported ingest extension: {suffix or '<none>'}")


def parse_pdf_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
) -> ParsedDocumentPayload:
    reader = PdfReader(str(file_path))
    markdown_sections: list[str] = []
    full_text_parts: list[str] = []
    chunks: list[ParsedChunkPayload] = []
    chunk_index = 0

    for page_number, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        
        # [핵심 로직 투입] 텍스트를 추출하자마자 정규화 전에 마스킹부터 씌웁니다.
        masked_text = _apply_neis_masking(raw_text)
        page_text = _normalize_text(masked_text)
        
        if not page_text:
            continue

        markdown_sections.append(f"## Page {page_number}\n\n{page_text}")
        full_text_parts.append(f"[Page {page_number}]\n{page_text}")

        for content, char_start, char_end in _slice_text(page_text, chunk_size_chars, overlap_chars):
            chunks.append(
                ParsedChunkPayload(
                    chunk_index=chunk_index,
                    page_number=page_number,
                    char_start=char_start,
                    char_end=char_end,
                    token_estimate=_estimate_tokens(content),
                    content_text=content,
                )
            )
            chunk_index += 1

    content_text = "\n\n".join(full_text_parts).strip()
    content_markdown = f"# {file_path.stem}\n\n" + ("\n\n".join(markdown_sections) or "No text extracted.")
    metadata = _clean_metadata(
        {
            "filename": file_path.name,
            "title": getattr(reader.metadata, "title", None),
            "author": getattr(reader.metadata, "author", None),
            "subject": getattr(reader.metadata, "subject", None),
            "creator": getattr(reader.metadata, "creator", None),
            "producer": getattr(reader.metadata, "producer", None),
        }
    )

    return ParsedDocumentPayload(
        parser_name="pypdf",
        source_extension=".pdf",
        page_count=len(reader.pages),
        word_count=len(content_text.split()),
        content_text=content_text,
        content_markdown=content_markdown.strip(),
        metadata=metadata,
        chunks=chunks,
    )


def parse_text_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
) -> ParsedDocumentPayload:
    raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
    
    # 텍스트 파일(MD, TXT) 형태의 생기부 복붙 데이터가 들어올 경우에도 마스킹 적용
    masked_text = _apply_neis_masking(raw_text)
    normalized = _normalize_text(masked_text)
    
    chunks = [
        ParsedChunkPayload(
            chunk_index=index,
            page_number=None,
            char_start=char_start,
            char_end=char_end,
            token_estimate=_estimate_tokens(content),
            content_text=content,
        )
        for index, (content, char_start, char_end) in enumerate(
            _slice_text(normalized, chunk_size_chars, overlap_chars)
        )
    ]

    if file_path.suffix.lower() == ".md":
        content_markdown = masked_text.strip()
    else:
        content_markdown = f"# {file_path.stem}\n\n{normalized}"

    return ParsedDocumentPayload(
        parser_name="plain-text",
        source_extension=file_path.suffix.lower(),
        page_count=1,
        word_count=len(normalized.split()),
        content_text=normalized,
        content_markdown=content_markdown.strip(),
        metadata={"filename": file_path.name},
        chunks=chunks,
    )


def can_ingest_file(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in SUPPORTED_EXTENSIONS


def _slice_text(text: str, chunk_size_chars: int, overlap_chars: int) -> list[tuple[str, int, int]]:
    if not text:
        return []

    step = max(chunk_size_chars - overlap_chars, 1)
    chunks: list[tuple[str, int, int]] = []

    for start in range(0, len(text), step):
        end = min(start + chunk_size_chars, len(text))
        chunk = text[start:end].strip()
        if not chunk:
            continue
        chunks.append((chunk, start, end))
        if end >= len(text):
            break

    return chunks


def _normalize_text(value: str) -> str:
    collapsed = value.replace("\x00", " ")
    collapsed = collapsed.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _estimate_tokens(value: str) -> int:
    return max(1, round(len(value) / 4))


def _clean_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in metadata.items() if value not in (None, "", [])}
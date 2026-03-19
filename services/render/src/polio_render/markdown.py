from __future__ import annotations


def split_markdown_sections(content: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "Overview"
    current_lines: list[str] = []

    for raw_line in (content or "").splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.removeprefix("## ").strip() or "Untitled Section"
            current_lines = []
            continue
        if line.startswith("# "):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.removeprefix("# ").strip() or "Untitled Section"
            current_lines = []
            continue
        current_lines.append(line)

    if current_lines or not sections:
        sections.append((current_title, current_lines))

    normalized: list[tuple[str, list[str]]] = []
    for title, lines in sections:
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        normalized.append((title, cleaned_lines))
    return normalized


def markdown_lines_to_bullets(lines: list[str], *, max_items: int = 6) -> list[str]:
    bullets: list[str] = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith("- "):
            cleaned = cleaned[2:].strip()
        if cleaned.startswith("* "):
            cleaned = cleaned[2:].strip()
        if cleaned.startswith("### "):
            cleaned = cleaned[4:].strip()
        bullets.append(cleaned)
        if len(bullets) >= max_items:
            break
    return bullets

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import (
    load_manifest,
    normalize_space,
    read_text,
    save_manifest,
    sha1_text,
    world_dir,
    write_jsonl,
)


CHAPTER_RE = re.compile(
    r"^\s*((?:第[零〇一二三四五六七八九十百千万两\d]+[章节回卷集部].{0,40})|(?:Chapter\s+\d+.{0,60})|(?:#{1,3}\s+.{1,80}))\s*$",
    re.IGNORECASE,
)


def iter_source_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    files = [path for path in input_path.rglob("*") if path.suffix.lower() in {".txt", ".md"}]
    return sorted(files, key=lambda p: str(p).lower())


def split_chapters(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    chapters: list[tuple[str, list[str]]] = []
    current_title = "未分章"
    current_lines: list[str] = []
    for line in lines:
        match = CHAPTER_RE.match(line)
        if match and current_lines:
            chapters.append((current_title, current_lines))
            current_title = match.group(1).strip("# ")
            current_lines = []
        elif match:
            current_title = match.group(1).strip("# ")
        else:
            current_lines.append(line)
    if current_lines:
        chapters.append((current_title, current_lines))
    return [(title, normalize_space("\n".join(body))) for title, body in chapters if normalize_space("\n".join(body))]


def split_long_text(text: str, target_chars: int, max_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal buf, size
        if buf:
            chunks.append("\n\n".join(buf).strip())
            buf = []
            size = 0

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            flush()
            for start in range(0, len(paragraph), target_chars):
                chunks.append(paragraph[start : start + target_chars].strip())
            continue
        if size and size + len(paragraph) > max_chars:
            flush()
        buf.append(paragraph)
        size += len(paragraph)
        if size >= target_chars:
            flush()
    flush()
    return [chunk for chunk in chunks if chunk]


def ingest(world: str, input_path: Path, target_chars: int, max_chars: int) -> None:
    wdir = world_dir(world)
    source_files = iter_source_files(input_path)
    if not source_files:
        raise SystemExit("No .txt or .md files found.")

    chunks = []
    source_index = []
    order = 0
    for source_file in source_files:
        text = normalize_space(read_text(source_file))
        file_hash = sha1_text(text, 16)
        source_index.append(
            {
                "source_file": str(source_file),
                "text_hash": file_hash,
                "char_count": len(text),
            }
        )
        for chapter_title, chapter_text in split_chapters(text):
            for piece in split_long_text(chapter_text, target_chars, max_chars):
                order += 1
                chunk_id = f"chunk_{order:06d}"
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "source_file": str(source_file),
                        "chapter_title": chapter_title,
                        "order": order,
                        "text_hash": sha1_text(piece, 16),
                        "text": piece,
                    }
                )

    write_jsonl(wdir / "source_index.jsonl", source_index)
    write_jsonl(wdir / "chunks.jsonl", chunks)
    manifest = load_manifest(wdir, world)
    manifest["source_files"] = source_index
    manifest["chunk_count"] = len(chunks)
    save_manifest(wdir, manifest)
    print(f"Ingested {len(source_files)} file(s), {len(chunks)} chunk(s) into {wdir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest TXT/MD novel sources into chunk JSONL.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--target-chars", type=int, default=4000)
    parser.add_argument("--max-chars", type=int, default=6000)
    args = parser.parse_args()
    ingest(args.world, args.input, args.target_chars, args.max_chars)


if __name__ == "__main__":
    main()


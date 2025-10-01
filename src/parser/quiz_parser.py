from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple
from rapidfuzz import fuzz


CHOICE_RE = re.compile(r"^\s*[\(\[]?([A-Za-z0-9])[\)\].:\-]?\s*(.+)$", re.IGNORECASE)
ANS_RE = re.compile(r"^\s*(?:Ans(?:wer)?[:\-]?\s*)?([A-Za-z0-9])(?:\)|\.)?\s*(?::|\-|\)|\.)?\s*(.*)$", re.IGNORECASE)
REF_RE = re.compile(r"^\s*(?:Ref(?:erence)?[:\-]?)\s*(.+)$", re.IGNORECASE)
Q_START_RE = re.compile(r"^(?:Q(?:\d+)?[.\-)\s]*)(.*)$", re.IGNORECASE)


@dataclass
class ParsedQuestion:
    text: str
    options: List[str]
    correct_index: int
    reference: str | None = None


@dataclass
class ParseError:
    message: str
    chunk: str


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    return text.strip()


def split_bulk(content: str) -> List[str]:
    content = normalize_text(content)
    parts = re.split(r"\n\s*\n|\n?---\n?", content)
    return [p.strip() for p in parts if p.strip()]


def parse_single_block(block: str) -> Tuple[ParsedQuestion | None, ParseError | None]:
    original = block
    block = normalize_text(block)
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if not lines:
        return None, ParseError("Empty block", original)

    question_text_lines: List[str] = []
    options: List[str] = []
    correct_index: int | None = None
    reference: str | None = None

    # Detect question start in first few lines
    i = 0
    # If first line starts with Q*, extract text after marker
    first = lines[0]
    m = Q_START_RE.match(first)
    if m:
        q_text = m.group(1).strip()
        if q_text:
            question_text_lines.append(q_text)
            i = 1
        else:
            # if nothing after marker, continue collecting from following lines
            i = 1
    else:
        # If not matched, assume first non-choice is part of question until we hit first choice
        pass

    # Collect until choices start
    while i < len(lines):
        if CHOICE_RE.match(lines[i]):
            break
        if not question_text_lines and Q_START_RE.match(lines[i]):
            question_text_lines.append(Q_START_RE.match(lines[i]).group(1).strip())
        else:
            question_text_lines.append(lines[i])
        i += 1

    # Collect choices
    while i < len(lines) and CHOICE_RE.match(lines[i]):
        m = CHOICE_RE.match(lines[i])
        assert m is not None
        option_text = m.group(2).strip()
        options.append(option_text)
        i += 1

    # Remaining lines: answer/ref possibly in any order
    while i < len(lines):
        line = lines[i]
        if REF_RE.match(line):
            reference = REF_RE.match(line).group(1).strip()
        elif ANS_RE.match(line):
            mg = ANS_RE.match(line)
            ans_token = mg.group(1).strip()
            trailing = mg.group(2).strip() if mg and mg.group(2) else ""
            # Map letter/number to index if possible
            idx: int | None = None
            if ans_token.isalpha():
                idx = ord(ans_token.lower()) - ord('a')
            elif ans_token.isdigit():
                try:
                    idx = int(ans_token) - 1
                except ValueError:
                    idx = None
            if idx is not None and 0 <= idx < len(options):
                correct_index = idx
            elif trailing:
                # Try match by full text fuzzy
                correct_index = _match_answer_to_options(trailing, options)
            else:
                # If only letter but out of range and we have up to 10 opts, clamp
                if idx is not None and len(options) > 0:
                    correct_index = max(0, min(idx, len(options) - 1))
        i += 1

    q_text_final = " ".join(question_text_lines).strip()
    if not q_text_final:
        return None, ParseError("Could not detect question text", original)
    if len(options) < 2:
        return None, ParseError("Less than two options parsed", original)
    if correct_index is None:
        # last chance: look for explicit text answer in lines without Ans
        for line in lines:
            if line.lower().startswith("ans"):
                # already processed; skip
                continue
            mi = _match_answer_to_options(line, options)
            if mi is not None:
                correct_index = mi
                break
    if correct_index is None:
        return None, ParseError("Could not determine correct answer", original)

    return ParsedQuestion(text=q_text_final, options=options, correct_index=correct_index, reference=reference), None


def _match_answer_to_options(answer_text: str, options: List[str]) -> int | None:
    answer_text = normalize_text(answer_text)
    best_idx = None
    best_score = 0
    for idx, opt in enumerate(options):
        score = fuzz.token_set_ratio(answer_text, normalize_text(opt))
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is not None and best_score >= 80:
        return best_idx
    return None


def parse_bulk(content: str) -> Tuple[List[ParsedQuestion], List[ParseError]]:
    chunks = split_bulk(content)
    parsed: List[ParsedQuestion] = []
    errors: List[ParseError] = []
    for chunk in chunks:
        pq, err = parse_single_block(chunk)
        if pq is not None:
            parsed.append(pq)
        else:
            assert err is not None
            errors.append(err)
    return parsed, errors

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple
from rapidfuzz import fuzz


CHOICE_RE = re.compile(r"^\s*[\(\[]?([A-Za-z0-9])[\)\].:\-]\s*(.+)$", re.IGNORECASE)
ANS_RE = re.compile(
    r"^\s*Ans(?:wer)?\s*[\-:]?\s*([A-Za-z0-9])(?:\)|\.)?\s*(?::|\-|\)|\.)?\s*(.*)$",
    re.IGNORECASE,
)
REF_RE = re.compile(r"^\s*Ref(?:erence)?\s*[\-:]?\s*(.+)$", re.IGNORECASE)
Q_START_RE = re.compile(r"^(?:Q(?:\d+)?[.\-)\s]*)(.*)$", re.IGNORECASE)
Q_SPLIT_RE = re.compile(r"(?mi)^Q(?:\d+)?[.\-)]")
CHANNEL_TAG_RE = re.compile(r"^@\S+")
MATCH_PAIR_LINE_RE = re.compile(
    r"^\d+\s*[).\-:]\s+\S.*\s+[a-zA-Z]\s*[).\-:]\s+\S"
)
_FIRST_CHOICE_RE = re.compile(r"^\s*[\(\[]?\s*A\s*[\)\].:\-]", re.IGNORECASE)


@dataclass
class ParsedQuestion:
    text: str
    options: List[str]
    correct_index: int
    reference: str | None = None
    pretext: str | None = None


@dataclass
class ParseError:
    message: str
    chunk: str


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    return text.strip()


def truncate_redundant_block(content: str) -> str:
    matches = list(Q_SPLIT_RE.finditer(content))
    if len(matches) >= 2:
        cut_idx = matches[1].start()
        return content[:cut_idx].strip()
    return content


def _chunk_has_answer(chunk: str) -> bool:
    for line in chunk.splitlines():
        if line.strip().lower().startswith("ans"):
            return True
    return False


def _split_by_answer_boundaries(text: str) -> List[str]:
    lines = text.split("\n")
    boundaries: List[int] = [0]
    state = "collecting"
    last_ref_idx = -1

    for idx, line in enumerate(lines):
        s = line.strip().lower()
        if state == "collecting":
            if s.startswith("ans"):
                state = "ans_seen"
            elif Q_SPLIT_RE.match(line.strip()):
                if idx > 0:
                    boundaries.append(idx)
        elif state == "ans_seen":
            if s.startswith("ref"):
                state = "ref_seen"
                last_ref_idx = idx
            elif Q_SPLIT_RE.match(line.strip()):
                boundaries.append(idx)
                state = "collecting"
            elif _FIRST_CHOICE_RE.match(s):
                boundaries.append(idx)
                state = "collecting"
            elif s and len(s) <= 2 and s.replace(".", "").replace("-", "").isalpha():
                pass
        elif state == "ref_seen":
            if s.startswith("ref"):
                last_ref_idx = idx
            else:
                boundaries.append(idx)
                state = "collecting"

    if len(boundaries) <= 1:
        return [text]
    chunks: List[str] = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def split_bulk(content: str) -> List[str]:
    content = normalize_text(content)
    parts = re.split(r"\n\s*\n|\n---[ \t]*\n", content)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []

    if len(parts) > 1:
        merged: List[str] = [parts[0]]
        for part in parts[1:]:
            first_line = part.split("\n", 1)[0].strip()
            low = first_line.lower()
            if low.startswith("ans") or low.startswith("ref"):
                merged[-1] += "\n" + part
            elif MATCH_PAIR_LINE_RE.match(first_line):
                merged[-1] += "\n" + part
            else:
                fl_m = CHOICE_RE.match(first_line)
                if fl_m and not _chunk_has_answer(merged[-1]):
                    merged[-1] += "\n" + part
                else:
                    merged.append(part)
    else:
        blob = parts[0]
        q_positions = [m.start() for m in Q_SPLIT_RE.finditer(blob)]
        if q_positions:
            merged = []
            for i, pos in enumerate(q_positions):
                end = q_positions[i + 1] if i + 1 < len(q_positions) else len(blob)
                chunk = blob[pos:end].strip()
                if chunk:
                    merged.append(chunk)
        else:
            merged = [blob]

    final: List[str] = []
    for chunk in merged:
        sub = _split_by_answer_boundaries(chunk)
        final.extend(sub)
    return final


def _find_letter_choice_start(lines: List[str], start_idx: int) -> int | None:
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        low = line.lower()
        if low.startswith("ans") or low.startswith("ref"):
            break
        m = CHOICE_RE.match(line)
        if m and m.group(1).isalpha():
            return idx
    return None


def parse_single_block(block: str) -> Tuple[ParsedQuestion | None, ParseError | None]:
    original = block
    block = normalize_text(block)
    block = truncate_redundant_block(block)
    lines = [l.strip() for l in block.splitlines() if l.strip() and not CHANNEL_TAG_RE.match(l.strip())]
    if not lines:
        return None, ParseError("Empty block", original)

    question_text_lines: List[str] = []
    options: List[str] = []
    correct_index: int | None = None
    reference: str | None = None
    pretext: str | None = None

    pretext_lines: List[str] = []
    remaining_lines: List[str] = []
    for line in lines:
        if MATCH_PAIR_LINE_RE.match(line):
            pretext_lines.append(line)
        else:
            remaining_lines.append(line)
    if pretext_lines:
        pretext = "\n".join(pretext_lines)
        lines = remaining_lines

    if not lines:
        return None, ParseError("Empty block after pretext extraction", original)

    i = 0
    first = lines[0]
    m = Q_START_RE.match(first)
    if m:
        q_text = m.group(1).strip()
        if q_text:
            question_text_lines.append(q_text)
            i = 1
        else:
            i = 1

    letter_choice_idx = _find_letter_choice_start(lines, i)

    while i < len(lines):
        if Q_START_RE.match(lines[i]) and options:
            break
        m = CHOICE_RE.match(lines[i])
        if m:
            if m.group(1).isdigit() and letter_choice_idx is not None:
                question_text_lines.append(lines[i])
                i += 1
                continue
            break
        if not question_text_lines and Q_START_RE.match(lines[i]):
            question_text_lines.append(Q_START_RE.match(lines[i]).group(1).strip())
        else:
            question_text_lines.append(lines[i])
        i += 1

    while i < len(lines):
        line = lines[i]
        low = line.lower()
        if low.startswith("ans") or low.startswith("ref") or Q_START_RE.match(line):
            break
        m = CHOICE_RE.match(line)
        if not m:
            break
        if m.group(1).isdigit() and letter_choice_idx is not None:
            i += 1
            continue
        option_text = m.group(2).strip()
        options.append(option_text)
        i += 1

    while i < len(lines):
        line = lines[i]
        if Q_START_RE.match(line):
            break
        if REF_RE.match(line):
            reference = REF_RE.match(line).group(1).strip()
        elif ANS_RE.match(line):
            mg = ANS_RE.match(line)
            ans_token = mg.group(1).strip()
            trailing = mg.group(2).strip() if mg and mg.group(2) else ""
            idx: int | None = None
            if ans_token.isalpha():
                idx = ord(ans_token.lower()) - ord("a")
            elif ans_token.isdigit():
                try:
                    idx = int(ans_token) - 1
                except ValueError:
                    idx = None
            if idx is not None and 0 <= idx < len(options):
                correct_index = idx
            elif trailing:
                correct_index = _match_answer_to_options(trailing, options)
            else:
                if idx is not None and len(options) > 0:
                    correct_index = max(0, min(idx, len(options) - 1))
        elif line.lower().startswith("ans") and correct_index is None:
            for j in range(i + 1, min(i + 3, len(lines))):
                nxt = lines[j].strip()
                if len(nxt) == 1 and nxt.isalpha():
                    idx = ord(nxt.lower()) - ord("a")
                    if 0 <= idx < len(options):
                        correct_index = idx
                        break
        i += 1

    q_text_final = " ".join(question_text_lines).strip()
    if not q_text_final:
        return None, ParseError("Could not detect question text", original)
    if len(options) < 2:
        return None, ParseError("Less than two options parsed", original)
    if correct_index is None:
        for line in lines:
            if line.lower().startswith("ans"):
                continue
            mi = _match_answer_to_options(line, options)
            if mi is not None:
                correct_index = mi
                break
    if correct_index is None:
        return None, ParseError("Could not determine correct answer", original)

    return (
        ParsedQuestion(
            text=q_text_final,
            options=options,
            correct_index=correct_index,
            reference=reference,
            pretext=pretext,
        ),
        None,
    )


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
        chunk = truncate_redundant_block(chunk)
        pq, err = parse_single_block(chunk)
        if pq is not None:
            parsed.append(pq)
        else:
            assert err is not None
            errors.append(err)
    return parsed, errors

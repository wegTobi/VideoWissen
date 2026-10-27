"""Conservative transcription warnings. Heuristics are not correctness scores."""
import math
import re
import unicodedata


def tokens(text):
    return re.findall(r"[^\W_]+", text.casefold(), re.UNICODE)


def repetition(text):
    words = tokens(text)
    for width in range(1, min(6, len(words) // 3) + 1):
        required = 4 if width == 1 else 3
        for start in range(len(words) - width * required + 1):
            phrase = words[start:start + width]
            count = 1
            while words[start + count * width:start + (count + 1) * width] == phrase:
                count += 1
            if count >= required and count * width >= len(words) / 2:
                return True
    return False


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def warnings(record, language):
    reasons = []
    words = tokens(record["text"])
    if repetition(record["text"]):
        reasons.append("Auffällige Wiederholungsschleife")
    duration = record.get("review_end", record["end"]) - record.get("review_start", record["start"])
    if duration > 20 and len(words) < 10:
        reasons.append("Langer Abschnitt mit sehr wenig erkanntem Text")
    logprob = record.get("avg_logprob")
    compression = record.get("compression_ratio")
    no_speech = record.get("no_speech_prob")
    if finite(logprob) and logprob < -1.0:
        reasons.append("Niedrige Erkennungssicherheit des Modells")
    if finite(compression) and compression > 2.4:
        reasons.append("Ungewöhnlich stark wiederholender Text laut Modell")
    if finite(no_speech) and no_speech > .6 and finite(logprob) and logprob < -.5:
        reasons.append("Widersprüchliche Sprach-/Stille-Erkennung")
    probabilities = record.get("word_probabilities", [])
    if probabilities and sum(probabilities) / len(probabilities) < .45:
        reasons.append("Niedrige Sicherheit erkannter Wörter")
    # Foreign names and code-switching are valid. A script mismatch alone is
    # insufficient; combine it with a second weak recognition signal.
    foreign = sum(c.isalpha() and "LATIN" not in unicodedata.name(c, "") for c in record["text"])
    if language in ("de", "en") and foreign and finite(logprob) and logprob < -.7:
        reasons.append("Ungewöhnliche Schriftzeichen zusammen mit schwacher Erkennung")
    return reasons


def flag_adjacent_repetitions(records):
    start = 0
    while start < len(records):
        end = start + 1
        phrase = tokens(records[start]["text"])
        while (phrase and end < len(records) and tokens(records[end]["text"]) == phrase
               and records[end]["start"] - records[end - 1]["end"] <= 2):
            end += 1
        if end - start >= 3:
            for record in records[start:end]:
                reason = "Derselbe Text in mehreren aufeinanderfolgenden Abschnitten"
                if reason not in record["warnings"]:
                    record["warnings"].append(reason)
        start = end


def review_windows(records):
    """Merge suspicious intervals; each retry covers at most 30s plus context."""
    merged = []
    for record in sorted(records, key=lambda item: item.get("review_start", item["start"])):
        if not record["warnings"]:
            continue
        left = record.get("review_start", record["start"])
        right = record.get("review_end", record["end"])
        if merged and left <= merged[-1][1] + 2:
            merged[-1][1] = max(merged[-1][1], right)
        else:
            merged.append([left, right])
    windows = []
    for start, end in merged:
        while start < end:
            stop = min(end, start + 30)
            windows.append((start, stop))
            start = stop
    return windows

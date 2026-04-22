import re
from collections import Counter

from app.parser import extract_document
from app.semantic import build_semantic_features


def _tokenize(value: str) -> list[str]:
    return re.findall(r"\w+", value.lower(), flags=re.UNICODE)


def _document_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [rendered for rendered in (str(item).strip() for item in value) if rendered]


def _document_count(counts: dict[str, object], key: str) -> int:
    value = counts.get(key)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def build_features(html: str, text: str, query: str) -> dict[str, float | int]:
    document = extract_document(html)
    counts = document.get("counts") if isinstance(document.get("counts"), dict) else {}

    normalized_text = text.strip() or str(document.get("text") or "")
    query = query.strip().lower()
    text_lower = normalized_text.lower()
    title = str(document.get("title") or "")
    title_lower = title.lower()
    meta_description = str(document.get("meta_description") or "")
    meta_description_lower = meta_description.lower()
    h1_texts = _document_text_list(document.get("h1_texts"))
    h2_texts = _document_text_list(document.get("h2_texts"))
    h3_texts = _document_text_list(document.get("h3_texts"))
    heading_text = " ".join([*h1_texts, *h2_texts, *h3_texts]).strip()
    heading_text_lower = heading_text.lower()

    words = _tokenize(normalized_text)
    query_words = _tokenize(query)
    first_200_words = words[:200]
    word_count = len(words)
    unique_word_count = len(set(words))
    unique_word_ratio = (unique_word_count / word_count) if word_count else 0.0
    sentence_count = max(len(re.findall(r"[.!?]+", normalized_text)), 1 if normalized_text else 0)
    paragraph_count = max(_document_count(counts, "paragraph"), 1 if normalized_text else 0)
    h1_count = _document_count(counts, "h1")
    h2_count = _document_count(counts, "h2")
    h3_count = _document_count(counts, "h3")
    link_count = _document_count(counts, "link")
    image_count = _document_count(counts, "image")
    list_item_count = _document_count(counts, "list_item")
    strong_count = _document_count(counts, "strong")
    form_count = _document_count(counts, "form")
    input_count = _document_count(counts, "input")
    heading_count = h1_count + h2_count + h3_count

    query_term_count = 0
    query_term_matches = 0
    keyword_coverage_ratio = 0.0
    exact_query_count = 0
    query_density = 0.0
    title_query_term_count = 0
    meta_query_term_count = 0
    title_keyword_coverage_ratio = 0.0
    meta_keyword_coverage_ratio = 0.0
    query_terms_in_headings = 0
    heading_query_coverage_ratio = 0.0
    first_200_words_query_term_count = 0

    if query_words:
        word_freq = Counter(words)
        first_200_word_freq = Counter(first_200_words)
        title_word_freq = Counter(_tokenize(title_lower))
        meta_word_freq = Counter(_tokenize(meta_description_lower))
        heading_word_freq = Counter(_tokenize(heading_text_lower))
        query_term_count = sum(word_freq[word] for word in query_words)
        query_term_matches = sum(1 for word in query_words if word in word_freq)
        keyword_coverage_ratio = query_term_matches / len(query_words)
        exact_query_count = text_lower.count(query)
        query_density = query_term_count / word_count if word_count else 0.0
        title_query_term_count = sum(title_word_freq[word] for word in query_words)
        meta_query_term_count = sum(meta_word_freq[word] for word in query_words)
        title_keyword_matches = sum(1 for word in query_words if word in title_word_freq)
        meta_keyword_matches = sum(1 for word in query_words if word in meta_word_freq)
        title_keyword_coverage_ratio = title_keyword_matches / len(query_words)
        meta_keyword_coverage_ratio = meta_keyword_matches / len(query_words)
        query_terms_in_headings = sum(heading_word_freq[word] for word in query_words)
        heading_query_matches = sum(1 for word in query_words if word in heading_word_freq)
        heading_query_coverage_ratio = heading_query_matches / len(query_words)
        first_200_words_query_term_count = sum(first_200_word_freq[word] for word in query_words)

    avg_word_length = (sum(len(word) for word in words) / word_count) if word_count else 0.0
    avg_sentence_length = (word_count / sentence_count) if sentence_count else 0.0
    avg_paragraph_length = (word_count / paragraph_count) if paragraph_count else 0.0
    inputs_per_form_ratio = (input_count / form_count) if form_count else 0.0
    text_to_html_ratio = (len(normalized_text) / len(html)) if html else 0.0
    per_1000_words = (1000.0 / word_count) if word_count else 0.0
    early_query_coverage_ratio = (first_200_words_query_term_count / len(query_words)) if query_words else 0.0

    features: dict[str, float | int] = {
        "text_length_chars": len(normalized_text),
        "html_length_chars": len(html),
        "word_count": word_count,
        "unique_word_count": unique_word_count,
        "unique_word_ratio": unique_word_ratio,
        "avg_word_length": round(avg_word_length, 4),
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_length, 4),
        "paragraph_count": paragraph_count,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "heading_count": heading_count,
        "title_present": int(bool(title)),
        "title_length": len(title),
        "meta_description_present": int(bool(meta_description)),
        "meta_description_length": len(meta_description),
        "query_in_title": int(bool(query and query in title_lower)),
        "query_in_text": int(bool(query and query in text_lower)),
        "exact_query_count": exact_query_count,
        "query_term_count": query_term_count,
        "title_query_term_count": title_query_term_count,
        "meta_query_term_count": meta_query_term_count,
        "title_keyword_coverage_ratio": round(title_keyword_coverage_ratio, 6),
        "meta_keyword_coverage_ratio": round(meta_keyword_coverage_ratio, 6),
        "query_terms_in_headings": query_terms_in_headings,
        "heading_query_coverage_ratio": round(heading_query_coverage_ratio, 6),
        "first_200_words_query_term_count": first_200_words_query_term_count,
        "query_density": round(query_density, 6),
        "keyword_coverage_ratio": round(keyword_coverage_ratio, 6),
        "link_count": link_count,
        "image_count": image_count,
        "list_item_count": list_item_count,
        "strong_tag_count": strong_count,
        "form_count": form_count,
        "input_count": input_count,
        "inputs_per_form_ratio": round(inputs_per_form_ratio, 6),
        "avg_paragraph_length": round(avg_paragraph_length, 4),
        "link_density_per_1000_words": round(link_count * per_1000_words, 6),
        "image_density_per_1000_words": round(image_count * per_1000_words, 6),
        "list_density_per_1000_words": round(list_item_count * per_1000_words, 6),
        "strong_density_per_1000_words": round(strong_count * per_1000_words, 6),
        "text_to_html_ratio": round(text_to_html_ratio, 6),
    }
    features.update(build_semantic_features(text=normalized_text, query=query))

    semantic_similarity = float(features.get("semantic_similarity", 0.0))
    conversion_signal_score = (
        int(form_count > 0)
        + int(input_count > 0)
        + int(image_count > 0)
        + int(list_item_count > 0)
    ) / 4.0
    content_link_ratio = (word_count / max(link_count, 1)) if word_count else 0.0
    heading_paragraph_balance = (heading_count / max(paragraph_count, 1)) if paragraph_count else 0.0
    query_semantic_alignment = semantic_similarity * keyword_coverage_ratio
    title_semantic_alignment = semantic_similarity * title_keyword_coverage_ratio
    heading_semantic_alignment = semantic_similarity * heading_query_coverage_ratio
    title_heading_keyword_alignment = title_keyword_coverage_ratio * heading_query_coverage_ratio
    content_depth_semantic_score = semantic_similarity * min(word_count / 1500.0, 1.0)
    query_prominence_score = (
        title_keyword_coverage_ratio * 0.35
        + heading_query_coverage_ratio * 0.25
        + min(early_query_coverage_ratio, 1.0) * 0.25
        + keyword_coverage_ratio * 0.15
    )
    title_length_quality = max(0.0, 1.0 - (abs(len(title) - 55.0) / 55.0)) if title else 0.0
    meta_length_quality = (
        max(0.0, 1.0 - (abs(len(meta_description) - 145.0) / 145.0)) if meta_description else 0.0
    )
    keyword_balance_score = keyword_coverage_ratio * max(0.0, 1.0 - min(abs(query_density - 0.03) / 0.03, 1.0))
    semantic_content_richness = semantic_similarity * min(word_count / 1800.0, 1.0) * min(unique_word_ratio, 1.0)
    cta_semantic_score = conversion_signal_score * semantic_similarity

    features.update(
        {
            "early_query_coverage_ratio": round(min(early_query_coverage_ratio, 1.0), 6),
            "conversion_signal_score": round(conversion_signal_score, 6),
            "content_link_ratio": round(content_link_ratio, 6),
            "heading_paragraph_balance": round(heading_paragraph_balance, 6),
            "query_semantic_alignment": round(query_semantic_alignment, 6),
            "title_semantic_alignment": round(title_semantic_alignment, 6),
            "heading_semantic_alignment": round(heading_semantic_alignment, 6),
            "title_heading_keyword_alignment": round(title_heading_keyword_alignment, 6),
            "content_depth_semantic_score": round(content_depth_semantic_score, 6),
            "query_prominence_score": round(query_prominence_score, 6),
            "title_length_quality": round(title_length_quality, 6),
            "meta_length_quality": round(meta_length_quality, 6),
            "keyword_balance_score": round(keyword_balance_score, 6),
            "semantic_content_richness": round(semantic_content_richness, 6),
            "cta_semantic_score": round(cta_semantic_score, 6),
        }
    )
    return features

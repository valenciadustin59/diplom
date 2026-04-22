from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlsplit

from app.parser import ensure_extraction_artifact, extract_document
from app.semantic import build_semantic_features


TECHNICAL_SEO_FEATURE_COLUMNS = [
    "http_status_code",
    "http_status_ok",
    "redirect_count",
    "has_redirect",
    "canonical_present",
    "canonical_matches_final_url",
    "meta_robots_present",
    "x_robots_tag_present",
    "robots_noindex",
    "robots_nofollow",
    "page_indexable",
    "viewport_present",
    "lang_present",
    "hreflang_count",
    "hreflang_present",
    "url_depth",
    "url_parameter_count",
    "url_has_query_parameters",
    "redirect_efficiency_score",
    "url_hygiene_score",
    "technical_metadata_score",
    "canonical_signal_score",
    "technical_seo_score",
]

COMMERCIAL_TRUST_FEATURE_COLUMNS = [
    "phone_present",
    "phone_count",
    "email_present",
    "address_present",
    "business_hours_present",
    "price_present",
    "currency_present",
    "delivery_info_present",
    "payment_info_present",
    "warranty_info_present",
    "returns_info_present",
    "reviews_present",
    "rating_present",
    "faq_present",
    "cta_present",
    "cta_count",
    "messenger_present",
    "value_proposition_present",
    "legal_requisites_present",
    "company_identity_present",
    "contact_options_score",
    "commercial_signal_count",
    "trust_signal_count",
    "commercial_signals_score",
    "trust_signals_score",
    "commercial_trust_score",
]

SNAPSHOT_AUXILIARY_FEATURE_COLUMNS = [
    *TECHNICAL_SEO_FEATURE_COLUMNS,
    *COMMERCIAL_TRUST_FEATURE_COLUMNS,
]

PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", flags=re.IGNORECASE)
PRICE_PATTERN = re.compile(
    r"(?:от\s+)?\d[\d\s]{1,12}(?:[.,]\d{1,2})?\s?(?:₽|р\.|руб(?:\.|лей)?|€|eur|usd|\$)",
    flags=re.IGNORECASE,
)
CURRENCY_PATTERN = re.compile(r"(?:₽|р\.|руб(?:\.|лей)?|€|eur|usd|\$)", flags=re.IGNORECASE)
RATING_PATTERN = re.compile(r"(?:ratingvalue|рейтинг|rating)\D{0,12}([1-5](?:[.,]\d)?)", flags=re.IGNORECASE)

ADDRESS_KEYWORDS = (
    "адрес",
    "ул.",
    "улица",
    "проспект",
    "пр-т",
    "дом ",
    "офис",
    "строение",
    "корпус",
    "street",
    "avenue",
    "suite",
)
BUSINESS_HOURS_KEYWORDS = (
    "режим работы",
    "часы работы",
    "график работы",
    "время работы",
    "opening hours",
    "mon",
    "пн-пт",
    "понедельник",
)
DELIVERY_KEYWORDS = (
    "доставка",
    "shipping",
    "самовывоз",
    "курьер",
)
PAYMENT_KEYWORDS = (
    "оплата",
    "payment",
    "безнал",
    "наличн",
    "карта",
    "visa",
    "mastercard",
)
WARRANTY_KEYWORDS = ("гаранти", "warranty")
RETURNS_KEYWORDS = ("возврат", "return", "refund", "обмен")
REVIEWS_KEYWORDS = ("отзывы", "reviews", "testimonial")
FAQ_KEYWORDS = ("faq", "вопросы и ответы", "часто задаваемые вопросы", "ответы на вопросы")
MESSENGER_KEYWORDS = ("whatsapp", "telegram", "t.me", "wa.me", "viber", "vk.me")
CTA_KEYWORDS = (
    "купить",
    "заказать",
    "оставить заявку",
    "получить",
    "связаться",
    "позвонить",
    "отправить",
    "подобрать",
    "узнать цену",
    "консультац",
    "request",
    "contact",
    "buy",
    "order",
)
VALUE_PROPOSITION_KEYWORDS = (
    "бесплатн",
    "скидк",
    "акци",
    "опыт",
    "лет на рынке",
    "под ключ",
    "официаль",
    "сертиф",
    "собственное производство",
    "от производителя",
    "качество",
    "быстро",
    "за 1 день",
    "рассроч",
    "выезд замерщика",
)
LEGAL_KEYWORDS = (
    "инн",
    "огрн",
    "кпп",
    "ооо",
    "ип ",
    "реквизит",
    "llc",
    "ltd",
    "inc",
)


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


def _normalize_scan_text(*values: object) -> str:
    rendered = " ".join(str(value or "") for value in values if value is not None)
    return re.sub(r"\s+", " ", rendered).strip().lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _nested_key_present(value: object, target_key: str) -> bool:
    if isinstance(value, dict):
        if target_key in value:
            return True
        return any(_nested_key_present(item, target_key) for item in value.values())
    if isinstance(value, list):
        return any(_nested_key_present(item, target_key) for item in value)
    return False


def _nested_string_present(value: object, keywords: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        return any(_nested_string_present(item, keywords) for item in value.values())
    if isinstance(value, list):
        return any(_nested_string_present(item, keywords) for item in value)
    if isinstance(value, str):
        normalized = value.lower()
        return _contains_any(normalized, keywords)
    return False


def _json_ld_objects(snapshot: dict[str, object]) -> list[dict[str, object]]:
    raw_items = snapshot.get("json_ld")
    if not isinstance(raw_items, list):
        return []

    objects: list[dict[str, object]] = []

    def append_items(value: object) -> None:
        if isinstance(value, dict):
            objects.append(value)
            graph = value.get("@graph")
            if isinstance(graph, list):
                append_items(graph)
        elif isinstance(value, list):
            for item in value:
                append_items(item)

    for raw_item in raw_items:
        if not isinstance(raw_item, str) or not raw_item.strip():
            continue
        try:
            append_items(json.loads(raw_item))
        except json.JSONDecodeError:
            continue

    return objects


def _json_ld_type_present(objects: list[dict[str, object]], *types: str) -> bool:
    normalized_types = {item.lower() for item in types}
    for obj in objects:
        raw_type = obj.get("@type")
        if isinstance(raw_type, str) and raw_type.lower() in normalized_types:
            return True
        if isinstance(raw_type, list) and any(str(item).lower() in normalized_types for item in raw_type):
            return True
    return False


def _document_payload(snapshot: dict[str, object]) -> dict[str, object]:
    document = snapshot.get("document")
    if isinstance(document, dict):
        return document
    return {}


def _headers_payload(snapshot: dict[str, object]) -> dict[str, str]:
    headers = snapshot.get("response_headers")
    if not isinstance(headers, dict):
        return {}
    return {str(key).strip().lower(): str(value).strip() for key, value in headers.items() if str(key).strip()}


def _header_value(headers: dict[str, str], key: str) -> str:
    return str(headers.get(key.lower()) or "").strip()


def _parse_robots_directives(*values: str) -> set[str]:
    directives: set[str] = set()
    for value in values:
        normalized = str(value or "").lower().replace(";", ",")
        for segment in normalized.split(","):
            token = segment.strip()
            if not token:
                continue
            if ":" in token:
                token = token.split(":", maxsplit=1)[1].strip()
            for part in token.split():
                cleaned = part.strip()
                if cleaned:
                    directives.add(cleaned)
    if "none" in directives:
        directives.update({"noindex", "nofollow"})
    return directives


def _normalize_url_parts(url: str, *, base_url: str = "") -> tuple[str, str, str, tuple[tuple[str, str], ...]] | None:
    resolved = urljoin(base_url, str(url or "").strip())
    if not resolved:
        return None

    parsed = urlsplit(resolved)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower().removeprefix("www.")
    if not scheme or not netloc:
        return None

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query = tuple(sorted((str(key), str(value)) for key, value in parse_qsl(parsed.query, keep_blank_values=True)))
    return scheme, netloc, path, query


def _canonical_matches_final_url(canonical_url: str, final_url: str) -> bool:
    canonical_parts = _normalize_url_parts(canonical_url, base_url=final_url)
    final_parts = _normalize_url_parts(final_url)
    if canonical_parts is None or final_parts is None:
        return False
    if canonical_parts[:3] != final_parts[:3]:
        return False
    if canonical_parts[3] == final_parts[3]:
        return True
    return not canonical_parts[3]


def _url_depth(url: str) -> int:
    parsed = urlsplit(url)
    return len([segment for segment in parsed.path.split("/") if segment])


def _url_parameter_count(url: str) -> int:
    parsed = urlsplit(url)
    return len(parse_qsl(parsed.query, keep_blank_values=True))


def _normalize_snapshot(snapshot: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(snapshot, dict):
        return None
    requested_url = str(snapshot.get("requested_url") or snapshot.get("final_url") or "").strip()
    if not requested_url:
        return None
    return ensure_extraction_artifact(requested_url=requested_url, artifact=snapshot)


def build_technical_seo_features(snapshot: dict[str, object] | None) -> dict[str, float | int]:
    normalized_snapshot = _normalize_snapshot(snapshot)
    if normalized_snapshot is None:
        return {}

    requested_url = str(normalized_snapshot.get("requested_url") or "").strip()
    final_url = str(normalized_snapshot.get("final_url") or requested_url).strip()
    document = _document_payload(normalized_snapshot)
    headers = _headers_payload(normalized_snapshot)
    status_code = normalized_snapshot.get("status_code")
    redirect_chain = (
        normalized_snapshot.get("redirect_chain") if isinstance(normalized_snapshot.get("redirect_chain"), list) else []
    )
    canonical = str(document.get("canonical") or "").strip()
    meta_robots = str(document.get("meta_robots") or "").strip()
    x_robots_tag = _header_value(headers, "x-robots-tag")
    viewport = str(document.get("viewport") or "").strip()
    lang = str(document.get("lang") or "").strip()
    hreflang_links = document.get("hreflang_links") if isinstance(document.get("hreflang_links"), list) else []

    http_status_code = int(status_code) if isinstance(status_code, (int, float)) else 0
    http_status_ok = int(200 <= http_status_code < 300)
    redirect_count = len(redirect_chain)
    has_redirect = int(redirect_count > 0)
    canonical_present = int(bool(canonical))
    canonical_matches_final_url = int(bool(canonical_present and _canonical_matches_final_url(canonical, final_url)))
    meta_robots_present = int(bool(meta_robots))
    x_robots_tag_present = int(bool(x_robots_tag))
    robots_directives = _parse_robots_directives(meta_robots, x_robots_tag)
    robots_noindex = int("noindex" in robots_directives)
    robots_nofollow = int("nofollow" in robots_directives)
    page_indexable = int(bool(http_status_ok and not robots_noindex))
    viewport_present = int(bool(viewport))
    lang_present = int(bool(lang))
    hreflang_count = sum(
        1
        for item in hreflang_links
        if isinstance(item, dict) and str(item.get("hreflang") or "").strip() and str(item.get("href") or "").strip()
    )
    hreflang_present = int(hreflang_count > 0)
    url_depth = _url_depth(final_url)
    url_parameter_count = _url_parameter_count(final_url)
    url_has_query_parameters = int(url_parameter_count > 0)
    redirect_efficiency_score = max(0.0, 1.0 - (min(redirect_count, 3) / 3.0))
    depth_score = max(0.0, 1.0 - (min(url_depth, 6) / 6.0))
    parameter_score = max(0.0, 1.0 - (min(url_parameter_count, 4) / 4.0))
    url_hygiene_score = depth_score * 0.6 + parameter_score * 0.4
    technical_metadata_score = (viewport_present + lang_present) / 2.0
    if canonical_matches_final_url:
        canonical_signal_score = 1.0
    elif canonical_present:
        canonical_signal_score = 0.0
    elif has_redirect or url_has_query_parameters:
        canonical_signal_score = 0.35
    else:
        canonical_signal_score = 0.75
    technical_seo_score = (
        page_indexable
        + canonical_signal_score
        + redirect_efficiency_score
        + url_hygiene_score
        + technical_metadata_score
    ) / 5.0

    return {
        "http_status_code": http_status_code,
        "http_status_ok": http_status_ok,
        "redirect_count": redirect_count,
        "has_redirect": has_redirect,
        "canonical_present": canonical_present,
        "canonical_matches_final_url": canonical_matches_final_url,
        "meta_robots_present": meta_robots_present,
        "x_robots_tag_present": x_robots_tag_present,
        "robots_noindex": robots_noindex,
        "robots_nofollow": robots_nofollow,
        "page_indexable": page_indexable,
        "viewport_present": viewport_present,
        "lang_present": lang_present,
        "hreflang_count": hreflang_count,
        "hreflang_present": hreflang_present,
        "url_depth": url_depth,
        "url_parameter_count": url_parameter_count,
        "url_has_query_parameters": url_has_query_parameters,
        "redirect_efficiency_score": round(redirect_efficiency_score, 6),
        "url_hygiene_score": round(url_hygiene_score, 6),
        "technical_metadata_score": round(technical_metadata_score, 6),
        "canonical_signal_score": round(canonical_signal_score, 6),
        "technical_seo_score": round(technical_seo_score, 6),
    }


def merge_technical_seo_features(
    features: dict[str, float | int],
    snapshot: dict[str, object] | None,
) -> dict[str, float | int]:
    technical_features = build_technical_seo_features(snapshot)
    if not technical_features:
        return dict(features)
    return {
        **features,
        **technical_features,
    }


def build_commercial_trust_features(snapshot: dict[str, object] | None) -> dict[str, float | int]:
    normalized_snapshot = _normalize_snapshot(snapshot)
    if normalized_snapshot is None:
        return {}

    document = _document_payload(normalized_snapshot)
    text = str(normalized_snapshot.get("text") or "")
    html = str(normalized_snapshot.get("html") or "")
    links = document.get("links") if isinstance(document.get("links"), list) else []
    button_texts = _document_text_list(document.get("button_texts"))
    counts = document.get("counts") if isinstance(document.get("counts"), dict) else {}
    json_ld_objects = _json_ld_objects(normalized_snapshot)

    link_hrefs = [str(item.get("href") or "").strip().lower() for item in links if isinstance(item, dict)]
    link_texts = [str(item.get("text") or "").strip() for item in links if isinstance(item, dict)]
    visible_text = _normalize_scan_text(text, " ".join(link_texts), " ".join(button_texts))
    html_text = html.lower()
    full_scan_text = _normalize_scan_text(visible_text, html_text)

    phone_matches = {
        re.sub(r"\D", "", match)
        for match in PHONE_PATTERN.findall(f"{text} {' '.join(link_hrefs)}")
        if len(re.sub(r"\D", "", match)) >= 10
    }
    if any(_nested_key_present(obj, "telephone") for obj in json_ld_objects):
        phone_matches.add("schema-phone")
    phone_count = len(phone_matches)
    phone_present = int(phone_count > 0 or any(href.startswith("tel:") for href in link_hrefs))

    email_matches = {match.lower() for match in EMAIL_PATTERN.findall(f"{text} {' '.join(link_hrefs)}")}
    email_present = int(bool(email_matches or any(href.startswith("mailto:") for href in link_hrefs)))

    address_present = int(
        _contains_any(full_scan_text, ADDRESS_KEYWORDS)
        or _nested_key_present(json_ld_objects, "address")
        or _json_ld_type_present(json_ld_objects, "PostalAddress")
    )
    business_hours_present = int(
        _contains_any(full_scan_text, BUSINESS_HOURS_KEYWORDS)
        or _nested_key_present(json_ld_objects, "openingHours")
        or _nested_key_present(json_ld_objects, "openingHoursSpecification")
    )
    price_present = int(
        bool(PRICE_PATTERN.search(full_scan_text))
        or _nested_key_present(json_ld_objects, "price")
        or _nested_key_present(json_ld_objects, "lowPrice")
    )
    currency_present = int(
        bool(CURRENCY_PATTERN.search(full_scan_text))
        or _nested_key_present(json_ld_objects, "priceCurrency")
    )
    delivery_info_present = int(
        _contains_any(full_scan_text, DELIVERY_KEYWORDS)
        or _nested_key_present(json_ld_objects, "shippingDetails")
        or _nested_key_present(json_ld_objects, "availableDeliveryMethod")
    )
    payment_info_present = int(_contains_any(full_scan_text, PAYMENT_KEYWORDS))
    warranty_info_present = int(
        _contains_any(full_scan_text, WARRANTY_KEYWORDS)
        or _nested_key_present(json_ld_objects, "warranty")
    )
    returns_info_present = int(
        _contains_any(full_scan_text, RETURNS_KEYWORDS)
        or _nested_key_present(json_ld_objects, "hasMerchantReturnPolicy")
    )
    reviews_present = int(
        _contains_any(full_scan_text, REVIEWS_KEYWORDS)
        or _nested_key_present(json_ld_objects, "review")
    )
    rating_present = int(
        bool(RATING_PATTERN.search(full_scan_text))
        or _nested_key_present(json_ld_objects, "aggregateRating")
        or _nested_key_present(json_ld_objects, "ratingValue")
    )
    faq_present = int(
        _contains_any(full_scan_text, FAQ_KEYWORDS)
        or _json_ld_type_present(json_ld_objects, "FAQPage")
    )

    cta_count = sum(1 for candidate in [*button_texts, *link_texts] if _contains_any(candidate.lower(), CTA_KEYWORDS))
    if _document_count(counts, "form") > 0 and cta_count == 0:
        cta_count = 1
    cta_present = int(cta_count > 0)

    messenger_present = int(
        any(_contains_any(href, MESSENGER_KEYWORDS) for href in link_hrefs)
        or _contains_any(full_scan_text, MESSENGER_KEYWORDS)
    )
    value_proposition_present = int(_contains_any(full_scan_text, VALUE_PROPOSITION_KEYWORDS))
    legal_requisites_present = int(
        _contains_any(full_scan_text, LEGAL_KEYWORDS)
        or _nested_key_present(json_ld_objects, "taxID")
        or _nested_key_present(json_ld_objects, "vatID")
    )
    company_identity_present = int(
        legal_requisites_present
        or _json_ld_type_present(json_ld_objects, "Organization", "LocalBusiness", "Corporation", "Store")
    )

    contact_signals = [phone_present, email_present, address_present, business_hours_present, messenger_present]
    commercial_signals = [
        phone_present,
        address_present,
        business_hours_present,
        price_present,
        delivery_info_present,
        payment_info_present,
        faq_present,
        cta_present,
        value_proposition_present,
    ]
    trust_signals = [
        email_present,
        address_present,
        business_hours_present,
        warranty_info_present,
        returns_info_present,
        reviews_present,
        rating_present,
        legal_requisites_present,
        company_identity_present,
    ]
    contact_options_score = sum(contact_signals) / len(contact_signals)
    commercial_signal_count = sum(commercial_signals)
    trust_signal_count = sum(trust_signals)
    commercial_signals_score = commercial_signal_count / len(commercial_signals)
    trust_signals_score = trust_signal_count / len(trust_signals)
    commercial_trust_score = (commercial_signals_score + trust_signals_score + contact_options_score) / 3.0

    return {
        "phone_present": phone_present,
        "phone_count": phone_count,
        "email_present": email_present,
        "address_present": address_present,
        "business_hours_present": business_hours_present,
        "price_present": price_present,
        "currency_present": currency_present,
        "delivery_info_present": delivery_info_present,
        "payment_info_present": payment_info_present,
        "warranty_info_present": warranty_info_present,
        "returns_info_present": returns_info_present,
        "reviews_present": reviews_present,
        "rating_present": rating_present,
        "faq_present": faq_present,
        "cta_present": cta_present,
        "cta_count": cta_count,
        "messenger_present": messenger_present,
        "value_proposition_present": value_proposition_present,
        "legal_requisites_present": legal_requisites_present,
        "company_identity_present": company_identity_present,
        "contact_options_score": round(contact_options_score, 6),
        "commercial_signal_count": commercial_signal_count,
        "trust_signal_count": trust_signal_count,
        "commercial_signals_score": round(commercial_signals_score, 6),
        "trust_signals_score": round(trust_signals_score, 6),
        "commercial_trust_score": round(commercial_trust_score, 6),
    }


def merge_commercial_trust_features(
    features: dict[str, float | int],
    snapshot: dict[str, object] | None,
) -> dict[str, float | int]:
    commercial_features = build_commercial_trust_features(snapshot)
    if not commercial_features:
        return dict(features)
    return {
        **features,
        **commercial_features,
    }


def merge_snapshot_auxiliary_features(
    features: dict[str, float | int],
    snapshot: dict[str, object] | None,
) -> dict[str, float | int]:
    with_technical = merge_technical_seo_features(features, snapshot)
    return merge_commercial_trust_features(with_technical, snapshot)


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

# core/icon_resolver.py
import json
import os
import re
import difflib
from typing import Dict, Optional, Tuple


def load_registry(registry_path: Optional[str] = None) -> Dict[str, dict]:
    """Loads icon registry JSON mapping icon keys and aliases to draw.io shapes."""
    if registry_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        registry_path = os.path.join(base_dir, "assets", "icons", "registry.json")

    if os.path.exists(registry_path):
        with open(registry_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def normalize_string(text: str) -> str:
    """Removes special characters and normalizes whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[_\-\/\.,]", " ", text)
    return re.sub(r"\s+", " ", text)


def resolve_icon_type(
    type_query: str,
    registry_path: Optional[str] = None,
    threshold: float = 0.70,
) -> Tuple[str, float]:
    """Resolves a free-text or predicted icon query to a registry icon key using fuzzy matching."""
    registry = load_registry(registry_path)
    if not type_query or not registry:
        return "generic_box", 0.0

    raw_query = type_query.strip().lower()
    norm_query = normalize_string(type_query)
    query_tokens = set(norm_query.split())

    # 1. Exact match on registry key
    if raw_query in registry:
        return raw_query, 1.0
    if norm_query in registry:
        return norm_query, 1.0

    # 2. Check for exact alias match first
    for key, data in registry.items():
        aliases = [a.lower() for a in data.get("aliases", [])] + [normalize_string(a) for a in data.get("aliases", [])]
        if raw_query in aliases or norm_query in aliases:
            return key, 1.0

    best_key = "generic_box"
    best_score = 0.0

    for key, data in registry.items():
        candidates = [key.lower(), normalize_string(key)] + [a.lower() for a in data.get("aliases", [])] + [normalize_string(a) for a in data.get("aliases", [])]
        for candidate in set(candidates):
            if not candidate:
                continue

            cand_tokens = set(candidate.split())

            # Token subset match
            if cand_tokens and cand_tokens == query_tokens:
                score = 0.98
            elif cand_tokens and cand_tokens.issubset(query_tokens):
                score = 0.90
            elif query_tokens and query_tokens.issubset(cand_tokens):
                score = 0.85
            # Short acronym exact word match (length <= 3 requires word boundary)
            elif len(candidate) <= 3:
                if re.search(rf"\b{re.escape(candidate)}\b", raw_query) or re.search(rf"\b{re.escape(candidate)}\b", norm_query):
                    score = 0.95
                else:
                    score = 0.0
            elif candidate in norm_query or norm_query in candidate:
                score = 0.80
            else:
                if query_tokens & cand_tokens:
                    score = difflib.SequenceMatcher(None, norm_query, candidate).ratio()
                else:
                    score = 0.0

            if score > best_score:
                best_score = score
                best_key = key

    if best_score >= threshold:
        return best_key, round(best_score, 2)

    return "generic_box", round(best_score, 2)


class IconMatch:
    def __init__(self, key: str, score: float):
        self.matched_key = key
        self.score = score
        self.found = score > 0.0 and key != "generic_box"


def resolve_icon(type_query: str) -> IconMatch:
    """Wrapper function returning IconMatch object."""
    key, score = resolve_icon_type(type_query)
    return IconMatch(key, score)

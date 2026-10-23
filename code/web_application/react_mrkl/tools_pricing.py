import requests
from bs4 import BeautifulSoup
from datetime import datetime

def _timestamp():
    return datetime.utcnow().isoformat()


def extract_passages(text: str, query: str, k: int = 3):
    """
    Very lightweight keyword-based passage extraction.
    Returns top-k matching snippets.
    """
    lines = text.split("\n")
    results = []

    for line in lines:
        if query.lower() in line.lower():
            results.append(line.strip())

    if not results:
        return ["No matching pricing information found."]

    return results[:k]


def policy_retriever(url: str, query: str, k: int = 3):
    """
    Fetch a pricing/policy page and extract matching text snippets.

    HW7 Requirements:
    - Return passages = [{text, source, score}]
    - Must treat HTML as untrusted input
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        raw_text = soup.get_text("\n")

        passages = extract_passages(raw_text, query, k)
        output = []

        for p in passages:
            output.append({
                "text": p,
                "source": url,
                "score": 1.0  # Simplified scoring
            })

        return {
            "success": True,
            "data": {
                "passages": output
            },
            "error": None,
            "source": "policy_retriever",
            "ts": _timestamp()
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Retrieval failed: {str(e)}",
            "source": "policy_retriever",
            "ts": _timestamp()
        }
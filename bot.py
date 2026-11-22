import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path("src/data/integrations.json")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
PREFERRED_MODELS = [
    "qwen/qwen3-8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

FALLBACK_INTEGRATIONS = [
    {
        "slug": "stripe-slack-payment-alerts",
        "name": "Stripe to Slack Payment Alerts",
        "category": "Billing & Notifications",
        "summary": "Send instant Slack alerts whenever a new subscription payment succeeds or fails.",
        "setup_steps": [
            "Create a Slack incoming webhook URL for your billing channel.",
            "Subscribe to checkout.session.completed and invoice.payment_failed events in Stripe.",
            "Post formatted event payloads to Slack with customer and plan details.",
        ],
        "monetization_angle": "Offer as a lightweight paid add-on for indie SaaS founders wanting zero-config alerts.",
    },
    {
        "slug": "notion-linear-bug-triage",
        "name": "Notion to Linear Bug Triage",
        "category": "Product & Support",
        "summary": "Turn tagged Notion customer feedback rows into prioritized Linear issues automatically.",
        "setup_steps": [
            "Filter Notion database items marked as Bug and Ready for Triage.",
            "Map title, severity tag, and customer context to Linear issue fields.",
            "Write the created Linear issue URL back to Notion to prevent duplicates.",
        ],
        "monetization_angle": "Target lean product teams that log feedback in Notion but track engineering sprints in Linear.",
    },
]


def load_existing() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
    except Exception:
        pass
    return []


def extract_json_array(text: str) -> list[dict]:
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("Expected JSON array from model")
    return data


def get_candidate_models(api_key: str) -> list[str]:
    models = list(PREFERRED_MODELS)
    req = urllib.request.Request(
        GROQ_MODELS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MicroSaaSDirectoryBot/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("data", []):
            model_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(model_id, str) and model_id.strip() and model_id not in models:
                models.append(model_id.strip())
    except Exception:
        pass
    return models


def try_model(api_key: str, model: str, prompt: str) -> list[dict] | None:
    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": "You output strictly valid JSON arrays."},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        GROQ_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MicroSaaSDirectoryBot/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        items = extract_json_array(content)
        return items if items else None
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"Model {model} failed ({e.code}): {err_body}")
        return None
    except Exception as e:
        print(f"Model {model} error: {e}")
        return None


def generate_with_ai(existing_names: list[str]) -> list[dict]:
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        print("AI_API_KEY is missing or empty.")
        return []

    avoid_text = ", ".join(existing_names[-20:]) if existing_names else "None"
    prompt = (
        "Generate 2 practical Micro-SaaS integration ideas as a strict JSON array. "
        f"Avoid these existing names: {avoid_text}. "
        "Each item must have exact keys: "
        "'slug' (lowercase kebab-case), 'name', 'category', 'summary' (1-2 sentences), "
        "'setup_steps' (array of 3 concise steps), 'monetization_angle' (1 sentence). "
        "Return ONLY valid JSON without extra text."
    )

    for model in get_candidate_models(api_key):
        items = try_model(api_key, model, prompt)
        if items:
            print(f"Generated ideas using model: {model}")
            return items

    return []


def normalize_item(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name", "")).strip()
    if not name:
        return None

    slug_raw = str(item.get("slug") or name).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug_raw).strip("-")
    if not slug:
        return None

    steps_raw = item.get("setup_steps", [])
    if not isinstance(steps_raw, list):
        steps_raw = []
    steps = [str(s).strip() for s in steps_raw if str(s).strip()][:5]
    if not steps:
        steps = [
            "Connect source webhook.",
            "Transform payload.",
            "Deliver to target service.",
        ]

    return {
        "slug": slug,
        "name": name,
        "category": str(item.get("category", "Automation")).strip() or "Automation",
        "summary": str(item.get("summary", "")).strip(),
        "setup_steps": steps,
        "monetization_angle": str(item.get("monetization_angle", "")).strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    existing = load_existing()
    existing_slugs = {str(x.get("slug", "")).strip().lower() for x in existing if isinstance(x, dict)}
    existing_names = [str(x.get("name", "")).strip() for x in existing if isinstance(x, dict) and x.get("name")]

    generated = generate_with_ai(existing_names)
    candidates = generated if generated else FALLBACK_INTEGRATIONS

    added = 0
    for raw_item in candidates:
        norm = normalize_item(raw_item)
        if not norm:
            continue
        if norm["slug"] in existing_slugs:
            continue
        existing.append(norm)
        existing_slugs.add(norm["slug"])
        added += 1

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(existing)} integrations ({added} new).")


if __name__ == "__main__":
    main()

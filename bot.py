import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path("src/data/integrations.json")

FALLBACK_INTEGRATIONS = [
    {
        "slug": "stripe-slack-payment-alerts",
        "name": "Stripe to Slack Payment Alerts",
        "category": "Billing & Notifications",
        "summary": "Send instant Slack alerts whenever a new subscription payment succeeds or fails.",
        "setup_steps": [
            "Create a Slack incoming webhook URL for your billing channel.",
            "Subscribe to checkout.session.completed and invoice.payment_failed events in Stripe.",
            "Post formatted event payloads to Slack with customer and plan details."
        ],
        "monetization_angle": "Offer as a lightweight paid add-on for indie SaaS founders wanting zero-config alerts."
    },
    {
        "slug": "notion-linear-bug-triage",
        "name": "Notion to Linear Bug Triage",
        "category": "Product & Support",
        "summary": "Turn tagged Notion customer feedback rows into prioritized Linear issues automatically.",
        "setup_steps": [
            "Filter Notion database items marked as Bug and Ready for Triage.",
            "Map title, severity tag, and customer context to Linear issue fields.",
            "Write the created Linear issue URL back to Notion to prevent duplicates."
        ],
        "monetization_angle": "Target lean product teams that log feedback in Notion but track engineering sprints in Linear."
    }
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


def generate_with_ai(existing_names: list[str]) -> list[dict]:
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        return []

    api_url = os.getenv("AI_API_URL", "https://api.groq.com/openai/v1/chat/completions").strip()
    model = os.getenv("AI_MODEL", "llama-3.3-70b-versatile").strip()
print(f"DEBUG url={api_url!r} model={model!r}")
    avoid_text = ", ".join(existing_names[-20:]) if existing_names else "None"
    prompt = (
        "Generate 2 practical Micro-SaaS integration ideas as a strict JSON array. "
        f"Avoid these existing names: {avoid_text}. "
        "Each item must have exact keys: "
        "'slug' (lowercase kebab-case), 'name', 'category', 'summary' (1-2 sentences), "
        "'setup_steps' (array of 3 concise steps), 'monetization_angle' (1 sentence). "
        "Return ONLY valid JSON without extra text."
    )

    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": "You output strictly valid JSON arrays."},
            {"role": "user", "content": prompt},
        ],
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MicroSaaSDirectoryBot/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    return extract_json_array(content)


def normalize_item(item: dict) -> dict | None:
    name = str(item.get("name", "")).strip()
    if not name:
        return None
    slug_raw = str(item.get("slug") or name).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug_raw).strip("-")
    if not slug:
        return None

    steps_raw = item.get("setup_steps", [])
    steps = [str(s).strip() for s in steps_raw if str(s).strip()][:5]
    if not steps:
        steps = ["Connect source webhook.", "Transform payload.", "Deliver to target service."]

    return {
        "slug": slug,
        "name": name,
        "category": str(item.get("category", "Workflow Automation")).strip() or "Workflow Automation",
        "summary": str(item.get("summary", "Automated Micro-SaaS integration.")).strip(),
        "setup_steps": steps,
        "monetization_angle": str(item.get("monetization_angle", "Built for fast B2B workflow adoption.")).strip(),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


def main() -> None:
    existing = load_existing()
    seen_slugs = {item.get("slug") for item in existing if item.get("slug")}
    existing_names = [item.get("name", "") for item in existing if item.get("name")]

    candidates: list[dict] = []
    try:
        candidates.extend(generate_with_ai(existing_names))
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"AI generation fallback triggered: {exc}")

    if not candidates:
        candidates.extend(FALLBACK_INTEGRATIONS)

    added = 0
    for raw_item in candidates:
        if not isinstance(raw_item, dict):
            continue
        norm = normalize_item(raw_item)
        if not norm or norm["slug"] in seen_slugs:
            continue
        existing.insert(0, norm)
        seen_slugs.add(norm["slug"])
        added += 1

    if added == 0 and not existing:
        for fallback in FALLBACK_INTEGRATIONS:
            norm = normalize_item(fallback)
            if norm and norm["slug"] not in seen_slugs:
                existing.append(norm)
                seen_slugs.add(norm["slug"])

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(existing)} integrations ({added} new).")


if __name__ == "__main__":
    main()

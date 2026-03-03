"""Claude Vision — parse receipts / bank screenshots / tax invoices."""
import base64
import json
import re
import time
from datetime import date

import anthropic

from config import ANTHROPIC_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are an expense data extractor for a Thai restaurant business.
Extract structured data from receipt images, bank transfer screenshots, or tax invoices.

Always respond with a single JSON object and nothing else. Use null for unknown fields.

JSON schema:
{
  "date": "DD.MM.YYYY or null",
  "amount": number or null,
  "currency": "THB" | "USD" | "AED" | null,
  "supplier_name": "string or null",
  "details": "string or null",
  "comment": "additional notes or null",
  "flow_type": "OpEx" | "CapEx" | null,
  "category_name": "Equipment" | "Construction" | "Furniture" | "Decoration" | "IT Software" | "Legal" | "Rent" | "Water/electricity bills" | null
}

Rules:
- date: convert any format to DD.MM.YYYY
- amount: numeric only, no currency symbols
- currency: default THB if not visible
- details: Describe WHAT was paid for in English, max 100 chars. Include:
  * The service or product name (e.g. "Water supply", "Electricity", "Rent", "Vegetables")
  * Billing period if shown (e.g. "for Dec 2025", "Jan 1–31 2026")
  * Payment type if it's not a regular charge (e.g. "installation fee", "reconnection fee", "fine", "penalty", "deposit", "advance")
  * Example good values: "Water supply for Dec 2025", "Electricity Jan 2026 + reconnection fee", "Monthly rent Feb 2026", "Equipment deposit"
- comment: invoice/reference number, tax ID, branch, meter number, or any other useful reference info
- flow_type: CapEx for equipment/furniture/construction/one-time assets; OpEx for rent/utilities/consumables/services
- category_name: best match from the list above
"""


def parse_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Parse a receipt/invoice image or PDF with Claude.
    Returns a dict with extracted fields (some may be None).
    Retries up to 3 times on overload (529) with exponential backoff.
    """
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    # PDFs use the "document" content type; images use "image"
    if "pdf" in mime_type.lower():
        file_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64,
            },
        }
    else:
        file_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": b64,
            },
        }

    last_err = None
    for attempt in range(3):
        try:
            message = _get_client().messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            file_block,
                            {
                                "type": "text",
                                "text": "Extract expense data from this document.",
                            },
                        ],
                    }
                ],
            )
            raw = message.content[0].text.strip()
            # Strip markdown code fences if present
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            return json.loads(raw)
        except anthropic.APIStatusError as err:
            last_err = err
            if err.status_code == 529 and attempt < 2:
                wait = 5 * (attempt + 1)   # 5s, 10s
                time.sleep(wait)
                continue
            raise
    raise last_err


def parse_text(text: str) -> dict:
    """
    Parse a free-text expense description with Claude.
    E.g.: "Lesya Bangkok bank, 5000 THB, Makro, vegetables, L1"
    """
    message = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Extract expense data from this text:\n{text}",
            }
        ],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)

"""
Payment providers behind one small interface, so the rest of the app
never talks to Razorpay directly. Stripe (or anything else) can be added
later as one more class here.

  RazorpayProvider  - real Razorpay API (test or live keys)
  SimulatedProvider - no account needed; used when no keys are set, so
                      the whole payment flow can be built, tested and demoed

Razorpay is called with plain HTTP (no SDK), keeping dependencies minimal.
"""
import hashlib
import hmac
import uuid
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import AppError

RAZORPAY_API = "https://api.razorpay.com/v1"
TIMEOUT = httpx.Timeout(20.0, connect=5.0)


class PaymentProviderError(AppError):
    pass


class PaymentProvider(Protocol):
    name: str
    public_key: str | None  # sent to the browser to open checkout; never the secret

    def create_order(self, amount_paise: int, currency: str, receipt: str) -> str: ...
    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool: ...
    def refund(self, payment_id: str, amount_paise: int) -> str: ...


def _hmac_sha256_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class RazorpayProvider:
    name = "razorpay"

    def __init__(self, key_id: str, key_secret: str):
        self.public_key = key_id
        self._auth = (key_id, key_secret)  # HTTP Basic auth, as Razorpay requires
        self._secret = key_secret

    def create_order(self, amount_paise: int, currency: str, receipt: str) -> str:
        data = self._post("/orders", {"amount": amount_paise, "currency": currency, "receipt": receipt[:40]})
        return data["id"]  # e.g. "order_ABC123"

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Razorpay signs "<order_id>|<payment_id>" with our secret. Only
        Razorpay and our server know the secret, so a matching signature
        proves the payment really happened; the browser saying "paid" proves
        nothing. compare_digest avoids leaking the answer through timing."""
        expected = _hmac_sha256_hex(self._secret, f"{order_id}|{payment_id}".encode())
        return hmac.compare_digest(expected, signature)

    def refund(self, payment_id: str, amount_paise: int) -> str:
        data = self._post(f"/payments/{payment_id}/refund", {"amount": amount_paise})
        return data["id"]  # e.g. "rfnd_ABC123"

    def _post(self, path: str, body: dict) -> dict:
        try:
            resp = httpx.post(f"{RAZORPAY_API}{path}", json=body, auth=self._auth, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise PaymentProviderError("The payment service is unreachable. Please try again.") from e
        if resp.status_code >= 400:
            raise PaymentProviderError(f"Razorpay error {resp.status_code}: {resp.text[:200]}")
        return resp.json()


class SimulatedProvider:
    """Behaves like a payment provider without moving any money. Payments
    are completed through a dedicated "simulate" endpoint instead of a
    signature, and that endpoint refuses to work in production."""
    name = "simulated"
    public_key = None

    def create_order(self, amount_paise: int, currency: str, receipt: str) -> str:
        return f"sim_order_{uuid.uuid4().hex[:16]}"

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        return False  # simulated payments never come through the signature path

    def refund(self, payment_id: str, amount_paise: int) -> str:
        return f"sim_rfnd_{uuid.uuid4().hex[:16]}"


def get_provider() -> PaymentProvider:
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        return RazorpayProvider(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    return SimulatedProvider()


def provider_for(name: str) -> PaymentProvider:
    """The provider that created a given payment (refunds must go back the same way)."""
    return get_provider() if name == "razorpay" else SimulatedProvider()


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Razorpay webhooks are signed over the exact raw request body with the
    webhook secret. Without a secret configured, every webhook is rejected."""
    if not settings.RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    return hmac.compare_digest(_hmac_sha256_hex(settings.RAZORPAY_WEBHOOK_SECRET, raw_body), signature)

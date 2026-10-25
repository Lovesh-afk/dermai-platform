"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { paymentApi, ApiError, Checkout, formatINR } from "@/lib/api";
import { Alert, Button, Spinner } from "@/components/ui";

const RAZORPAY_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

// Minimal typing for Razorpay's browser SDK (loaded from their CDN)
interface RazorpaySuccess { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }
interface RazorpayInstance { open: () => void; on: (event: string, cb: () => void) => void }
declare global {
  interface Window { Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance }
}

function loadRazorpay(): Promise<boolean> {
  if (window.Razorpay) return Promise.resolve(true);
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = RAZORPAY_SCRIPT;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

function minutesLeft(iso: string | null): number | null {
  if (!iso) return null;
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 60000));
}

/** Pays for one booking. Real Razorpay Checkout when the server has
 * Razorpay keys; otherwise a clearly labelled simulated checkout. Either
 * way the SERVER decides whether the payment counts, never this component. */
export function PaymentCheckout({ paymentId, onPaid }: { paymentId: string; onPaid: () => void }) {
  const { accessToken, user } = useAuth();
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [, setTick] = useState(0); // re-render each minute for the countdown

  useEffect(() => {
    if (!accessToken) return;
    paymentApi
      .checkout(accessToken, paymentId)
      .then(setCheckout)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load the payment."));
    const timer = setInterval(() => setTick((t) => t + 1), 30_000);
    return () => clearInterval(timer);
  }, [accessToken, paymentId]);

  async function payWithRazorpay(c: Checkout) {
    setBusy(true);
    setError(null);
    if (!(await loadRazorpay()) || !window.Razorpay) {
      setBusy(false);
      return setError("Couldn't load Razorpay. Check your connection and try again.");
    }
    const rzp = new window.Razorpay({
      key: c.key_id,
      amount: c.amount_paise,
      currency: c.currency,
      order_id: c.order_id,
      name: "DermAI",
      description: c.description,
      prefill: { name: user?.full_name, email: user?.email },
      theme: { color: "#2F5D50" },
      handler: async (resp: RazorpaySuccess) => {
        try {
          await paymentApi.verify(accessToken!, paymentId, resp); // server checks Razorpay's signature
          onPaid();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "We couldn't confirm the payment.");
        } finally {
          setBusy(false);
        }
      },
      modal: { ondismiss: () => setBusy(false) },
    });
    rzp.on("payment.failed", () => setError("The payment didn't go through. You can try again."));
    rzp.open();
  }

  async function simulate(outcome: "success" | "failure") {
    setBusy(true);
    setError(null);
    try {
      const result = await paymentApi.simulate(accessToken!, paymentId, outcome);
      if (result.status === "paid") onPaid();
      else setError("Simulated payment failed. You can try again.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't complete the payment.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !checkout) return <Alert>{error}</Alert>;
  if (!checkout) return <Spinner className="h-5 w-5 text-pine-600" />;

  const left = minutesLeft(checkout.expires_at);
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg bg-sage-50 px-4 py-3">
        <p className="text-sm text-ink-soft">{checkout.description}</p>
        <p className="font-display text-2xl text-ink">{formatINR(checkout.amount_paise)}</p>
        {left !== null && (
          <p className="text-xs text-ochre-700">
            Your slot is held for {left} more minute{left === 1 ? "" : "s"}. Pay before then to keep it.
          </p>
        )}
      </div>

      {checkout.provider === "razorpay" ? (
        <Button onClick={() => payWithRazorpay(checkout)} disabled={busy}>
          {busy ? "Opening Razorpay…" : `Pay ${formatINR(checkout.amount_paise)} (card / UPI)`}
        </Button>
      ) : (
        <>
          <p className="rounded-lg border border-dashed border-ochre-300 px-3 py-2 text-xs text-ochre-700">
            Simulated checkout: no payment account is configured, so no real money is involved.
          </p>
          <div className="flex gap-2">
            <Button className="flex-1" onClick={() => simulate("success")} disabled={busy}>
              {busy ? "Processing…" : `Pay ${formatINR(checkout.amount_paise)}`}
            </Button>
            <Button variant="secondary" onClick={() => simulate("failure")} disabled={busy}>Simulate failure</Button>
          </div>
        </>
      )}
      {error && <Alert>{error}</Alert>}
    </div>
  );
}

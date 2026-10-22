"use client";

import { useState } from "react";
import Link from "next/link";
import { Prediction, fileUrl } from "@/lib/api";

/** Below this, the result is additionally flagged as uncertain. */
const LOW_SCORE_THRESHOLD = 0.6;

/** User-facing wording lives here, in the frontend, on purpose: it can be
 * made safer without retraining or redeploying the model, and it also
 * applies to results that were stored before the wording changed.
 *
 * "normal" is never phrased as "no condition": the model only checks 4
 * conditions, so the honest statement is that it found none of THOSE. */
const RESULT_TITLES: Record<string, string> = {
  acne: "Possible acne",
  eczema: "Possible eczema",
  fungal: "Possible fungal infection",
  normal: "No signs of acne, eczema or fungal infection found",
};

const CLASS_NAMES: Record<string, string> = {
  acne: "Acne",
  eczema: "Eczema",
  fungal: "Fungal infection",
  normal: "None of these",
};

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** One AI analysis: photo / Grad-CAM heatmap toggle, the result, every
 * class score, guidance, and safety messaging. Shared by the patient's
 * photo page and the doctor's patient view. */
export function AnalysisResult({
  photoUrl,
  prediction,
  showBookingLink = false,
}: {
  photoUrl: string;
  prediction: Prediction;
  showBookingLink?: boolean; // patients get a "book a dermatologist" prompt; doctors don't need one
}) {
  const [showHeatmap, setShowHeatmap] = useState(false);
  const isLowScore = prediction.confidence < LOW_SCORE_THRESHOLD;
  const ranked = Object.entries(prediction.all_probabilities).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex flex-col gap-4">
      <div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={fileUrl(showHeatmap ? prediction.gradcam_url : photoUrl)}
          alt={showHeatmap ? "Heatmap of the areas the AI focused on" : "Uploaded skin photo"}
          className="h-56 w-full rounded-lg object-cover"
        />
        <div className="mt-2 inline-flex rounded-full bg-sage-100 p-1 text-xs font-medium" role="group" aria-label="Image view">
          {[
            { key: false, label: "Photo" },
            { key: true, label: "AI focus heatmap" },
          ].map((opt) => (
            <button
              key={opt.label}
              type="button"
              aria-pressed={showHeatmap === opt.key}
              onClick={() => setShowHeatmap(opt.key)}
              className={`rounded-full px-3 py-1 ${showHeatmap === opt.key ? "bg-white text-ink shadow-sm" : "text-ink-soft"}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {showHeatmap && (
          <p className="mt-2 text-xs text-ink-soft">Yellow areas are where the model looked most when making its prediction.</p>
        )}
      </div>

      <div>
        <p className="font-display text-lg text-ink">{RESULT_TITLES[prediction.predicted_class] ?? prediction.label}</p>
        <p className="text-sm text-ink-soft">Model score: {pct(prediction.confidence)}</p>
        {/* Softmax scores aren't calibrated probabilities: a model can score 100% and still be wrong. */}
        <p className="text-xs text-ink-soft">How strongly the model leans toward this answer, not the chance that it&rsquo;s correct.</p>
      </div>

      {/* Always shown, whatever the score: a high score is not a guarantee. */}
      <p className="rounded-lg bg-ochre-50 px-3 py-2 text-sm text-ochre-700">
        This AI only checks for acne, eczema and fungal infection, and it can be wrong, even with a high score.
        It can&rsquo;t rule out other skin conditions. Only a dermatologist can diagnose you.
        {isLowScore && " This result is especially uncertain: try a clearer, well-lit close-up."}
      </p>

      <ul className="flex flex-col gap-1.5" aria-label="Model score for each condition">
        {ranked.map(([cls, p]) => (
          <li key={cls} className="text-xs">
            <div className="flex justify-between text-ink-soft">
              <span>{CLASS_NAMES[cls] ?? cls}</span>
              <span>{pct(p)}</span>
            </div>
            <div className="mt-0.5 h-1.5 rounded-full bg-sage-100">
              <div className="h-1.5 rounded-full bg-pine-600" style={{ width: pct(p) }} />
            </div>
          </li>
        ))}
      </ul>

      <p className="text-sm text-ink">{prediction.guidance}</p>

      {showBookingLink && (
        <Link
          href="/patient/doctors"
          className="inline-flex w-fit items-center rounded-full bg-pine-700 px-4 py-2 text-sm font-medium text-white hover:bg-pine-800"
        >
          Book a dermatologist
        </Link>
      )}

      <p className="border-t border-sage-100 pt-3 text-xs text-ink-soft">{prediction.disclaimer}</p>
    </div>
  );
}

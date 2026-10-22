"use client";

import { useState } from "react";
import { Prediction, fileUrl } from "@/lib/api";

/** Below this, the result is flagged as uncertain. A softmax "confidence"
 * of 0.46 means the model is close to guessing between classes. */
const LOW_CONFIDENCE_THRESHOLD = 0.6;

const CLASS_NAMES: Record<string, string> = {
  acne: "Acne",
  eczema: "Eczema",
  fungal: "Fungal infection",
  normal: "No condition",
};

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** One AI analysis: photo / Grad-CAM heatmap toggle, the top result,
 * every class probability, guidance, and the disclaimer. Shared by the
 * patient's photo page and the doctor's patient view. */
export function AnalysisResult({ photoUrl, prediction }: { photoUrl: string; prediction: Prediction }) {
  const [showHeatmap, setShowHeatmap] = useState(false);
  const isLowConfidence = prediction.confidence < LOW_CONFIDENCE_THRESHOLD;
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
        <p className="font-display text-lg text-ink">{prediction.label}</p>
        <p className="text-sm text-ink-soft">Model confidence: {pct(prediction.confidence)}</p>
      </div>

      {isLowConfidence && (
        <p className="rounded-lg bg-ochre-50 px-3 py-2 text-sm text-ochre-700">
          Low confidence: the model isn&rsquo;t sure about this photo. Treat this result with extra caution, and try a
          clearer, well-lit close-up if you can.
        </p>
      )}

      <ul className="flex flex-col gap-1.5" aria-label="Probability for each condition">
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
      <p className="border-t border-sage-100 pt-3 text-xs text-ink-soft">{prediction.disclaimer}</p>
    </div>
  );
}

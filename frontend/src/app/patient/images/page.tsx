"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { patientApi, fileUrl, ApiError, SkinImage } from "@/lib/api";
import { Card, Button, StatusPill, Spinner, EmptyState, Alert } from "@/components/ui";
import { AnalysisResult } from "@/components/AnalysisResult";

/** How often to re-check while any photo is still being analyzed. */
const POLL_INTERVAL_MS = 3000;

export default function PatientImagesPage() {
  const { accessToken } = useAuth();
  const { data: images, loading, refetch } = useAuthedData((t) => patientApi.myImages(t));
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Analysis runs in the background on the server, so poll until every
  // photo has finished. Polling stops by itself once nothing is pending.
  const anyAnalyzing = images?.some((img) => img.status === "queued_for_analysis") ?? false;
  useEffect(() => {
    if (!anyAnalyzing) return;
    const timer = setInterval(refetch, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [anyAnalyzing, refetch]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !accessToken) return;
    setUploading(true);
    setError(null);
    try {
      await patientApi.uploadImage(accessToken, file); // analysis starts automatically
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleAnalyze(imageId: string) {
    if (!accessToken) return;
    setError(null);
    try {
      await patientApi.analyzeImage(accessToken, imageId);
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start the analysis.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-ink">Skin photos</h1>
          <p className="mt-1 text-ink-soft">
            Upload a clear photo and our AI gives a preliminary read in a few seconds. It&rsquo;s not a diagnosis.
          </p>
        </div>
        <div>
          <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={handleFileChange} />
          <Button onClick={() => inputRef.current?.click()} disabled={uploading}>
            {uploading ? "Uploading…" : "Upload photo"}
          </Button>
        </div>
      </div>

      {error && <Alert>{error}</Alert>}

      {loading && !images ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !images || images.length === 0 ? (
        <EmptyState title="No photos yet" body="Upload a clear, well-lit photo of the area you're concerned about." />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {images.map((img) => (
            <ImageCard key={img.id} image={img} onAnalyze={() => handleAnalyze(img.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function ImageCard({ image, onAnalyze }: { image: SkinImage; onAnalyze: () => void }) {
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs text-ink-soft">{new Date(image.created_at).toLocaleDateString()}</p>
        <StatusPill status={image.status} />
      </div>

      {image.status === "analyzed" && image.prediction ? (
        <AnalysisResult photoUrl={image.file_url} prediction={image.prediction} showBookingLink />
      ) : (
        <div className="flex flex-col gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={fileUrl(image.file_url)} alt="Uploaded skin photo" className="h-56 w-full rounded-lg object-cover" />

          {image.status === "queued_for_analysis" && (
            <p className="flex items-center gap-2 text-sm text-ink-soft">
              <Spinner className="h-4 w-4 text-pine-600" /> Analyzing your photo — usually a few seconds.
            </p>
          )}

          {image.status === "failed" && (
            <>
              <Alert>{image.analysis_error ?? "Analysis failed."}</Alert>
              <Button variant="secondary" size="sm" onClick={onAnalyze}>Retry analysis</Button>
            </>
          )}

          {/* Photos uploaded before AI analysis existed */}
          {image.status === "uploaded" && (
            <Button variant="secondary" size="sm" onClick={onAnalyze}>Analyze this photo</Button>
          )}
        </div>
      )}
    </Card>
  );
}

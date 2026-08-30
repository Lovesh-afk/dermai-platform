"use client";

import { useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { patientApi, fileUrl, ApiError } from "@/lib/api";
import { Card, Button, StatusPill, Spinner, EmptyState, Alert } from "@/components/ui";

export default function PatientImagesPage() {
  const { accessToken } = useAuth();
  const { data: images, loading, refetch } = useAuthedData((t) => patientApi.myImages(t));
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !accessToken) return;
    setUploading(true);
    setError(null);
    try {
      await patientApi.uploadImage(accessToken, file);
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl text-ink">Skin photos</h1>
          <p className="mt-1 text-ink-soft">Upload a photo for your records — AI analysis is coming in a later phase.</p>
        </div>
        <div>
          <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={handleFileChange} />
          <Button onClick={() => inputRef.current?.click()} disabled={uploading}>
            {uploading ? "Uploading…" : "Upload photo"}
          </Button>
        </div>
      </div>

      {error && <Alert>{error}</Alert>}

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !images || images.length === 0 ? (
        <EmptyState title="No photos yet" body="Upload a clear, well-lit photo of the area you're concerned about." />
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {images.map((img) => (
            <Card key={img.id} className="overflow-hidden p-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={fileUrl(img.file_url)} alt="Uploaded skin photo" className="h-40 w-full object-cover" />
              <div className="flex items-center justify-between p-3">
                <p className="text-xs text-ink-soft">{new Date(img.created_at).toLocaleDateString()}</p>
                <StatusPill status={img.status} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

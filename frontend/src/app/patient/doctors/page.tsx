"use client";

import { useEffect, useState } from "react";
import { hospitalApi, doctorApi, appointmentApi, patientApi, HospitalOut, DoctorProfile, ApiError, Condition, Recommendations } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, Button, Select, Field, Input, Alert, Spinner, EmptyState } from "@/components/ui";

export default function FindDoctorPage() {
  const { accessToken } = useAuth();
  const [hospitals, setHospitals] = useState<HospitalOut[]>([]);
  const [hospitalId, setHospitalId] = useState("");
  const [doctors, setDoctors] = useState<DoctorProfile[]| null>(null);
  const [loadingDoctors, setLoadingDoctors] = useState(false);
  const [bookingFor, setBookingFor] = useState<DoctorProfile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    hospitalApi
      .list()
      .then((list) => {
        setHospitals(list);
        if (list.length) setHospitalId(list[0].id);
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Couldn't load hospitals."));
  }, []);

  useEffect(() => {
    if (!hospitalId) return;
    setLoadingDoctors(true);
    doctorApi
      .listByHospital(hospitalId)
      .then(setDoctors)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) return; // handled by api.ts
        setLoadError(err instanceof ApiError ? err.message : "Couldn't load doctors for this hospital.");
      })
      .finally(() => setLoadingDoctors(false));
  }, [hospitalId]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Find a doctor</h1>
        <p className="mt-1 text-ink-soft">Browse by hospital and book a time.</p>
      </div>

      {loadError && <Alert>{loadError}</Alert>}

      {accessToken && <RecommendedDoctors token={accessToken} onBook={setBookingFor} />}

      <h2 className="font-display text-xl text-ink">Browse by hospital</h2>

      {hospitals.length === 0 ? (
        <Alert>No hospitals are set up yet.</Alert>
      ) : (
        <div className="max-w-xs">
          <Field label="Hospital">
            <Select value={hospitalId} onChange={(e) => setHospitalId(e.target.value)}>
              {hospitals.map((h) => (
                <option key={h.id} value={h.id}>{h.name}</option>
              ))}
            </Select>
          </Field>
        </div>
      )}

      {loadingDoctors ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !doctors || doctors.length === 0 ? (
        <EmptyState title="No doctors here yet" body="This hospital doesn't have any doctors registered yet." />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {doctors.map((d) => (
            <Card key={d.id}>
              <p className="font-display text-lg text-ink">{doctorName(d)}</p>
              <p className="mt-0.5 text-sm text-ink-soft">{d.specialization} · License {d.license_number}</p>
              {d.years_experience != null && <p className="mt-1 text-sm text-ink-soft">{d.years_experience} years experience</p>}
              {d.consultation_fee != null && <p className="mt-1 text-sm text-ink-soft">${d.consultation_fee} consultation</p>}
              {d.bio && <p className="mt-2 text-sm text-ink-soft">{d.bio}</p>}
              <div className="mt-4">
                {d.is_accepting_appointments ? (
                  <Button size="sm" onClick={() => setBookingFor(d)}>Book appointment</Button>
                ) : (
                  <span className="text-sm text-ink-soft">Not accepting appointments</span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {bookingFor && accessToken && (
        <BookingModal doctor={bookingFor} token={accessToken} onClose={() => setBookingFor(null)} />
      )}
    </div>
  );
}

function BookingModal({ doctor, token, onClose }: { doctor: DoctorProfile; token: string; onClose: () => void }) {
  const [dateTime, setDateTime] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await appointmentApi.book(token, { doctor_id: doctor.id, scheduled_at: new Date(dateTime).toISOString(), reason: reason || undefined });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't book that slot.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-ink/30 px-6" onClick={onClose}>
      <Card className="w-full max-w-sm" >
        <div onClick={(e) => e.stopPropagation()}>
          {success ? (
            <>
              <p className="font-display text-xl text-ink">Booked</p>
              <p className="mt-1 text-sm text-ink-soft">Your appointment request has been sent. You&rsquo;ll see it in your appointments list.</p>
              <Button className="mt-4 w-full" onClick={onClose}>Done</Button>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <p className="font-display text-xl text-ink">Book with {doctorName(doctor)}</p>
              <Field label="Date and time">
                <Input type="datetime-local" required value={dateTime} onChange={(e) => setDateTime(e.target.value)} />
              </Field>
              <Field label="Reason (optional)">
                <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Suspicious mole" />
              </Field>
              {error && <Alert>{error}</Alert>}
              <div className="flex gap-2">
                <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
                <Button type="submit" disabled={submitting} className="flex-1">{submitting ? "Booking…" : "Book"}</Button>
              </div>
            </form>
          )}
        </div>
      </Card>
    </div>
  );
}

function doctorName(d: DoctorProfile) {
  return d.full_name ? `Dr. ${d.full_name.replace(/^Dr\.?\s+/i, "")}` : d.specialization;
}

const CONDITION_OPTIONS: { value: Condition | null; label: string }[] = [
  { value: null, label: "Any" },
  { value: "acne", label: "Acne" },
  { value: "eczema", label: "Eczema" },
  { value: "fungal", label: "Fungal infection" },
];

/** Top matches, ranked by the backend with plain-language reasons.
 * The condition comes from the URL (the "Book a dermatologist" button on a
 * photo result), the chips here, or else the patient's latest photo analysis. */
function RecommendedDoctors({ token, onBook }: { token: string; onBook: (d: DoctorProfile) => void }) {
  // "auto" = let the server use the latest photo analysis; "none" = the
  // patient picked "Any"; otherwise a condition the patient picked.
  const [choice, setChoice] = useState<Condition | "auto" | "none" | undefined>(undefined); // undefined = not read yet
  const [data, setData] = useState<Recommendations | null>(null);
  const [loading, setLoading] = useState(true);

  // Read ?condition= once on load (read directly to avoid Next's Suspense requirement for useSearchParams)
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("condition");
    const valid = CONDITION_OPTIONS.some((o) => o.value !== null && o.value === fromUrl);
    setChoice(valid ? (fromUrl as Condition) : "auto");
  }, []);

  useEffect(() => {
    if (choice === undefined) return;
    setLoading(true);
    patientApi
      .recommendedDoctors(token, choice)
      .then(setData)
      .catch(() => setData(null)) // non-critical: the full browse list below still works
      .finally(() => setLoading(false));
  }, [token, choice]);

  const activeCondition = data?.condition ?? null;
  const subtitle =
    data?.condition_source === "photo"
      ? `Based on your latest skin photo analysis (possible ${CONDITION_OPTIONS.find((o) => o.value === activeCondition)?.label.toLowerCase()}). The AI can be wrong.`
      : "Ranked by relevant experience, availability and whether you've seen them before.";

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="font-display text-xl text-ink">Recommended for you</h2>
        <p className="text-sm text-ink-soft">{subtitle}</p>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Condition">
        {CONDITION_OPTIONS.map((o) => {
          const selected = o.value === null ? !activeCondition : activeCondition === o.value;
          return (
            <button
              key={o.label}
              type="button"
              aria-pressed={selected}
              onClick={() => setChoice(o.value ?? "none")}
              className={`rounded-full px-3 py-1 text-sm ${selected ? "bg-pine-600 text-porcelain" : "bg-sage-100 text-ink hover:bg-sage-200"}`}
            >
              {o.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !data || data.doctors.length === 0 ? (
        <p className="text-sm text-ink-soft">No doctors are available to recommend right now.</p>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {data.doctors.slice(0, 3).map((rec, i) => (
            <Card key={rec.doctor.id}>
              {i === 0 && <p className="mb-1 text-xs font-medium uppercase tracking-wide text-pine-700">Best match</p>}
              <p className="font-display text-lg text-ink">{doctorName(rec.doctor)}</p>
              <p className="text-sm text-ink-soft">{rec.hospital_name}</p>
              <ul className="mt-3 flex flex-col gap-1 text-sm text-ink">
                {rec.reasons.map((r) => (
                  <li key={r} className="flex gap-1.5">
                    <span aria-hidden className="text-pine-600">✓</span>
                    {r}
                  </li>
                ))}
              </ul>
              {rec.doctor.consultation_fee != null && (
                <p className="mt-2 text-sm text-ink-soft">Fee: {rec.doctor.consultation_fee}</p>
              )}
              <Button size="sm" className="mt-4" onClick={() => onBook(rec.doctor)}>Book appointment</Button>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { hospitalApi, doctorApi, appointmentApi, HospitalOut, DoctorProfile, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, Button, Select, Field, Input, Alert, Spinner, EmptyState } from "@/components/ui";

export default function FindDoctorPage() {
  const { accessToken } = useAuth();
  const [hospitals, setHospitals] = useState<HospitalOut[]>([]);
  const [hospitalId, setHospitalId] = useState("");
  const [doctors, setDoctors] = useState<DoctorProfile[]| null>(null);
  const [loadingDoctors, setLoadingDoctors] = useState(false);
  const [bookingFor, setBookingFor] = useState<DoctorProfile | null>(null);

  useEffect(() => {
    hospitalApi.list().then((list) => {
      setHospitals(list);
      if (list.length) setHospitalId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (!hospitalId) return;
    setLoadingDoctors(true);
    doctorApi.listByHospital(hospitalId).then(setDoctors).finally(() => setLoadingDoctors(false));
  }, [hospitalId]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Find a doctor</h1>
        <p className="mt-1 text-ink-soft">Browse by hospital and book a time.</p>
      </div>

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
              <p className="font-display text-lg text-ink">{d.specialization}</p>
              <p className="mt-0.5 text-sm text-ink-soft">License {d.license_number}</p>
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
              <p className="font-display text-xl text-ink">Book with {doctor.specialization}</p>
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

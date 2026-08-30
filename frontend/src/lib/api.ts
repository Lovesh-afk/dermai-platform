/**
 * Typed API client for the FastAPI backend. Every request goes
 * through apiFetch() so auth-header injection, error normalization,
 * and the base URL happen in one place — no endpoint call site
 * repeats that logic. Types here mirror the backend's Pydantic
 * schemas (see backend/app/schemas/) — keep them in sync by hand
 * when a schema changes, there's no codegen wired up yet.
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_BASE = `${API_URL}/api/v1`;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}, accessToken?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
  });

  if (res.status === 204) return undefined as T;

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    throw new ApiError(res.status, body?.detail ?? res.statusText ?? "Request failed");
  }
  return body as T;
}

function authed<T>(path: string, token: string, options: RequestInit = {}) {
  return request<T>(path, options, token);
}

// ---------------------------------------------------------------------------
// Types (mirroring backend Pydantic schemas)
// ---------------------------------------------------------------------------

export type Role = "PATIENT" | "DOCTOR" | "SUPER_ADMIN" | string;

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  hospital_id: string | null;
}

export interface LoginResponse {
  mfa_required: boolean;
  access_token?: string;
  refresh_token?: string;
  token_type: string;
  mfa_pending_token?: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface HospitalOut {
  id: string;
  name: string;
  slug: string;
  subscription_tier: string;
  is_active: boolean;
}

export interface PatientProfile {
  id: string;
  user_id: string;
  date_of_birth: string | null;
  gender: string | null;
  phone: string | null;
  address: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  known_allergies: string | null;
}

export interface DoctorProfile {
  id: string;
  user_id: string;
  hospital_id: string;
  specialization: string;
  license_number: string;
  years_experience: number | null;
  consultation_fee: number | null;
  bio: string | null;
  is_accepting_appointments: boolean;
}

export type AppointmentStatus = "pending" | "confirmed" | "completed" | "cancelled" | "no_show";

export interface Appointment {
  id: string;
  hospital_id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  status: AppointmentStatus;
  reason: string | null;
  cancellation_reason: string | null;
}

export interface MedicalRecord {
  id: string;
  hospital_id: string;
  patient_id: string;
  doctor_id: string | null;
  appointment_id: string | null;
  diagnosis: string | null;
  notes: string | null;
  attachment_urls: string[];
}

export type SkinImageStatus = "uploaded" | "queued_for_analysis" | "analyzed";

export interface SkinImage {
  id: string;
  patient_id: string;
  file_url: string;
  content_type: string;
  status: SkinImageStatus;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const authApi = {
  register: (data: { email: string; password: string; full_name: string; hospital_slug?: string | null }) =>
    request<UserOut>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),

  mfaLoginVerify: (data: { mfa_pending_token: string; code: string }) =>
    request<TokenPair>("/auth/mfa/login-verify", { method: "POST", body: JSON.stringify(data) }),

  refresh: (refresh_token: string) =>
    request<TokenPair>("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token }) }),

  logout: (refresh_token: string) =>
    request<void>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token }) }),

  me: (token: string) => authed<UserOut>("/auth/me", token),

  mfaSetup: (token: string) =>
    authed<{ secret: string; provisioning_uri: string }>("/auth/mfa/setup", token, { method: "POST" }),

  mfaVerifySetup: (token: string, code: string) =>
    authed<void>("/auth/mfa/verify-setup", token, { method: "POST", body: JSON.stringify({ code }) }),

  mfaDisable: (token: string, password: string) =>
    authed<void>("/auth/mfa/disable", token, { method: "POST", body: JSON.stringify({ password }) }),

  passwordResetRequest: (email: string) =>
    request<{ message: string; dev_reset_token?: string }>("/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  passwordResetConfirm: (token: string, new_password: string) =>
    request<void>("/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ token, new_password }) }),
};

// ---------------------------------------------------------------------------
// Hospitals (temporary demo-only create — see backend DECISIONS.md)
// ---------------------------------------------------------------------------

export const hospitalApi = {
  list: () => request<HospitalOut[]>("/hospitals"),
  create: (data: { name: string; slug: string }) =>
    request<HospitalOut>("/hospitals", { method: "POST", body: JSON.stringify(data) }),
};

// ---------------------------------------------------------------------------
// Patient
// ---------------------------------------------------------------------------

export const patientApi = {
  createProfile: (token: string, data: Partial<Omit<PatientProfile, "id" | "user_id">>) =>
    authed<PatientProfile>("/patients/me", token, { method: "POST", body: JSON.stringify(data) }),

  getProfile: (token: string) => authed<PatientProfile>("/patients/me", token),

  myAppointments: (token: string) => authed<Appointment[]>("/patients/me/appointments", token),

  myMedicalRecords: (token: string) => authed<MedicalRecord[]>("/patients/me/medical-records", token),

  uploadImage: (token: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return authed<SkinImage>("/patients/me/images", token, { method: "POST", body: form });
  },

  myImages: (token: string) => authed<SkinImage[]>("/patients/me/images", token),

  updateProfile: (token: string, data: Partial<Omit<PatientProfile, "id" | "user_id">>) =>
    authed<PatientProfile>("/patients/me", token, { method: "PATCH", body: JSON.stringify(data) }),
};

// ---------------------------------------------------------------------------
// Doctors
// ---------------------------------------------------------------------------

export const doctorApi = {
  createProfile: (token: string, data: { hospital_id: string; specialization?: string; license_number: string; years_experience?: number; consultation_fee?: number; bio?: string }) =>
    authed<DoctorProfile>("/doctors/me", token, { method: "POST", body: JSON.stringify(data) }),

  getMyProfile: (token: string) => authed<DoctorProfile>("/doctors/me", token),

  updateMyProfile: (token: string, data: Partial<Pick<DoctorProfile, "specialization" | "years_experience" | "consultation_fee" | "bio" | "is_accepting_appointments">>) =>
    authed<DoctorProfile>("/doctors/me", token, { method: "PATCH", body: JSON.stringify(data) }),

  myQueue: (token: string) => authed<Appointment[]>("/doctors/me/appointments", token),

  myPatients: (token: string) => authed<PatientProfile[]>("/doctors/me/patients", token),

  myPatient: (token: string, patientId: string) => authed<PatientProfile>(`/doctors/me/patients/${patientId}`, token),

  myCreatedRecords: (token: string) => authed<MedicalRecord[]>("/doctors/me/medical-records", token),

  listByHospital: (hospitalId: string) => request<DoctorProfile[]>(`/doctors?hospital_id=${hospitalId}`),

  get: (doctorId: string) => request<DoctorProfile>(`/doctors/${doctorId}`),
};

// ---------------------------------------------------------------------------
// Appointments
// ---------------------------------------------------------------------------

export const appointmentApi = {
  book: (token: string, data: { doctor_id: string; scheduled_at: string; reason?: string }) =>
    authed<Appointment>("/appointments", token, { method: "POST", body: JSON.stringify(data) }),

  cancel: (token: string, appointmentId: string, cancellation_reason?: string) =>
    authed<Appointment>(`/appointments/${appointmentId}/cancel`, token, {
      method: "POST",
      body: JSON.stringify({ cancellation_reason }),
    }),

  updateStatus: (token: string, appointmentId: string, status: AppointmentStatus) =>
    authed<Appointment>(`/appointments/${appointmentId}/status`, token, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};

// ---------------------------------------------------------------------------
// Medical records
// ---------------------------------------------------------------------------

export const medicalRecordApi = {
  create: (token: string, data: { patient_id: string; appointment_id?: string; diagnosis?: string; notes?: string }) =>
    authed<MedicalRecord>("/medical-records", token, { method: "POST", body: JSON.stringify(data) }),
};

export function fileUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

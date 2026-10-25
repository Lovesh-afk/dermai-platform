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

function authed<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  return request<T>(path, options, token).catch(async (err) => {
    // A 401 here almost always means the 15-minute access token
    // expired mid-session — without this, every page silently crashed
    // with an unhandled "Could not validate credentials" error the
    // moment that happened, no matter how careful any individual page
    // was about its own error handling. One refresh attempt here
    // covers every call site in the app, rather than each page having
    // to remember to do it itself.
    if (err instanceof ApiError && err.status === 401) {
      const refreshToken = localStorage.getItem("dermai_refresh_token");
      if (refreshToken) {
        try {
          const tokens = await request<{ access_token: string; refresh_token: string }>("/auth/refresh", {
            method: "POST",
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          localStorage.setItem("dermai_access_token", tokens.access_token);
          localStorage.setItem("dermai_refresh_token", tokens.refresh_token);
          return await request<T>(path, options, tokens.access_token);
        } catch {
          // Refresh token is also dead — fall through to a full logout below.
        }
      }
      localStorage.removeItem("dermai_access_token");
      localStorage.removeItem("dermai_refresh_token");
      if (typeof window !== "undefined") window.location.href = "/login";
    }
    throw err;
  });
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

export interface PlatformStats {
  total_hospitals: number;
  total_users: number;
  total_patients: number;
  total_doctors: number;
  total_appointments: number;
}

export interface HospitalStats {
  hospital_id: string;
  total_doctors: number;
  total_patients: number;
  total_appointments: number;
  total_completed_appointments: number;
}

export interface StaffMember {
  id: string;
  email: string;
  full_name: string;
  role: string;
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
  full_name: string | null;
  hospital_id: string;
  specialization: string;
  license_number: string;
  years_experience: number | null;
  consultation_fee: number | null;
  bio: string | null;
  is_accepting_appointments: boolean;
}

export type AppointmentStatus = "awaiting_payment" | "pending" | "confirmed" | "completed" | "cancelled" | "no_show";

export type PaymentStatus = "created" | "paid" | "failed" | "expired" | "refunded" | "refund_failed";

export interface Appointment {
  id: string;
  hospital_id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  status: AppointmentStatus;
  reason: string | null;
  cancellation_reason: string | null;
  hold_expires_at: string | null; // while awaiting payment
  payment: { id: string; status: PaymentStatus; amount_paise: number; currency: string; provider: string } | null;
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

export type SkinImageStatus = "uploaded" | "queued_for_analysis" | "analyzed" | "failed";

export type Condition = "acne" | "eczema" | "fungal";

// --- Scheduling (Phase 11) ---
export interface WorkingHoursBlock {
  weekday: number; // 0 = Monday ... 6 = Sunday
  start_time: string; // "09:00" when sending; the API returns "09:00:00"
  end_time: string;
}

export interface WeeklyHours {
  is_default: boolean; // true = doctor hasn't set hours, defaults apply
  timezone: string;
  slot_minutes: number;
  blocks: WorkingHoursBlock[];
}

export interface DoctorSlots {
  doctor_id: string;
  timezone: string;
  slot_minutes: number;
  days: { date: string; slots: { start: string; label: string }[] }[];
}

export interface RecommendedDoctor {
  doctor: DoctorProfile;
  hospital_name: string;
  score: number; // 0-100
  reasons: string[];
}

export interface Recommendations {
  condition: Condition | null;
  condition_source: "photo" | "selected" | null;
  doctors: RecommendedDoctor[];
}

export interface Prediction {
  predicted_class: string;
  label: string;
  confidence: number; // 0-1
  all_probabilities: Record<string, number>;
  guidance: string;
  disclaimer: string;
  gradcam_url: string;
  model_name: string;
  created_at: string;
}

export interface SkinImage {
  id: string;
  patient_id: string;
  file_url: string;
  content_type: string;
  status: SkinImageStatus;
  analysis_error: string | null;
  prediction: Prediction | null;
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
// Hospitals (public, read-only directory — creation moved to adminApi
// in Phase 6, gated behind SUPER_ADMIN)
// ---------------------------------------------------------------------------

export const hospitalApi = {
  list: () => request<HospitalOut[]>("/hospitals"),
  get: (id: string) => request<HospitalOut>(`/hospitals/${id}`),
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

  /** Retries analysis for an image whose last attempt failed. */
  /** Ranked doctors with reasons. Without a condition, the server uses
   * the patient's latest photo analysis. */
  recommendedDoctors: (token: string, choice: Condition | "auto" | "none") => {
    // "auto" = use latest photo analysis; "none" = rank without any condition
    const query = choice === "auto" ? "" : choice === "none" ? "?use_photo=false" : `?condition=${choice}`;
    return authed<Recommendations>(`/patients/me/recommended-doctors${query}`, token);
  },

  analyzeImage: (token: string, imageId: string) =>
    authed<SkinImage>(`/patients/me/images/${imageId}/analyze`, token, { method: "POST" }),

  updateProfile: (token: string, data: Partial<Omit<PatientProfile, "id" | "user_id">>) =>
    authed<PatientProfile>("/patients/me", token, { method: "PATCH", body: JSON.stringify(data) }),
};

// ---------------------------------------------------------------------------
// Doctors
// ---------------------------------------------------------------------------

export const doctorApi = {
  getMyHours: (token: string) => authed<WeeklyHours>("/doctors/me/availability", token),

  /** Replaces the weekly schedule; an empty list restores default hours. */
  setMyHours: (token: string, blocks: WorkingHoursBlock[]) =>
    authed<WeeklyHours>("/doctors/me/availability", token, { method: "PUT", body: JSON.stringify({ blocks }) }),

  slots: (doctorId: string, days = 14) => request<DoctorSlots>(`/doctors/${doctorId}/slots?days=${days}`),

  createProfile: (token: string, data: { hospital_id: string; specialization?: string; license_number: string; years_experience?: number; consultation_fee?: number; bio?: string }) =>
    authed<DoctorProfile>("/doctors/me", token, { method: "POST", body: JSON.stringify(data) }),

  getMyProfile: (token: string) => authed<DoctorProfile>("/doctors/me", token),

  updateMyProfile: (token: string, data: Partial<Pick<DoctorProfile, "specialization" | "years_experience" | "consultation_fee" | "bio" | "is_accepting_appointments">>) =>
    authed<DoctorProfile>("/doctors/me", token, { method: "PATCH", body: JSON.stringify(data) }),

  myQueue: (token: string) => authed<Appointment[]>("/doctors/me/appointments", token),

  myPatients: (token: string) => authed<PatientProfile[]>("/doctors/me/patients", token),

  myPatient: (token: string, patientId: string) => authed<PatientProfile>(`/doctors/me/patients/${patientId}`, token),

  patientImages: (token: string, patientId: string) =>
    authed<SkinImage[]>(`/doctors/me/patients/${patientId}/images`, token),

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

// ---------------------------------------------------------------------------
// Admin (Phase 6) — split by scope:
//   platform.*  -> SUPER_ADMIN only, cuts across every hospital
//   hospital.*  -> SUPER_ADMIN or HOSPITAL_ADMIN, scoped to the
//                  caller's own hospital (server resolves which one —
//                  never passed by the client, same "operate on my
//                  own data" rule used everywhere else in this app)
// ---------------------------------------------------------------------------

export const adminApi = {
  platform: {
    stats: (token: string) => authed<PlatformStats>("/admin/platform/stats", token),

    listHospitals: (token: string) => authed<HospitalOut[]>("/admin/platform/hospitals", token),

    createHospital: (token: string, data: { name: string; slug: string }) =>
      authed<HospitalOut>("/admin/platform/hospitals", token, { method: "POST", body: JSON.stringify(data) }),

    updateHospital: (token: string, hospitalId: string, data: Partial<{ name: string; subscription_tier: string; is_active: boolean }>) =>
      authed<HospitalOut>(`/admin/platform/hospitals/${hospitalId}`, token, { method: "PATCH", body: JSON.stringify(data) }),

    promoteHospitalAdmin: (token: string, hospitalId: string, email: string) =>
      authed<StaffMember>(`/admin/platform/hospitals/${hospitalId}/admins`, token, {
        method: "POST",
        body: JSON.stringify({ email }),
      }),
  },

  hospital: {
    stats: (token: string) => authed<HospitalStats>("/admin/hospital/stats", token),
    staff: (token: string) => authed<StaffMember[]>("/admin/hospital/staff", token),
  },
};

// ---------------------------------------------------------------------------
// Chatbot (Phase 9)
// ---------------------------------------------------------------------------

/** How an answer was produced: AI-written from our notes, the notes
 * themselves (no AI key / AI unavailable), a fixed safety response,
 * or a redirect for off-topic questions. */
export type ChatMode = "ai" | "knowledge_base" | "emergency" | "out_of_scope";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode: ChatMode | null;
  sources: { title: string; section: string }[];
  created_at: string;
}

export interface ChatConversation {
  id: string;
  title: string;
  updated_at: string;
}

export interface ChatTurn {
  conversation_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}

export const chatApi = {
  send: (token: string, content: string, conversationId?: string) =>
    authed<ChatTurn>("/chat/messages", token, {
      method: "POST",
      body: JSON.stringify({ content, conversation_id: conversationId ?? null }),
    }),
  conversations: (token: string) => authed<ChatConversation[]>("/chat/conversations", token),
  messages: (token: string, conversationId: string) =>
    authed<ChatMessage[]>(`/chat/conversations/${conversationId}/messages`, token),
  remove: (token: string, conversationId: string) =>
    authed<void>(`/chat/conversations/${conversationId}`, token, { method: "DELETE" }),
};

// ---------------------------------------------------------------------------
// Notifications (Phase 12)
// ---------------------------------------------------------------------------

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string | null; // page to open when clicked
  read_at: string | null;
  created_at: string;
}

export const notificationApi = {
  list: (token: string, limit = 15) => authed<AppNotification[]>(`/notifications?limit=${limit}`, token),
  unreadCount: (token: string) => authed<{ unread: number }>("/notifications/unread-count", token),
  markRead: (token: string, id: string) => authed<AppNotification>(`/notifications/${id}/read`, token, { method: "POST" }),
  markAllRead: (token: string) => authed<void>("/notifications/read-all", token, { method: "POST" }),
};

// ---------------------------------------------------------------------------
// Payments (Phase 13)
// ---------------------------------------------------------------------------

export interface Checkout {
  payment_id: string;
  provider: "razorpay" | "simulated";
  key_id: string | null; // Razorpay PUBLIC key; the secret never reaches the browser
  order_id: string;
  amount_paise: number;
  currency: string;
  expires_at: string | null;
  description: string;
}

export interface PaymentRecord {
  id: string;
  appointment_id: string;
  amount_paise: number;
  currency: string;
  status: PaymentStatus;
  provider: string;
  paid_at: string | null;
  refunded_at: string | null;
  note: string | null;
  created_at: string;
  doctor_name: string | null;
  appointment_time: string | null;
}

export const paymentApi = {
  checkout: (token: string, paymentId: string) => authed<Checkout>(`/payments/${paymentId}/checkout`, token),
  verify: (token: string, paymentId: string, body: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) =>
    authed<PaymentRecord>(`/payments/${paymentId}/verify`, token, { method: "POST", body: JSON.stringify(body) }),
  simulate: (token: string, paymentId: string, outcome: "success" | "failure") =>
    authed<PaymentRecord>(`/payments/${paymentId}/simulate`, token, { method: "POST", body: JSON.stringify({ outcome }) }),
  mine: (token: string) => authed<PaymentRecord[]>("/patients/me/payments", token),
};

/** Paise -> "₹500" / "₹499.99". Money travels as integer paise end to end. */
export function formatINR(paise: number): string {
  const rupees = paise / 100;
  return `₹${rupees.toLocaleString("en-IN", { minimumFractionDigits: rupees % 1 ? 2 : 0, maximumFractionDigits: 2 })}`;
}

export function fileUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

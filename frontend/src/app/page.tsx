export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-3xl font-semibold tracking-tight text-clinical-700">
        DermAI Platform
      </h1>
      <p className="max-w-xl text-slate-600">
        AI-assisted dermatology care for hospitals and clinics. This is the
        Phase 1 scaffold — patient, doctor, and admin portals land in later
        phases.
      </p>
      <p className="text-sm text-slate-400">
        Backend health check:{" "}
        <code className="rounded bg-slate-100 px-1.5 py-0.5">
          GET /health
        </code>
      </p>
    </main>
  );
}

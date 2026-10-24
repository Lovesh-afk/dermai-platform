"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { doctorApi, ApiError, WeeklyHours, WorkingHoursBlock } from "@/lib/api";
import { Alert, Button, Card, Select, Spinner } from "@/components/ui";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// Every half hour from 06:00 to 22:00 (blocks must start/end on :00 or :30)
const TIME_OPTIONS = Array.from({ length: 33 }, (_, i) => {
  const minutes = 6 * 60 + i * 30;
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
});

/** One editable row per weekday. The API supports several blocks per day
 * (e.g. a lunch break); this page edits one block per day to keep it simple. */
interface DayRow {
  working: boolean;
  start: string;
  end: string;
  hadSplitHours: boolean; // the saved schedule had 2+ blocks this day
}

function toRows(hours: WeeklyHours): DayRow[] {
  return WEEKDAYS.map((_, weekday) => {
    const blocks = hours.blocks.filter((b) => b.weekday === weekday);
    if (blocks.length === 0) return { working: false, start: "09:00", end: "17:00", hadSplitHours: false };
    return {
      working: true,
      start: blocks[0].start_time.slice(0, 5), // "09:00:00" -> "09:00"
      end: blocks[blocks.length - 1].end_time.slice(0, 5),
      hadSplitHours: blocks.length > 1,
    };
  });
}

export default function DoctorSchedulePage() {
  const { accessToken } = useAuth();
  const [hours, setHours] = useState<WeeklyHours | null>(null);
  const [rows, setRows] = useState<DayRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    doctorApi
      .getMyHours(accessToken)
      .then((h) => {
        setHours(h);
        setRows(toRows(h));
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) return; // handled by api.ts
        setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Couldn't load your hours." });
      });
  }, [accessToken]);

  function updateRow(weekday: number, change: Partial<DayRow>) {
    setRows((prev) => prev.map((r, i) => (i === weekday ? { ...r, ...change } : r)));
    setMessage(null);
  }

  async function save(blocks: WorkingHoursBlock[], successText: string) {
    if (!accessToken) return;
    setSaving(true);
    setMessage(null);
    try {
      const updated = await doctorApi.setMyHours(accessToken, blocks);
      setHours(updated);
      setRows(toRows(updated));
      setMessage({ kind: "success", text: successText });
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Couldn't save your hours." });
    } finally {
      setSaving(false);
    }
  }

  function handleSave() {
    const invalid = rows.findIndex((r) => r.working && r.start >= r.end);
    if (invalid !== -1) {
      setMessage({ kind: "error", text: `${WEEKDAYS[invalid]}: the end time must be after the start time.` });
      return;
    }
    if (!rows.some((r) => r.working)) {
      setMessage({
        kind: "error",
        text: "Choose at least one working day. To pause bookings entirely, turn off \"accepting appointments\" in My profile.",
      });
      return;
    }
    const blocks = rows.flatMap((r, weekday) => (r.working ? [{ weekday, start_time: r.start, end_time: r.end }] : []));
    save(blocks, "Your hours are saved. Patients now see slots based on this schedule.");
  }

  if (!hours) return <Spinner className="h-5 w-5 text-pine-600" />;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">My hours</h1>
        <p className="mt-1 text-ink-soft">
          Patients can book {hours.slot_minutes}-minute slots within these hours. Times are in {hours.timezone}.
        </p>
      </div>

      {hours.is_default && (
        <Alert variant="success">
          You&rsquo;re using the default hours (Monday to Friday, 09:00 to 17:00). Change them below to set your own.
        </Alert>
      )}

      <Card className="max-w-2xl">
        <ul className="flex flex-col divide-y divide-sage-100">
          {rows.map((row, weekday) => (
            <li key={WEEKDAYS[weekday]} className="flex flex-wrap items-center gap-4 py-3">
              <label className="flex w-36 items-center gap-2 text-sm font-medium text-ink">
                <input
                  type="checkbox"
                  checked={row.working}
                  onChange={(e) => updateRow(weekday, { working: e.target.checked })}
                  className="h-4 w-4 accent-pine-600"
                />
                {WEEKDAYS[weekday]}
              </label>

              {row.working ? (
                <div className="flex items-center gap-2">
                  <div className="w-28">
                    <Select aria-label={`${WEEKDAYS[weekday]} start`} value={row.start} onChange={(e) => updateRow(weekday, { start: e.target.value })}>
                      {TIME_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                    </Select>
                  </div>
                  <span className="text-sm text-ink-soft">to</span>
                  <div className="w-28">
                    <Select aria-label={`${WEEKDAYS[weekday]} end`} value={row.end} onChange={(e) => updateRow(weekday, { end: e.target.value })}>
                      {TIME_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                    </Select>
                  </div>
                </div>
              ) : (
                <span className="text-sm text-ink-soft">Day off</span>
              )}

              {row.hadSplitHours && (
                <p className="w-full text-xs text-ochre-700">
                  This day has split hours saved; saving here replaces them with one block.
                </p>
              )}
            </li>
          ))}
        </ul>

        {message && (
          <div className="mt-4">
            <Alert variant={message.kind === "success" ? "success" : undefined}>{message.text}</Alert>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save hours"}</Button>
          {!hours.is_default && (
            <Button variant="secondary" disabled={saving} onClick={() => save([], "Default hours restored.")}>
              Reset to default hours
            </Button>
          )}
        </div>
        <p className="mt-3 text-xs text-ink-soft">
          Changing your hours doesn&rsquo;t cancel existing bookings. Review your queue if any now fall outside them.
        </p>
      </Card>
    </div>
  );
}

import type { ReactNode } from "react";

export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}
    >
      {title && (
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "pass" | "fail" | "neutral" | "improvement";
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    pass: "bg-emerald-100 text-emerald-800",
    fail: "bg-red-100 text-red-800",
    neutral: "bg-slate-100 text-slate-700",
    improvement: "bg-eco-100 text-eco-700",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-slate-500" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-eco-600" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {message}
    </div>
  );
}

export function DisclaimerNote({ text, methodology }: { text: string; methodology?: string }) {
  return (
    <p className="mt-3 text-xs leading-relaxed text-slate-400">
      {methodology && <span className="block italic text-slate-400">{methodology}</span>}
      {text}
    </p>
  );
}

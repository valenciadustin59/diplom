import { useState, type FormEvent } from "react";
import type { AuditCreatePayload } from "../types";

type AuditLaunchFormProps = {
  isSubmitting: boolean;
  layout?: "horizontal" | "vertical";
  submitLabel?: string;
  onSubmit: (payload: AuditCreatePayload) => Promise<boolean>;
};

export function AuditLaunchForm({
  isSubmitting,
  layout = "horizontal",
  submitLabel = "Запустить аудит",
  onSubmit,
}: AuditLaunchFormProps) {
  const [query, setQuery] = useState("");
  const [targetUrl, setTargetUrl] = useState("");

  function normalizeTargetUrl(value: string): string {
    const trimmed = value.trim();
    if (!trimmed) {
      return "";
    }

    if (/^https?:\/\//i.test(trimmed)) {
      return trimmed;
    }

    return `https://${trimmed}`;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedUrl = normalizeTargetUrl(targetUrl);
    setTargetUrl(normalizedUrl);

    const isCreated = await onSubmit({
      query: query.trim(),
      target_url: normalizedUrl,
    });

    if (isCreated) {
      setQuery("");
      setTargetUrl("");
    }
  }

  return (
    <form
      className={layout === "vertical" ? "audit-form audit-form--vertical" : "audit-form"}
      onSubmit={handleSubmit}
    >
      <label className="filter-field">
        <span>Поисковый запрос</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="например: купить козловой кран"
          required
        />
      </label>

      <label className="filter-field">
        <span>URL сайта</span>
        <input
          value={targetUrl}
          onChange={(event) => setTargetUrl(event.target.value)}
          onBlur={() => setTargetUrl(normalizeTargetUrl(targetUrl))}
          placeholder="example.com или https://example.com"
          inputMode="url"
          type="text"
          required
        />
      </label>

      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Запускаем..." : submitLabel}
      </button>
    </form>
  );
}

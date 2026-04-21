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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const isCreated = await onSubmit({
      query,
      target_url: targetUrl,
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
          placeholder="ремонт квартир москва"
          required
        />
      </label>

      <label className="filter-field">
        <span>URL сайта</span>
        <input
          value={targetUrl}
          onChange={(event) => setTargetUrl(event.target.value)}
          placeholder="https://example.com"
          type="url"
          required
        />
      </label>

      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Запускаем..." : submitLabel}
      </button>
    </form>
  );
}

/**
 * API client.
 *
 * Failures are returned, not thrown. Every screen in this product has a designed state for
 * "this source did not answer", because that state is not an exception here — it is a
 * routine and meaningful result. A thrown error would push those cases into a generic
 * boundary and lose the one thing worth showing: what was tried and why it did not work.
 */

import type { Corpus, EvalReport, Finding, GeocodeCandidate, Health, PageDetail } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface Ok<T> {
  ok: true;
  data: T;
}
export interface Err {
  ok: false;
  status: number;
  message: string;
}
export type Result<T> = Ok<T> | Err;

async function request<T>(path: string, init?: RequestInit): Promise<Result<T>> {
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });

    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body?.detail) message = body.detail;
      } catch {
        // A non-JSON error body is itself information, but not worth surfacing raw.
      }
      return { ok: false, status: response.status, message };
    }

    return { ok: true, data: (await response.json()) as T };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      message:
        error instanceof Error
          ? `Could not reach the analysis service: ${error.message}`
          : "Could not reach the analysis service.",
    };
  }
}

export const api = {
  health: () => request<Health>("/api/health"),

  corpus: () => request<Corpus>("/api/corpus"),

  page: (pageNumber: number) => request<PageDetail>(`/api/corpus/page/${pageNumber}`),

  geocode: (q: string) =>
    request<{
      ok: boolean;
      ambiguous?: boolean;
      limitation?: string;
      reason?: string;
      candidates: GeocodeCandidate[];
    }>(`/api/geocode?q=${encodeURIComponent(q)}`),

  analyse: (question: string, location: string, latitude?: number, longitude?: number) =>
    request<Finding>("/api/analyse", {
      method: "POST",
      body: JSON.stringify({ question, location, latitude, longitude }),
    }),

  evaluation: () => request<EvalReport>("/api/eval"),

  sources: () => request<Record<string, unknown>>("/api/sources"),
};

export function pageImageUrl(pageNumber: number): string {
  return `${BASE}/api/corpus/page/${pageNumber}/image`;
}

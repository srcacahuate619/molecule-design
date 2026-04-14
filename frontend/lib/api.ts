import type {
  AlphaFoldEntry,
  EvaluationSubmitResponse,
  HistoryResponse,
  JobStatus,
  SuggestionResponse,
  UserStats,
  ValidationResult,
} from "@/lib/types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const stored = localStorage.getItem("moldesign_auth");
    if (stored) {
      const { token } = JSON.parse(stored);
      if (token) return { Authorization: `Bearer ${token}` };
    }
  } catch {}
  return {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  return (await response.json()) as T;
}

// ── Chemistry ────────────────────────────────────────────────────

export async function validateSmiles(smiles: string): Promise<ValidationResult> {
  return request<ValidationResult>("/chem/validate", {
    method: "POST",
    body: JSON.stringify({ smiles }),
  });
}

// ── Evaluation ───────────────────────────────────────────────────

export async function submitEvaluation(smiles: string, targetPdbId = "7E2Y") {
  return request<EvaluationSubmitResponse>("/evaluation/submit", {
    method: "POST",
    body: JSON.stringify({ smiles, target_pdb_id: targetPdbId }),
  });
}

export async function getJobStatus(taskId: string) {
  return request<JobStatus>(`/evaluation/status/${taskId}`);
}

/**
 * Descarga el archivo SDF con las poses de docking desde MinIO.
 * Retorna texto plano (SDF) o null si no hay archivo.
 */
export async function getPoseFile(moleculeId: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/evaluation/files/poses/${moleculeId}`, {
      headers: getAuthHeaders(),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

/**
 * Descarga el archivo PDB del target biológico.
 * Retorna texto plano (PDB) o null si no está disponible.
 */
export async function getProteinFile(moleculeId: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/evaluation/files/protein/${moleculeId}`, {
      headers: getAuthHeaders(),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

// ── History ──────────────────────────────────────────────────────

export async function getEvaluationHistory(
  page = 1,
  pageSize = 20,
  sortBy = "created_at",
  sortOrder = "desc",
  status?: string,
): Promise<HistoryResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  });
  if (status) params.set("status", status);
  return request<HistoryResponse>(`/history/evaluations?${params}`);
}

export async function getUserStats(): Promise<UserStats> {
  return request<UserStats>("/history/stats");
}

// ── Suggestions ──────────────────────────────────────────────────

export async function getSuggestions(
  smiles: string,
  properties?: Record<string, unknown>,
  scores?: Record<string, unknown>,
): Promise<SuggestionResponse> {
  return request<SuggestionResponse>("/suggestions/generate", {
    method: "POST",
    body: JSON.stringify({ smiles, properties, scores, max_suggestions: 5 }),
  });
}

// ── AlphaFold ────────────────────────────────────────────────────

export async function lookupAlphaFold(uniprotId: string): Promise<AlphaFoldEntry> {
  return request<AlphaFoldEntry>(`/targets/alphafold/lookup/${uniprotId}`);
}

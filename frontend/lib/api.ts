import type {
  AlphaFoldEntry,
  EvaluationSubmitResponse,
  HistoryResponse,
  JobStatus,
  SuggestionResponse,
  UserStats,
  ValidationResult,
  GlobalStats,
} from "./types";

const API_URL = "https://road-adware-kde-forums.trycloudflare.com";

if (typeof window !== "undefined") {
  console.log("🔌 MolDesign API URL (Hardcoded):", API_URL);
}

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

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function attemptRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const stored = localStorage.getItem("moldesign_auth");
      if (!stored) return false;

      const { refreshToken, user } = JSON.parse(stored);
      if (!refreshToken) return false;

      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) throw new Error("Refresh failed");

      const data = await res.json();
      localStorage.setItem(
        "moldesign_auth",
        JSON.stringify({
          token: data.access_token,
          refreshToken: data.refresh_token,
          user: {
            user_id: data.user_id,
            username: data.username,
            email: data.email,
          },
        })
      );
      return true;
    } catch (err) {
      console.error("Token refresh failed:", err);
      localStorage.removeItem("moldesign_auth");
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const fetchUrl = `${API_URL}${path}`;
  const fetchInit = {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers || {}),
    },
    cache: "no-store" as RequestCache,
  };

  let response = await fetch(fetchUrl, fetchInit);

  if (response.status === 401) {
    const refreshed = await attemptRefresh();
    if (refreshed) {
      // Retry with new headers
      response = await fetch(fetchUrl, {
        ...fetchInit,
        headers: {
          ...fetchInit.headers,
          ...getAuthHeaders(),
        },
      });
    } else {
      // Si el refresh falla, borramos el token muerto del storage
      if (typeof window !== "undefined") {
        localStorage.removeItem("moldesign_auth");
        // Solo redirigir si NO estamos en la página de evaluación (donde permitimos anónimos)
        if (!window.location.pathname.startsWith("/evaluation")) {
          window.location.href = "/login?expired=true";
        }
      }
    }
  }

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

export async function submitEvaluation(smiles: string, targetPdbId = "7E2Y", isControl = false) {
  return request<EvaluationSubmitResponse>("/evaluation/submit", {
    method: "POST",
    body: JSON.stringify({ smiles, target_pdb_id: targetPdbId, is_control: isControl }),
  });
}

export async function getLimitStatus() {
  return request<{ is_limited: boolean; count: number; max: number; remaining: number }>("/evaluation/limit-status");
}

export async function getJobStatus(taskId: string) {
  return request<JobStatus>(`/evaluation/status/${taskId}`);
}

export async function getAiReport(moleculeId: string): Promise<string | null> {
  try {
    const data = await request<{ ai_report: string | null }>(
      `/evaluation/ai-report/${moleculeId}`,
      { method: "POST" },
    );
    return data.ai_report ?? null;
  } catch {
    return null;
  }
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

/**
 * Descarga el archivo PDB complejo (proteína + ligando HETATM).
 * Retorna texto plano (PDB) o null si no está disponible.
 */
export async function getComplexFile(moleculeId: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/evaluation/files/complex/${moleculeId}`, {
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

export async function saveMolecule(moleculeId: string): Promise<void> {
  await request(`/history/save/${moleculeId}`, { method: "POST" });
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

// ── Blockchain ────────────────────────────────────────────────────

export async function certifyMolecule(
  moleculeId: string,
  userWallet?: string
): Promise<{ signature: string; message: string }> {
  return request<{ signature: string; message: string }>("/blockchain/certify", {
    method: "POST",
    body: JSON.stringify({
      molecule_id: moleculeId,
      user_wallet: userWallet,
    }),
  });
}

export async function downloadCertificate(moleculeId: string): Promise<void> {
  const headers = await getAuthHeaders();
  const url = `${API_URL}/blockchain/certificate/${moleculeId}`;

  const response = await fetch(url, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    throw new Error("No se pudo descargar el certificado");
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = `Certificado_${moleculeId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

export async function getGlobalStats(): Promise<GlobalStats> {
  return request<GlobalStats>("/stats/global");
}
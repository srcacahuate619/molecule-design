"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { user, login, register, isLoading } = useAuth();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect if already logged in
  if (!isLoading && user) {
    router.replace("/evaluation");
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Email y contraseña son obligatorios.");
      return;
    }

    if (mode === "register") {
      if (!username) {
        setError("El nombre de usuario es obligatorio.");
        return;
      }
      if (password.length < 8) {
        setError("La contraseña debe tener al menos 8 caracteres.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Las contraseñas no coinciden.");
        return;
      }
    }

    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, username, password);
      }
      router.push("/evaluation");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <main className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </main>
    );
  }

  return (
    <main className="flex items-center justify-center py-12">
      <div className="w-full max-w-md space-y-6">
        {/* ── Header ── */}
        <div className="text-center">
          <div className="mb-3 text-4xl">🧬</div>
          <h1 className="text-2xl font-bold text-white">
            {mode === "login" ? "Iniciar sesión" : "Crear cuenta"}
          </h1>
          <p className="mt-1 text-sm text-surface-400">
            {mode === "login"
              ? "Accede a tus moléculas guardadas."
              : "Registra una cuenta para guardar tus evaluaciones."}
          </p>
        </div>

        {/* ── Mode Toggle ── */}
        <div className="flex rounded-xl border border-surface-800 bg-surface-900 p-1">
          <button
            onClick={() => { setMode("login"); setError(null); }}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${
              mode === "login"
                ? "bg-brand-600 text-white"
                : "text-surface-400 hover:text-surface-300"
            }`}
          >
            Iniciar sesión
          </button>
          <button
            onClick={() => { setMode("register"); setError(null); }}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${
              mode === "register"
                ? "bg-brand-600 text-white"
                : "text-surface-400 hover:text-surface-300"
            }`}
          >
            Registrarse
          </button>
        </div>

        {/* ── Form ── */}
        <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-surface-800 bg-surface-900 p-6">
          {/* Email */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-surface-400">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@email.com"
              autoComplete="email"
              className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 text-sm text-gray-200 placeholder-surface-500 transition-colors focus:border-brand-500 focus:outline-none"
            />
          </div>

          {/* Username (register only) */}
          {mode === "register" && (
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-surface-400">
                Nombre de usuario
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="usuario123"
                autoComplete="username"
                className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 text-sm text-gray-200 placeholder-surface-500 transition-colors focus:border-brand-500 focus:outline-none"
              />
            </div>
          )}

          {/* Password */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-surface-400">
              Contraseña
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 text-sm text-gray-200 placeholder-surface-500 transition-colors focus:border-brand-500 focus:outline-none"
            />
          </div>

          {/* Confirm Password (register only) */}
          {mode === "register" && (
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-surface-400">
                Confirmar contraseña
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="new-password"
                className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 text-sm text-gray-200 placeholder-surface-500 transition-colors focus:border-brand-500 focus:outline-none"
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="rounded-xl border border-red-900/50 bg-red-950/30 p-3 text-xs text-red-400">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-brand-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                {mode === "login" ? "Iniciando sesión..." : "Creando cuenta..."}
              </span>
            ) : mode === "login" ? (
              "Iniciar sesión"
            ) : (
              "Crear cuenta"
            )}
          </button>
        </form>

        {/* ── Footer ── */}
        <p className="text-center text-xs text-surface-500">
          MolDesign es una herramienta de investigación computacional.
          <br />
          Los resultados no constituyen evidencia clínica.
        </p>
      </div>
    </main>
  );
}

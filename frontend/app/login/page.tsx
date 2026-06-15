"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "../../lib/auth";

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
          {/* Email o Username */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-surface-400">
              Email o Usuario
            </label>
            <input
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@email.com o usuario"
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

        {/* ── Divisor ── */}
        <div className="relative flex items-center py-2">
          <div className="flex-grow border-t border-surface-700"></div>
          <span className="mx-4 flex-shrink-0 text-xs text-surface-500 uppercase tracking-widest">O continúa con</span>
          <div className="flex-grow border-t border-surface-700"></div>
        </div>

        {/* ── OAuth Buttons ── */}
        <div className="flex flex-col gap-3">
          <button
            type="button"
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-surface-700 bg-surface-800 py-3 text-sm font-medium text-white transition-all hover:bg-surface-700 hover:border-surface-600"
            onClick={() => alert("Simulando redirección a Microsoft Azure AD...")}
          >
            <svg width="20" height="20" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 0H0V10H10V0Z" fill="#F25022"/>
              <path d="M21 0H11V10H21V0Z" fill="#7FBA00"/>
              <path d="M10 11H0V21H10V11Z" fill="#00A4EF"/>
              <path d="M21 11H11V21H21V11Z" fill="#FFB900"/>
            </svg>
            Microsoft (Institucional)
          </button>
          
          <button
            type="button"
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-surface-700 bg-surface-800 py-3 text-sm font-medium text-white transition-all hover:bg-surface-700 hover:border-surface-600"
            onClick={() => alert("Simulando redirección a Google Workspace...")}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25C22.56 11.47 22.49 10.72 22.36 10H12V14.26H17.92C17.66 15.63 16.88 16.8 15.71 17.58V20.34H19.28C21.36 18.42 22.56 15.6 22.56 12.25Z" fill="#4285F4"/>
              <path d="M12 23C14.97 23 17.46 22.02 19.28 20.34L15.71 17.58C14.72 18.24 13.46 18.66 12 18.66C9.17 18.66 6.77 16.75 5.88 14.19H2.18V17.06C4.01 20.69 7.73 23 12 23Z" fill="#34A853"/>
              <path d="M5.88 14.19C5.65 13.52 5.52 12.78 5.52 12C5.52 11.22 5.65 10.48 5.88 9.81V6.94H2.18C1.43 8.44 1 10.16 1 12C1 13.84 1.43 15.56 2.18 17.06L5.88 14.19Z" fill="#FBBC05"/>
              <path d="M12 5.34C13.62 5.34 15.06 5.89 16.2 6.98L19.35 3.83C17.45 2.06 14.97 1 12 1C7.73 1 4.01 3.31 2.18 6.94L5.88 9.81C6.77 7.25 9.17 5.34 12 5.34Z" fill="#EA4335"/>
            </svg>
            Google
          </button>
        </div>

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

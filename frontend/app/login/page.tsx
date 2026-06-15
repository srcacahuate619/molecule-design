"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useAuth } from "../../lib/auth";
import { SessionProvider, signIn, signOut, useSession } from "next-auth/react";

function LoginContent() {
  const router = useRouter();
  const { user, login, register, loginWithOAuth, isLoading } = useAuth();
  const { data: session, status } = useSession();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session?.user && (session as any).id_token && (session as any).provider) {
      setBusy(true);
      loginWithOAuth((session as any).provider, (session as any).id_token)
        .then(() => {
          signOut({ redirect: false });
          router.push("/evaluation");
        })
        .catch((err) => {
          signOut({ redirect: false });
          setError(err.message);
          setBusy(false);
        });
    }
  }, [session, loginWithOAuth, router]);

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
    <main className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
      <div className="w-full max-w-md space-y-6 rounded-2xl border border-surface-700 bg-surface-900/50 p-8 shadow-2xl backdrop-blur-md">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-white">
            {mode === "login" ? "Bienvenido a MolDesign" : "Crear cuenta MolDesign"}
          </h1>
          <p className="text-sm text-surface-400">
            {mode === "login"
              ? "Ingresa tus credenciales para continuar"
              : "Regístrate para acceder al pipeline científico"}
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="flex rounded-xl bg-surface-800 p-1">
          <button
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={`w-1/2 rounded-lg py-2 text-sm font-medium transition-all ${
              mode === "login"
                ? "bg-surface-700 text-white shadow"
                : "text-surface-400 hover:text-white"
            }`}
          >
            Iniciar Sesión
          </button>
          <button
            onClick={() => {
              setMode("register");
              setError(null);
            }}
            className={`w-1/2 rounded-lg py-2 text-sm font-medium transition-all ${
              mode === "register"
                ? "bg-brand-600 text-white shadow"
                : "text-surface-400 hover:text-white"
            }`}
          >
            Registrarse
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-surface-300">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-white placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="tu@email.com"
            />
          </div>

          {mode === "register" && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-surface-300">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-white placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="usuario123"
              />
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium text-surface-300">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-white placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="••••••••"
            />
          </div>

          {mode === "register" && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-surface-300">Confirmar Contraseña</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-white placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="••••••••"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={busy || status === "loading"}
            className="w-full rounded-xl bg-brand-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy || status === "loading" ? (
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

        <div className="relative flex items-center py-2">
          <div className="flex-grow border-t border-surface-700"></div>
          <span className="mx-4 flex-shrink-0 text-xs text-surface-500 uppercase tracking-widest">O continúa con</span>
          <div className="flex-grow border-t border-surface-700"></div>
        </div>

        <div className="flex flex-col gap-3">
          <button
            type="button"
            disabled={busy || status === "loading"}
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-surface-700 bg-surface-800 py-3 text-sm font-medium text-white transition-all hover:bg-surface-700 hover:border-surface-600 disabled:opacity-50"
            onClick={() => signIn("google")}
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

        <p className="text-center text-xs text-surface-500">
          MolDesign es una herramienta de investigación computacional.
          <br />
          Los resultados no constituyen evidencia clínica.
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <SessionProvider>
      <LoginContent />
    </SessionProvider>
  );
}

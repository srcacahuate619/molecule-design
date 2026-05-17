// Centralized configuration for the MolDesign Frontend
const getApiUrl = () => {
  if (typeof window === "undefined") return "http://localhost:8010";
  
  const { hostname, protocol } = window.location;
  
  // Si estamos en Vercel o similar (no localhost, no IP local)
  const isVercel = !hostname.includes("localhost") && !hostname.includes("192.168.");
  
  if (isVercel) {
    return "https://preston-pic-customise-hist.trycloudflare.com";
  }
  
  // Si estamos en la red local (ej: 192.168.100.12 o 192.168.1.64)
  if (hostname.includes("192.168.")) {
    return `http://${hostname}:8010`;
  }
  
  // Default local dev
  return "http://localhost:8010";
};

export const API_URL = getApiUrl();

if (typeof window !== "undefined") {
  console.log(`🚀 MolDesign API:`, API_URL);
}

// Centralized configuration for the MolDesign Frontend
const IS_PRODUCTION = typeof window !== "undefined" && !window.location.hostname.includes("localhost") && !window.location.hostname.includes("192.168.1");

export const API_URL = IS_PRODUCTION
  ? "https://alter-care-fossil-harbor.trycloudflare.com"
  : "http://localhost:8000";

if (typeof window !== "undefined") {
  console.log(`🚀 MolDesign [${IS_PRODUCTION ? "PROD" : "LOCAL"}] API:`, API_URL);
}

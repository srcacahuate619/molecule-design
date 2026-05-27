// Centralized configuration for the MolDesign Frontend
const getApiUrl = () => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  if (typeof window === "undefined") return "http://localhost:8010";
  
  const { hostname } = window.location;
  
  if (hostname.includes("192.168.")) {
    return `http://${hostname}:8010`;
  }
  
  return "http://localhost:8010";
};

export const API_URL = getApiUrl();

if (typeof window !== "undefined") {
  console.log(`🚀 MolDesign API:`, API_URL);
}

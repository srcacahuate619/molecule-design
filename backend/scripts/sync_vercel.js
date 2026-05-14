const { execSync } = require('child_process');

async function sync() {
  console.log("🔍 Buscando URL del túnel...");
  
  // Esperamos a que el túnel genere la URL (Cloudflare tarda unos segundos)
  await new Promise(r => setTimeout(r, 20000));

  try {
    // Intentamos extraer la URL usando grep directamente para ser más eficientes
    let newUrl = "";
    try {
      newUrl = execSync("docker logs moldesign_tunnel 2>&1 | grep -oE 'https://[a-zA-Z0-9-]+\\.trycloudflare\\.com' | head -n 1").toString().trim();
    } catch (e) {
      console.error("⚠️ Falló el intento con grep, reintentando con JS...");
      const logs = execSync('docker logs moldesign_tunnel 2>&1').toString();
      const match = logs.match(/https:\/\/[a-zA-Z0-9-]+\.trycloudflare\.com/);
      if (match) newUrl = match[0].trim();
    }
    
    if (!newUrl) {
      console.error("❌ No se encontró la URL del túnel en los logs después de 20s.");
      process.exit(1);
    }

    console.log(`🚀 Nueva URL detectada: ${newUrl}`);

    const token = process.env.VERCEL_TOKEN;
    if (!token) {
      console.error("❌ VERCEL_TOKEN no configurado en el entorno.");
      process.exit(1);
    }

    // Comandos de Vercel para actualizar y desplegar
    console.log("📤 Actualizando variables en Vercel (Production, Preview, Development)...");
    
    // Lista de entornos a actualizar
    const envs = ["production", "preview", "development"];
    
    for (const env of envs) {
      try {
        console.log(`🧹 Limpiando env ${env}...`);
        execSync(`npx vercel env rm NEXT_PUBLIC_API_URL ${env} -y --token ${token} --project prj_t8DpzibTj4Zcj3pTohIydld7PcQk`, { stdio: 'ignore' });
      } catch (e) {}
    }
    
    console.log(`➕ Agregando nueva URL a todos los entornos...`);
    for (const env of envs) {
      execSync(`echo "${newUrl}" | npx vercel env add NEXT_PUBLIC_API_URL ${env} --token ${token} --project prj_t8DpzibTj4Zcj3pTohIydld7PcQk`, { stdio: 'inherit' });
    }
    
    console.log("⚡ Forzando redeploy en Vercel...");
    execSync(`npx vercel deploy --prod --token ${token} --yes --project prj_t8DpzibTj4Zcj3pTohIydld7PcQk`, { stdio: 'inherit' });
    
    console.log("✅ Sincronización completada con éxito.");
    process.exit(0);
  } catch (error) {
    console.error("❌ Error en la sincronización:", error.message);
    // Esperamos 1 minuto antes de salir para evitar un bucle de reinicio agresivo en Docker
    console.log("⏳ Reintentando en 60 segundos...");
    await new Promise(r => setTimeout(r, 60000));
    process.exit(1);
  }
}

sync();

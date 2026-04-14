# MolDesign setup script for Windows (PowerShell)
# Guarda este archivo como setup_moldesign.ps1 y ejecútalo desde PowerShell en la raíz del proyecto.

Write-Host "MolDesign: Setup automatizado (Windows PowerShell)"

# 1. Chequeo de prerequisitos
function Check-Command {
    param([string]$cmd)
    $exists = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $exists) {
        Write-Error "ERROR: '$cmd' no está instalado o no está en el PATH. Instálalo antes de continuar."
        exit 1
    }
}

Check-Command python
Check-Command pip
Check-Command node
Check-Command npm
Check-Command docker
Check-Command docker-compose

# 2. Levantar servicios base
Write-Host "Levantando servicios con docker-compose..."
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: docker-compose falló. Revisa logs de Docker Desktop."
    exit 1
}

# 3. Backend: crear venv e instalar dependencias
Write-Host "Instalando dependencias backend..."
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Migrar base de datos (si aplica)
if (Test-Path .\migrate.bat) {
    Write-Host "Ejecutando migración inicial de base de datos..."
    .\migrate.bat
} elseif (Test-Path .\migrations) {
    if (Test-Path .\migrations\alembic.ini) {
        alembic upgrade head
    } else {
        Write-Host "No se detectó script de migración automático. Revisa README para pasos manuales."
    }
} else {
    Write-Host "No se detectó carpeta de migraciones."
}

# 5. Lanzar backend (FastAPI)
Write-Host "Lanzando backend (deja esta terminal abierta)..."
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd backend; .venv\Scripts\activate; uvicorn api.main:app --reload --host 0.0.0.0 --port 8000'

cd ..

# 6. Frontend: instalar dependencias
Write-Host "Instalando dependencias frontend..."
cd frontend
npm install

# 7. Lanzar frontend
Write-Host "Lanzando frontend (deja esta terminal abierta)..."
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd frontend; npm run dev'

Write-Host "\nMolDesign listo. Accede a la UI en http://localhost:3000 y a la API en http://localhost:8000/docs"

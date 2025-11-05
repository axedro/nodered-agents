#!/bin/bash
# Script de inicio rápido para Node-RED Multi-Agent Flow Builder

echo "🤖 Node-RED Multi-Agent Flow Builder"
echo "===================================="
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no encontrado. Por favor instala Python 3.11+"
    exit 1
fi

echo "✓ Python encontrado: $(python3 --version)"

# Verificar Ollama
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "⚠️  Ollama no está corriendo en localhost:11434"
    echo "   Por favor inicia Ollama o actualiza OLLAMA_BASE_URL en .env"
    echo ""
    echo "   Para instalar Ollama:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    echo "   ollama serve"
    echo ""
else
    echo "✓ Ollama está corriendo"
fi

# Verificar entorno virtual
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creando entorno virtual..."
    python3 -m venv venv
fi

# Activar entorno virtual
echo "🔄 Activando entorno virtual..."
source venv/bin/activate

# Instalar dependencias
if [ ! -f "venv/.installed" ]; then
    echo "📥 Instalando dependencias..."
    pip install -r requirements.txt
    touch venv/.installed
else
    echo "✓ Dependencias ya instaladas"
fi

# Verificar .env
if [ ! -f ".env" ]; then
    echo "⚙️  Creando archivo .env desde .env.example..."
    cp .env.example .env
    echo "   Por favor revisa y ajusta la configuración en .env"
fi

echo ""
echo "🚀 Iniciando backend en http://localhost:8000"
echo "   Documentación API: http://localhost:8000/docs"
echo ""
echo "   Para abrir el frontend:"
echo "   - Abre frontend/index.html en tu navegador"
echo "   - O ejecuta: cd frontend && python3 -m http.server 8080"
echo ""
echo "   Presiona Ctrl+C para detener"
echo ""

# Iniciar backend
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

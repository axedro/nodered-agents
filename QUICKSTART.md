# 🚀 Guía de Inicio Rápido (5 minutos)

## Opción 1: Script Automático (Linux/Mac)

```bash
./start.sh
```

Luego abre `frontend/index.html` en tu navegador.

## Opción 2: Paso a Paso

### 1. Instalar Ollama (si no lo tienes)
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral
ollama serve
```

### 2. Configurar el proyecto
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
```

### 3. Iniciar backend
```bash
python -m uvicorn backend.main:app --reload
```

### 4. Abrir frontend
- Opción A: Abre `frontend/index.html` directamente en el navegador
- Opción B: Sirve con HTTP server
  ```bash
  cd frontend
  python -m http.server 8080
  # Abre http://localhost:8080
  ```

## 🎯 Primera Conversación

1. En el frontend, escribe:
   ```
   Quiero un flujo que reciba datos de una API REST y los guarde en debug
   ```

2. Responde las preguntas del sistema

3. Copia el JSON generado

4. Importa en Node-RED:
   - Menu → Import → Clipboard
   - Pega el JSON
   - Deploy!

5. Prueba el flujo

6. Regresa al frontend y da feedback (Aprobar/Rechazar)

## ✅ Verificar que funciona

### Test 1: Backend
```bash
curl http://localhost:8000/health
# Debe responder: {"status":"healthy","llm_provider":"ollama"}
```

### Test 2: Inicializar nodos
```bash
curl -X POST http://localhost:8000/api/init-nodes
# Debe responder: {"status":"success","message":"Initialized 9 sample nodes"}
```

### Test 3: Chat básico
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, quiero ayuda para crear un flujo"}'
```

## 🐛 Problemas Comunes

### "Connection refused"
→ Verifica que Ollama esté corriendo: `ollama serve`

### "Model not found"
→ Descarga el modelo: `ollama pull mistral`

### Respuestas muy lentas
→ Usa un modelo más pequeño en `.env`:
```env
OLLAMA_MODEL=mistral  # (más rápido)
# o
OLLAMA_MODEL=llama2   # (alternativa)
```

## 🎉 ¡Listo!

Ahora puedes crear flujos de Node-RED conversando naturalmente.

**Ejemplos de prompts:**
- "Necesito recibir webhooks y enviarlos a Slack"
- "Quiero leer archivos CSV y procesarlos"
- "Crear un flujo que consulte una API cada 5 minutos"

**Documentación completa:** Ver `README.md`

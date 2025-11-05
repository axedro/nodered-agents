# 🤖 Node-RED Multi-Agent Flow Builder

Sistema multi-agente impulsado por IA para generar flujos de Node-RED a través de conversaciones naturales. Utiliza LangGraph para orquestar múltiples agentes especializados, RAG para aprendizaje continuo, y soporte para múltiples proveedores LLM.

## 🌟 Características

- **🤝 Sistema Multi-Agente**: 8 agentes especializados trabajando en conjunto
- **💬 Interfaz Conversacional**: Chat natural para especificar requisitos
- **🧠 Memoria y Contexto**: Mantiene el historial de conversación
- **📚 RAG (Retrieval Augmented Generation)**:
  - Base de datos de nodos instalados
  - Cache de soluciones aprobadas
  - Sistema de feedback para reinforcement learning
- **🔄 Aprendizaje Continuo**: Mejora con cada flujo aprobado
- **🎯 Validación Automática**: Verifica sintaxis y estructura de flujos
- **🌐 Multi-LLM**: Soporte para Ollama (local), OpenAI, Anthropic

## 🏗️ Arquitectura

### Agentes del Sistema

1. **CacheSearcher**: Busca soluciones previas similares (>95% similitud)
2. **Conversator**: Dialoga con el usuario para clarificar requisitos
3. **LocalSearcher**: Busca nodos instalados en la base de datos local
4. **WebSearcher**: Busca paquetes npm para nodos faltantes
5. **Installer**: Instala paquetes necesarios (simulado en MVP)
6. **FunctionCoder**: Genera código JavaScript para nodos function
7. **JsonBuilder**: Ensambla el flujo completo de Node-RED
8. **Validator**: Valida estructura y sintaxis del JSON

### Flujo de Trabajo

```
Usuario → CacheSearcher → (cache miss) → Conversator
                ↓                              ↓
            (cache hit)                 LocalSearcher
                ↓                              ↓
            Validator                    WebSearcher
                ↓                              ↓
            FIN                            Installer
                                              ↓
                                        FunctionCoder
                                              ↓
                                         JsonBuilder
                                              ↓
                                         Validator
                                              ↓
                                            FIN
```

### Stack Tecnológico

- **Backend**: FastAPI + Python 3.11+
- **Orquestación**: LangGraph
- **LLM**: Ollama (local) / OpenAI / Anthropic
- **Vector DB**: ChromaDB
- **Embeddings**: sentence-transformers
- **Frontend**: HTML/CSS/JavaScript (vanilla)

## 📋 Requisitos Previos

### 1. Python 3.11+
```bash
python --version
```

### 2. Ollama (para LLM local)
```bash
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Descargar un modelo (elige uno)
ollama pull mistral        # Recomendado para balance
ollama pull llama2         # Alternativa popular
ollama pull codellama      # Mejor para código
ollama pull deepseek-coder # Excelente para código

# Verificar que Ollama esté corriendo
curl http://localhost:11434/api/tags
```

### 3. Node-RED (opcional, para probar flujos)
```bash
npm install -g node-red
node-red
# Accede a http://localhost:1880
```

## 🚀 Instalación

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd nodered-agents
```

### 2. Crear entorno virtual
```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env

# Editar .env con tus configuraciones
nano .env
```

**Configuración mínima para Ollama local:**
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

### 5. Iniciar el backend
```bash
# Desde la raíz del proyecto
python -m uvicorn backend.main:app --reload

# O usando el módulo directamente
python -m backend.main
```

El backend estará disponible en:
- API: http://localhost:8000
- Documentación: http://localhost:8000/docs
- Salud: http://localhost:8000/health

### 6. Abrir el frontend
Abre `frontend/index.html` en tu navegador, o sirve con un servidor HTTP:

```bash
# Opción 1: Python HTTP Server
cd frontend
python -m http.server 8080
# Abre http://localhost:8080

# Opción 2: Node.js http-server
npx http-server frontend -p 8080
```

## 💡 Uso

### 1. Interfaz Web (Recomendado para MVP)

1. Abre la interfaz web en tu navegador
2. Inicia una conversación describiendo el flujo que necesitas:
   - "Quiero recibir datos de una API REST y enviarlos a Slack"
   - "Necesito procesar webhooks de Stripe y guardarlos en una base de datos"
   - "Crear un flujo que lea archivos CSV y los envíe por email"

3. El sistema te hará preguntas clarificadoras
4. Una vez completo, generará el JSON del flujo
5. Copia el JSON y pégalo en Node-RED (Import > Clipboard)
6. Prueba el flujo en Node-RED
7. Regresa al frontend y da feedback (Aprobar/Rechazar)

### 2. API Directa

#### Iniciar conversación
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito un flujo que lea datos de una API REST cada 5 minutos",
    "user_id": "usuario1"
  }'
```

#### Continuar conversación
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "SESSION_ID_AQUI",
    "message": "La API es de OpenWeatherMap",
    "user_id": "usuario1"
  }'
```

#### Enviar feedback
```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "SESSION_ID_AQUI",
    "flow_json": "...",
    "feedback_type": "approve",
    "score": 5,
    "comments": "Funciona perfectamente"
  }'
```

#### Ver estadísticas
```bash
curl http://localhost:8000/api/stats
```

## 🎯 Ejemplos de Uso

### Ejemplo 1: Integración API → Slack
```
Usuario: "Quiero que cada vez que llegue un webhook de GitHub,
          se envíe una notificación a Slack"

Sistema: "¿Qué tipo de eventos de GitHub quieres monitorear?"

Usuario: "Solo los pull requests nuevos"

Sistema: "¿Cuál es la URL del webhook de Slack?"

Usuario: "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"

Sistema: ✓ Flujo generado exitosamente!
```

### Ejemplo 2: Procesamiento de Datos
```
Usuario: "Necesito leer un archivo CSV, filtrar las filas
          donde la columna 'status' sea 'active', y enviar
          el resultado a una API"

Sistema: [Hace preguntas sobre la estructura del CSV,
         la API de destino, formato de envío, etc.]

Sistema: ✓ Flujo generado exitosamente!
```

## 🗂️ Estructura del Proyecto

```
nodered-agents/
├── backend/
│   ├── agents/              # Agentes individuales
│   │   ├── cache_searcher.py
│   │   ├── conversator.py
│   │   ├── local_searcher.py
│   │   ├── web_searcher.py
│   │   ├── installer.py
│   │   ├── function_coder.py
│   │   ├── json_builder.py
│   │   └── validator.py
│   ├── core/                # Core del sistema
│   │   ├── state.py         # LangGraph state
│   │   ├── graph.py         # Workflow orchestration
│   │   └── llm_manager.py   # LLM abstraction
│   ├── rag/                 # Vector database
│   │   ├── vector_store.py
│   │   └── embeddings.py
│   ├── api/                 # FastAPI routes
│   │   └── routes.py
│   ├── models/              # Pydantic models
│   │   └── schemas.py
│   ├── utils/               # Utilities
│   │   └── nodered_utils.py
│   ├── config.py            # Configuration
│   └── main.py              # FastAPI app
├── data/                    # Datos persistentes
│   ├── chroma_db/          # ChromaDB storage
│   ├── approved_flows/     # Flujos aprobados
│   ├── installed_nodes/    # Catálogo de nodos
│   └── feedback/           # Feedback history
├── frontend/                # Frontend simple
│   ├── index.html
│   └── app.js
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 Configuración Avanzada

### Usar OpenAI en lugar de Ollama
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

### Usar Anthropic Claude
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-opus-20240229
```

### Ajustar umbrales de aprendizaje
```env
MIN_FEEDBACK_SCORE=3      # Mínimo score para "flujo bueno"
SIMILARITY_THRESHOLD=0.95 # Para cache hits (95% similar)
```

## 🐛 Solución de Problemas

### Problema: "Connection refused" al iniciar
**Solución**: Verifica que Ollama esté corriendo
```bash
ollama serve
```

### Problema: "Model not found"
**Solución**: Descarga el modelo especificado
```bash
ollama pull mistral
```

### Problema: "ChromaDB initialization failed"
**Solución**: Borra y reinicia la base de datos
```bash
rm -rf data/chroma_db
# Reinicia el backend
```

### Problema: Respuestas lentas
**Solución**:
- Usa un modelo más pequeño (ej. llama2 en lugar de llama2:70b)
- Aumenta recursos de Ollama
- Considera usar GPU para Ollama

## 📊 Sistema de Feedback y Aprendizaje

El sistema aprende de cada flujo que creas:

1. **Aprobación (score ≥4)**: El flujo se guarda en el RAG de soluciones
2. **Rechazo (score <3)**: Se registra para evitar errores similares
3. **Modificación**: El sistema re-genera considerando tus comentarios
4. **Reuso**: Futuras solicitudes similares reutilizan flujos aprobados

### Ver estadísticas de aprendizaje
```bash
curl http://localhost:8000/api/stats

# Respuesta:
{
  "active_sessions": 2,
  "installed_nodes_count": 15,
  "approved_flows_count": 8,
  "feedback_stats": {
    "total_count": 12,
    "average_score": 4.2,
    "approval_rate": 0.67
  }
}
```

## 🚀 Próximos Pasos (Roadmap)

- [ ] Instalación real de paquetes npm
- [ ] Integración directa con Node-RED API
- [ ] Testing automático de flujos
- [ ] Exportación a Git
- [ ] Interfaz web mejorada con React
- [ ] Soporte para subflows
- [ ] Templates de flujos comunes
- [ ] Fine-tuning del modelo con flujos aprobados

## 🤝 Contribuir

Las contribuciones son bienvenidas! Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature
3. Haz commit de tus cambios
4. Push a tu fork
5. Crea un Pull Request

## 📝 Licencia

MIT License - ver LICENSE file

## 🙏 Agradecimientos

- LangChain & LangGraph por el framework de agentes
- Ollama por LLMs locales
- Node-RED community
- ChromaDB por vector storage

## 📧 Contacto

Para preguntas o soporte, abre un issue en GitHub.

---

**¡Feliz automatización con Node-RED! 🎉**

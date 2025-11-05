"""
Main FastAPI Application
Node-RED Multi-Agent Flow Builder
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import sys

from backend.config import settings
from backend.api.routes import router

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO" if not settings.debug else "DEBUG"
)

# Create FastAPI app
app = FastAPI(
    title="Node-RED Multi-Agent Flow Builder",
    description="AI-powered system to generate Node-RED flows through conversational agents",
    version="1.0.0",
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["Multi-Agent System"])

# Serve frontend (static files)
# app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    logger.info("=" * 60)
    logger.info("Starting Node-RED Multi-Agent Flow Builder")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"API: http://{settings.api_host}:{settings.api_port}")
    logger.info("=" * 60)

    # Initialize LLM
    try:
        from backend.core.llm_manager import LLMManager
        llm = LLMManager()
        logger.info(f"✓ LLM initialized: {llm.get_provider_name()}")
    except Exception as e:
        logger.error(f"✗ Failed to initialize LLM: {e}")
        logger.warning("System will start but may not work properly without LLM")

    # Initialize Vector Store
    try:
        from backend.rag.vector_store import VectorStoreManager
        vector_store = VectorStoreManager()
        logger.info(f"✓ Vector store initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize vector store: {e}")

    logger.info("System ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Node-RED Multi-Agent Flow Builder")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Node-RED Multi-Agent Flow Builder",
        "version": "1.0.0",
        "status": "running",
        "llm_provider": settings.llm_provider,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "llm_provider": settings.llm_provider
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )

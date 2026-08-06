"""FastAPI Backend for the Multi-Agent Orchestrator (MAO) system."""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import config, config_manager

# Import MAO components
from orchestrator import MAOrchestrator
from utils.file_utils import FileUtils
from utils.logger import get_logger, setup_logging

logger = get_logger("api")

# Storage directory for API
STORAGE_DIR = Path("./api_storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global api_orchestrator
    logger.info("MAO API starting up...")
    api_orchestrator = MAOrchestrator()
    try:
        FileUtils.cleanup_temp_dir(STORAGE_DIR / "temp")
    except Exception:
        pass
    logger.info("MAO API ready")
    yield
    logger.info("MAO API shutting down...")
    api_orchestrator.cleanup()
    logger.info("MAO API shutdown complete")

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Agent Orchestrator (MAO)",
    description="A modular, multi-phase agent orchestration system for intelligent image generation with quality verification.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
setup_logging(log_level=config.log_level, console=True)

# Create global orchestrator instance for the API
api_orchestrator = MAOrchestrator()


# ==================== Pydantic Models ====================

class GenerationRequest(BaseModel):
    """Request model for image generation."""
    prompt: str
    references: list[dict] | None = None
    max_iterations: int | None = None
    backend: str | None = None


class ClarificationResponse(BaseModel):
    """Response model for clarification questions."""
    question_id: str
    answer: str


class GenerationResponse(BaseModel):
    """Response model for generation results."""
    success: bool
    task_id: str | None = None
    message: str | None = None
    error: str | None = None
    data: dict | None = None
    
    class Config:
        arbitrary_types_allowed = True


# ==================== API Endpoints ====================

def _copy_image_to_task(result, task_dir: Path):
    """Copy the generated image into the task directory for download."""
    try:
        if result.generation_result and result.generation_result.image_path:
            src = Path(result.generation_result.image_path)
            if src.is_file():
                dst = task_dir / src.name
                import shutil
                shutil.copy2(src, dst)
                # Update path in response to point to task-relative location
                result.generation_result.image_path = str(dst)
    except Exception as e:
        logger.warning(f"Could not copy image to task dir: {e}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/status")
async def get_status():
    """Get orchestrator status."""
    status = api_orchestrator.get_status()
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "orchestrator": status
    }


@app.post("/api/generate")
async def generate_image(request: GenerationRequest):
    """
    Generate an image from a prompt.
    
    This endpoint runs the complete MAO workflow:
    1. Input analysis
    2. Image generation
    3. Quality verification
    4. Optional refinement
    """
    try:
        task_id = str(uuid.uuid4())
        logger.info(f"Generation task started: {task_id}")
        
        # Create task directory
        task_dir = STORAGE_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Save request
        request_file = task_dir / "request.json"
        request_file.write_text(request.json())
        
        # Run orchestrator
        result = await api_orchestrator.run(
            user_input=request.prompt,
            references=request.references,
            max_iterations=request.max_iterations
        )
        
        # Copy generated image to task directory for easy download
        _copy_image_to_task(result, task_dir)
        
        # Prepare response
        response_data = result.to_dict()
        response_data["task_id"] = task_id
        
        # Save result
        result_file = task_dir / "result.json"
        result_file.write_text(json.dumps(response_data, indent=2, default=str))
        
        logger.info(f"Generation task completed: {task_id}")
        
        return JSONResponse(content={
            "success": result.success,
            "task_id": task_id,
            "message": "Generation completed" if result.success else result.error,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
async def analyze_input(request: GenerationRequest):
    """
    Analyze user input without generating.
    
    This endpoint only runs Phase 1 (Input Analyzer) to:
    - Parse the prompt
    - Extract intent, subject, style, constraints
    - Validate context
    - Request clarification if needed
    """
    try:
        task_id = str(uuid.uuid4())
        logger.info(f"Analysis task started: {task_id}")
        
        # Run only Phase 1
        analyzed = await api_orchestrator.phase1.analyze(
            request.prompt,
            request.references
        )
        
        # Check if clarification is needed
        if not analyzed.is_sufficient:
            clarification = api_orchestrator.phase1.generate_clarification(analyzed)
            
            logger.info(f"Analysis task completed (clarification needed): {task_id}")
            
            return JSONResponse(content={
                "success": True,
                "task_id": task_id,
                "needs_clarification": True,
                "analyzed_input": analyzed.to_dict(),
                "clarification": clarification.to_dict()
            })
        
        logger.info(f"Analysis task completed: {task_id}")
        
        return JSONResponse(content={
            "success": True,
            "task_id": task_id,
            "needs_clarification": False,
            "analyzed_input": analyzed.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-single")
async def generate_single_image(request: GenerationRequest):
    """
    Generate a single image without refinement loop.
    
    This runs:
    1. Input analysis
    2. Single generation
    3. Quality check (once)
    """
    try:
        task_id = str(uuid.uuid4())
        logger.info(f"Single generation task started: {task_id}")
        
        # Create task directory
        task_dir = STORAGE_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Run single generation
        result = await api_orchestrator.run_single_generation(
            user_input=request.prompt,
            references=request.references
        )
        
        # Copy generated image to task directory for easy download
        _copy_image_to_task(result, task_dir)
        
        # Prepare response
        response_data = result.to_dict()
        response_data["task_id"] = task_id
        
        # Save result
        result_file = task_dir / "result.json"
        result_file.write_text(json.dumps(response_data, indent=2, default=str))
        
        logger.info(f"Single generation task completed: {task_id}")
        
        return JSONResponse(content={
            "success": result.success,
            "task_id": task_id,
            "message": "Generation completed" if result.success else result.error,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"Single generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clarify-and-generate")
async def clarify_and_generate(
    request: GenerationRequest,
    clarifications: list[ClarificationResponse] | None = None
):
    """
    Generate with clarification responses.
    
    This is a two-step process:
    1. First analyze the input
    2. If clarification is needed, use the provided responses
    """
    try:
        # Convert clarifications to dict
        clarification_dict = {}
        if clarifications:
            for resp in clarifications:
                clarification_dict[resp.question_id] = resp.answer
        
        # Run with clarifications
        result = await api_orchestrator.clarify_and_run(
            user_input=request.prompt,
            references=request.references,
            clarification_responses=clarification_dict
        )
        
        task_id = str(uuid.uuid4())
        
        return JSONResponse(content={
            "success": result.success,
            "task_id": task_id,
            "message": "Generation completed" if result.success else result.error,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Clarify and generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-variants")
async def generate_variants(
    count: int = Query(4, ge=1, le=10),
    request: GenerationRequest = None
):
    """
    Generate multiple variants of the same input.
    """
    if not request:
        raise HTTPException(status_code=400, detail="Request body required")
    
    try:
        task_id = str(uuid.uuid4())
        logger.info(f"Variant generation task started: {task_id}")
        
        # Create task directory
        task_dir = STORAGE_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate variants
        results = await api_orchestrator.generate_multiple_variants(
            user_input=request.prompt,
            count=count,
            references=request.references
        )
        
        # Select best variant
        best = api_orchestrator.select_best_variant(results)
        
        # Save all results
        all_results = [r.to_dict() for r in results]
        result_file = task_dir / "all_results.json"
        result_file.write_text(json.dumps(all_results, indent=2, default=str))
        
        logger.info(f"Variant generation task completed: {task_id}")
        
        return JSONResponse(content={
            "success": True,
            "task_id": task_id,
            "count": count,
            "best_variant": best.to_dict(),
            "all_variants": all_results
        })
        
    except Exception as e:
        logger.error(f"Variant generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-reference")
async def upload_reference(
    file: UploadFile = File(...),
    reference_type: str = Form("image")
):
    """
    Upload a reference file for use in generation.
    """
    try:
        # Validate file type
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
        if Path(file.filename).suffix.lower() not in valid_extensions:
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Save file
        upload_dir = STORAGE_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        save_path = upload_dir / f"{file_id}{file_extension}"
        
        # Save file
        with open(save_path, "wb") as buffer:
            buffer.write(await file.read())
        
        logger.info(f"Reference uploaded: {file_id}")
        
        return JSONResponse(content={
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "file_type": reference_type,
            "file_path": str(save_path),
            "url": f"/api/download-reference/{file_id}"
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download-reference/{file_id}")
async def download_reference(file_id: str):
    """
    Download a reference file.
    """
    upload_dir = STORAGE_DIR / "uploads"
    
    # Find file with this ID
    for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
        file_path = upload_dir / f"{file_id}{ext}"
        if file_path.exists():
            return FileResponse(
                path=file_path,
                filename=file_path.name,
                media_type="image/*"
            )
    
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    """
    Download the result of a generation task.
    """
    task_dir = STORAGE_DIR / task_id
    
    # Try to find the result JSON
    result_file = task_dir / "result.json"
    if result_file.exists():
        return FileResponse(
            path=result_file,
            filename=f"{task_id}_result.json",
            media_type="application/json"
        )
    
    raise HTTPException(status_code=404, detail="Task not found")


@app.get("/api/download-image/{task_id}")
async def download_image(task_id: str):
    """
    Download the generated image from a task.
    """
    task_dir = STORAGE_DIR / task_id
    
    # Try to find any image file in the task directory
    for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
        files = list(task_dir.glob(f"*{ext}"))
        if files:
            return FileResponse(
                path=files[0],
                filename=files[0].name,
                media_type="image/*"
            )
    
    raise HTTPException(status_code=404, detail="Image not found")


# ==================== Serving Static Files ====================

# Serve frontend via catch-all route (must be AFTER all API routes)
_frontend_dir = None
for _dir_name in ["build", "dist"]:
    _candidate = Path(f"./frontend/{_dir_name}")
    if _candidate.exists():
        _frontend_dir = _candidate
        break

if _frontend_dir:
    from starlette.staticfiles import StaticFiles as StarletteStaticFiles
    from starlette.responses import FileResponse as StarletteFileResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    # Mount static assets (css/js/images) under /static/*
    _static_dir = _frontend_dir / "static"
    if _static_dir.exists():
        app.mount("/static", StarletteStaticFiles(directory=_static_dir), name="frontend-static")

    class SPAFallbackMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            # If the route was not found (404) and it's not an API route, serve index.html
            if response.status_code == 404 and not request.url.path.startswith("/api"):
                return StarletteFileResponse(_frontend_dir / "index.html")
            return response

    app.add_middleware(SPAFallbackMiddleware)
    logger.info(f"Frontend SPA served from {_frontend_dir}")


# ==================== Configuration Endpoints ====================

@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    config_dict = {
        "phase1": {
            "context_threshold": config.phase1.context_threshold,
            "required_fields": config.phase1.required_fields,
            "optional_fields": config.phase1.optional_fields
        },
        "phase2": {
            "default_backend": config.phase2.default_backend,
            "max_retries": config.phase2.max_retries,
            "timeout_seconds": config.phase2.timeout_seconds,
            "preferred_backends": config.phase2.preferred_backends
        },
        "phase3": {
            "pass_threshold": config.phase3.pass_threshold,
            "max_iterations": config.phase3.max_iterations,
            "enable_ml_validators": config.phase3.enable_ml_validators,
            "enable_ai_validators": config.phase3.enable_ai_validators
        },
        "output_dir": config.output_dir,
        "log_level": config.log_level,
        "debug": config.debug
    }
    
    return JSONResponse(content=config_dict)


@app.post("/api/config")
async def update_config(config_data: dict):
    """Update configuration (admin only)."""
    # In production, add authentication here
    
    try:
        # Update config
        config_manager.config.phase1.context_threshold = config_data.get(
            "phase1.context_threshold", config.phase1.context_threshold
        )
        
        # Save config
        config_manager.save_config()
        
        return JSONResponse(content={
            "success": True,
            "message": "Configuration updated"
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Utility Endpoints ====================

@app.get("/api/backends")
async def list_backends():
    """List available backends."""
    from agents.phase2.backend_registry import BackendRegistry
    
    # Create a temporary registry to check backends
    registry = BackendRegistry()
    
    backends = []
    for name in registry.list_backends():
        backend = registry.get_backend(name)
        if backend:
            backends.append({
                "name": name,
                "type": backend.backend_type.value,
                "available": backend.is_available(),
                "capabilities": backend.capabilities
            })
    
    return JSONResponse(content={
        "backends": backends,
        "available": [b["name"] for b in backends if b["available"]]
    })


@app.post("/api/health-check")
async def check_backend_health():
    """Check health of all backends."""
    from agents.phase2.backend_registry import BackendRegistry
    
    registry = BackendRegistry()
    health = await registry.check_all_health()
    
    return JSONResponse(content={
        "health": health
    })


# ==================== WebSocket Endpoint (Optional) ====================

# In production, you could add WebSocket endpoints for real-time updates
# This is left as an exercise for the user


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    
    # Run the API server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True,
        workers=1
    )

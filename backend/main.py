from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
import uuid
import os
import shutil
import asyncio
import logging
import time
import json
from pathlib import Path

from config import settings, get_runtime_config, update_runtime_config, ensure_dirs
from document_processor import DocumentProcessor
from rag_service import RAGService
from cim_generator import CIMGenerator
from pdf_generator import PDFGenerator
import database as db
import auth
from db.tenant_context import set_tenant_id
from llm.gateway import GatewayMessage, LLMGateway, LLMGenerateRequest

ensure_dirs()
db.init_db()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("cim.api")


def _log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, default=str))

app = FastAPI(title="CIM Generator API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
sessions: Dict[str, dict] = {}


# ─────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_model: Optional[str] = None
    groq_model: Optional[str] = None
    embedding_model: Optional[str] = None
    vector_backend: Optional[str] = None
    postgres_dsn: Optional[str] = None

class ChatRequest(BaseModel):
    message: str

class SectionUpdate(BaseModel):
    content: str

class GenerateSectionRequest(BaseModel):
    section_name: str
    force_regenerate: bool = False

class GenerateAllRequest(BaseModel):
    sections: Optional[List[str]] = None  # None = all sections

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str


class LLMGatewayMessage(BaseModel):
    role: str
    content: str


class LLMGatewayRequest(BaseModel):
    provider: str = "auto"
    model: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.2
    messages: List[LLMGatewayMessage]


# ─────────────────────────────────────────────
# Auth endpoints  (public — no token needed)
# ─────────────────────────────────────────────

@app.post("/api/auth/register", status_code=201)
def register(body: RegisterRequest):
    result = auth.register_user(body.email, body.name, body.password)
    return result

@app.post("/api/auth/login")
def login(body: LoginRequest):
    return auth.login_user(body.email, body.password)

@app.get("/api/auth/me")
def me(current_user: dict = Depends(auth.get_current_user)):
    return {"id": current_user["id"], "email": current_user["email"], "name": current_user["name"]}


# ─────────────────────────────────────────────
# Config endpoints
# ─────────────────────────────────────────────

@app.get("/api/config")
def get_config(current_user: dict = Depends(auth.get_current_user)):
    cfg = get_runtime_config()
    masked = cfg.copy()
    if masked.get("llm_api_key"):
        masked["llm_api_key"] = "•" * 8 + masked["llm_api_key"][-4:]
    return masked

@app.put("/api/config")
def set_config(body: ConfigUpdate, current_user: dict = Depends(auth.get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = update_runtime_config(updates)
    secret_fields = {"llm_api_key", "openai_api_key", "anthropic_api_key", "groq_api_key"}
    return {
        "status": "ok",
        "config": {k: (v if k not in secret_fields else "***") for k, v in updated.items()},
    }


@app.post("/api/llm/generate")
async def llm_generate(body: LLMGatewayRequest, current_user: dict = Depends(auth.get_current_user)):
    """Dynamic runtime LLM routing endpoint.

    `provider=auto` selects the cheapest configured provider to optimize token cost.
    """
    cfg = get_runtime_config()
    gateway = LLMGateway.from_config(cfg)
    result = await gateway.generate(
        LLMGenerateRequest(
            provider=body.provider,
            model=body.model,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
            messages=[GatewayMessage(role=m.role, content=m.content) for m in body.messages],
        )
    )
    return {
        "provider": body.provider,
        "model": body.model or cfg.get("llm_model"),
        "response": result,
    }


# ─────────────────────────────────────────────
# Session endpoints  (auth-protected + ownership)
# ─────────────────────────────────────────────

@app.post("/api/sessions")
def create_session(current_user: dict = Depends(auth.get_current_user)):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": session_id,
        "owner_id": current_user["id"],
        "status": "created",
        "files": [],
        "sections": {},
        "processing_log": [],
    }
    # Persist ownership so it survives across restarts (if session is rehydrated)
    db.bind_session_to_user(session_id, current_user["id"])
    return {"session_id": session_id}

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    return {
        "id": session["id"],
        "status": session["status"],
        "files": session["files"],
        "sections_ready": list(session["sections"].keys()),
        "processing_log": session.get("processing_log", []),
    }

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    try:
        rag = RAGService(session_id=session_id, tenant_id=current_user["id"])
        rag.delete_collection()
    except Exception:
        pass
    session_upload_dir = os.path.join(settings.upload_dir, session_id)
    if os.path.exists(session_upload_dir):
        shutil.rmtree(session_upload_dir)
    sessions.pop(session_id, None)
    db.delete_session_ownership(session_id)
    return {"status": "deleted"}

@app.get("/api/sessions")
def list_my_sessions(current_user: dict = Depends(auth.get_current_user)):
    """List all sessions belonging to the current user."""
    user_session_ids = db.get_user_sessions(current_user["id"])
    result = []
    for sid in user_session_ids:
        if sid in sessions:
            s = sessions[sid]
            result.append({
                "id": sid,
                "status": s["status"],
                "files_count": len(s.get("files", [])),
                "sections_count": len(s.get("sections", {})),
            })
    return {"sessions": result}


# ─────────────────────────────────────────────
# Document upload & processing  (auth-protected)
# ─────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/documents")
async def upload_documents(
    session_id: str,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    session_upload_dir = os.path.join(settings.upload_dir, session_id)
    os.makedirs(session_upload_dir, exist_ok=True)

    saved = []
    for file in files:
        dest = os.path.join(session_upload_dir, file.filename)
        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)
        saved.append({"name": file.filename, "size": len(content), "path": dest})
        session["files"].append({"name": file.filename, "size": len(content)})

    return {"uploaded": len(saved), "files": saved}

@app.post("/api/sessions/{session_id}/process")
async def process_documents(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    session["status"] = "processing"
    session["processing_log"] = []
    background_tasks.add_task(_run_processing, session_id, session)
    return {"status": "processing_started", "session_id": session_id}

@app.get("/api/sessions/{session_id}/process/status")
def get_process_status(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    return {
        "status": session["status"],
        "log": session.get("processing_log", []),
        "files_processed": len(session.get("processed_files", [])),
    }


# ─────────────────────────────────────────────
# CIM section generation  (auth-protected)
# ─────────────────────────────────────────────

CIM_SECTIONS = [
    "executive_summary",
    "investment_thesis",
    "market_overview",
    "company_overview",
    "products_services",
    "revenue_profile",
    "employee_profile",
    "customer_profile",
    "financials",
    "management_structure",
]

@app.get("/api/sessions/{session_id}/sections")
def get_all_sections(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    return {
        "sections": session.get("sections", {}),
        "available_sections": CIM_SECTIONS,
    }

@app.get("/api/sessions/{session_id}/sections/{section_name}")
def get_section(session_id: str, section_name: str, current_user: dict = Depends(auth.get_current_user)):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    if section_name not in session.get("sections", {}):
        raise HTTPException(404, f"Section '{section_name}' not yet generated")
    return session["sections"][section_name]

@app.put("/api/sessions/{session_id}/sections/{section_name}")
def update_section(
    session_id: str, section_name: str, body: SectionUpdate,
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    if "sections" not in session:
        session["sections"] = {}
    if section_name not in session["sections"]:
        session["sections"][section_name] = {}
    session["sections"][section_name]["content"] = body.content
    session["sections"][section_name]["manually_edited"] = True
    return {"status": "updated"}

@app.post("/api/sessions/{session_id}/sections/{section_name}/generate")
async def generate_section(
    session_id: str, section_name: str, force: bool = False,
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    if session["status"] not in ("ready", "generating", "generated"):
        raise HTTPException(400, "Documents must be processed first. Call /process endpoint.")
    if section_name not in CIM_SECTIONS:
        raise HTTPException(400, f"Unknown section: {section_name}. Valid: {CIM_SECTIONS}")

    cfg = get_runtime_config()
    if not cfg.get("llm_api_key"):
        raise HTTPException(400, "LLM API key not configured. Use PUT /api/config.")

    try:
        rag = RAGService(session_id=session_id, tenant_id=current_user["id"])
        generator = CIMGenerator(rag, cfg)
        result = await generator.generate_section(section_name)
        if "sections" not in session:
            session["sections"] = {}
        session["sections"][section_name] = result
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")

@app.post("/api/sessions/{session_id}/generate-all")
async def generate_all_sections(
    session_id: str, body: GenerateAllRequest, background_tasks: BackgroundTasks,
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    if session["status"] not in ("ready", "generating", "generated"):
        raise HTTPException(400, "Documents must be processed first.")

    cfg = get_runtime_config()
    if not cfg.get("llm_api_key"):
        raise HTTPException(400, "LLM API key not configured.")

    sections_to_gen = body.sections or CIM_SECTIONS
    session["status"] = "generating"
    session["generation_progress"] = {"done": [], "total": sections_to_gen}
    background_tasks.add_task(_run_generation, session_id, session, sections_to_gen, cfg)
    return {"status": "generation_started", "sections": sections_to_gen}

@app.get("/api/sessions/{session_id}/generate-all/status")
def get_generation_status(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    progress = session.get("generation_progress", {})
    return {
        "status": session["status"],
        "done": progress.get("done", []),
        "total": progress.get("total", []),
        "sections_ready": list(session.get("sections", {}).keys()),
    }


# ─────────────────────────────────────────────
# Chat with knowledge base  (auth-protected)
# ─────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/chat")
async def chat(
    session_id: str, body: ChatRequest,
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    if session["status"] not in ("ready", "generating", "generated"):
        raise HTTPException(400, "Documents must be processed before chatting.")

    cfg = get_runtime_config()
    if not cfg.get("llm_api_key"):
        raise HTTPException(400, "LLM API key not configured.")

    try:
        rag = RAGService(session_id=session_id, tenant_id=current_user["id"])
        generator = CIMGenerator(rag, cfg)
        answer = await generator.chat(body.message)
        history = session.setdefault("chat_history", [])
        history.append({"role": "user", "content": body.message})
        history.append({"role": "assistant", "content": answer})
        return {"answer": answer, "history": history[-20:]}
    except Exception as e:
        raise HTTPException(500, f"Chat failed: {str(e)}")

@app.get("/api/sessions/{session_id}/chat/history")
def get_chat_history(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    return {"history": session.get("chat_history", [])}


# ─────────────────────────────────────────────
# PDF generation  (auth-protected)
# ─────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/generate-pdf")
async def generate_pdf(
    session_id: str, background_tasks: BackgroundTasks,
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    if not session.get("sections"):
        raise HTTPException(400, "No sections generated yet.")
    session["pdf_status"] = "generating"
    background_tasks.add_task(_run_pdf_generation, session_id, session)
    return {"status": "pdf_generation_started"}

@app.get("/api/sessions/{session_id}/generate-pdf/status")
def get_pdf_status(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    return {
        "status": session.get("pdf_status", "not_started"),
        "pdf_path": session.get("pdf_path"),
    }

@app.get("/api/sessions/{session_id}/download-pdf")
def download_pdf(
    session_id: str,
    token: Optional[str] = None,          # query-param fallback for <a download> links
    current_user: dict = Depends(auth.get_current_user),
):
    session = _get_session(session_id)
    auth.assert_session_owner(session_id, current_user)
    pdf_path = session.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(404, "PDF not yet generated. Call /generate-pdf first.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"CIM_{session_id[:8]}.pdf"
    )


# ─────────────────────────────────────────────
# Background tasks
# ─────────────────────────────────────────────

async def _run_processing(session_id: str, session: dict):
    try:
        session_upload_dir = os.path.join(settings.upload_dir, session_id)
        files = list(Path(session_upload_dir).iterdir()) if os.path.exists(session_upload_dir) else []

        processor = DocumentProcessor()
        rag = RAGService(session_id=session_id, tenant_id=session["owner_id"])

        processed = []
        for file_path in files:
            try:
                session["processing_log"].append(f"Processing: {file_path.name}")
                docs = processor.process_file(str(file_path))
                if docs:
                    await rag.add_documents_async(docs, source=file_path.name)
                    processed.append(file_path.name)
                    session["processing_log"].append(f"✓ {file_path.name} → {len(docs)} chunks")
            except Exception as e:
                session["processing_log"].append(f"✗ {file_path.name}: {str(e)}")

        session["processed_files"] = processed
        session["status"] = "ready"
        session["processing_log"].append(f"✓ Processing complete. {len(processed)} files indexed.")
    except Exception as e:
        session["status"] = "error"
        session["processing_log"].append(f"Fatal error: {str(e)}")

async def _run_generation(session_id: str, session: dict, sections: list, cfg: dict):
    try:
        rag = RAGService(session_id=session_id, tenant_id=session["owner_id"])
        generator = CIMGenerator(rag, cfg)

        for section_name in sections:
            try:
                session["processing_log"] = session.get("processing_log", [])
                session["processing_log"].append(f"Generating: {section_name}")
                result = await generator.generate_section(section_name)
                if "sections" not in session:
                    session["sections"] = {}
                session["sections"][section_name] = result
                session["generation_progress"]["done"].append(section_name)
            except Exception as e:
                session["generation_progress"]["done"].append(section_name)
                session.setdefault("sections", {})[section_name] = {
                    "content": f"Error generating section: {str(e)}",
                    "charts": [],
                    "error": str(e),
                }

        session["status"] = "generated"
    except Exception as e:
        session["status"] = "error"

async def _run_pdf_generation(session_id: str, session: dict):
    try:
        pdf_gen = PDFGenerator()
        output_path = os.path.join(settings.output_dir, f"CIM_{session_id[:8]}.pdf")
        pdf_gen.generate(session["sections"], output_path, session_id)
        session["pdf_path"] = output_path
        session["pdf_status"] = "ready"
    except Exception as e:
        session["pdf_status"] = "error"
        session["pdf_error"] = str(e)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_session(session_id: str) -> dict:
    if session_id not in sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return sessions[session_id]

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    """Middleware-driven tenant propagation with request-scoped structured logging."""
    set_tenant_id(None)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    authz = request.headers.get("authorization", "")
    token = request.query_params.get("token")
    tenant_id = None

    if authz.lower().startswith("bearer "):
        token = authz.split(" ", 1)[1].strip()

    if token:
        try:
            payload = auth.decode_token(token)
            tenant_id = payload.get("sub")
            set_tenant_id(tenant_id)
        except Exception:
            set_tenant_id(None)

    _log_event(
        "request_start",
        method=request.method,
        path=request.url.path,
        request_id=request_id,
        tenant_id=tenant_id,
    )

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _log_event(
            "request_error",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
            tenant_id=tenant_id,
            latency_ms=elapsed_ms,
        )
        logger.exception("Unhandled exception for request_id=%s", request_id)
        set_tenant_id(None)
        raise

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    _log_event(
        "request_end",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        request_id=request_id,
        tenant_id=tenant_id,
        latency_ms=elapsed_ms,
    )
    set_tenant_id(None)
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

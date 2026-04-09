"""
TiniX Story API Server
FastAPI wrapper cho toàn bộ service Python hiện có
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import logging
import uvicorn
import os
from pathlib import Path
from datetime import datetime

# Import existing services
from services.api_client import get_api_client, reinit_api_client
from core.config import get_config, GenerationConfig, API_PROVIDERS
from core.config_api import ConfigAPIManager
from services.novel_generator import (
    NovelGenerator, NovelProject, Chapter, OutlineParser,
    get_preset_templates, get_generator,
    get_cache_size, list_generation_caches, clear_generation_cache
)
from services.project_manager import ProjectManager
from services.genre_manager import GenreManager
from services.sub_genre_manager import SubGenreManager
from services.style_manager import StyleManager
from utils.exporter import export_to_docx, export_to_txt, export_to_markdown, export_to_html
from locales.i18n import t
from core.database import get_db
from core.state import app_state
from core.task_manager import task_manager, TaskStatus

logger = logging.getLogger(__name__)

app = FastAPI(title="TiniX Story API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Request/Response Models ====================

class ProjectCreateReq(BaseModel):
    title: str
    genre: str
    sub_genres: List[str] = []
    character_setting: str = ""
    world_setting: str = ""
    plot_idea: str = ""

class SuggestionReq(BaseModel):
    type: str  # 'title', 'char', 'world', 'plot'
    genre: str = ""
    sub_genres: List[str] = []
    title: str = ""
    character_setting: str = ""
    world_setting: str = ""
    custom_prompt: str = ""
    num_main_chars: int = 2
    num_sub_chars: int = 3

class OutlineReq(BaseModel):
    title: str
    genre: str
    sub_genres: List[str] = []
    total_chapters: int = 20
    character_setting: str
    world_setting: str
    plot_idea: str
    custom_outline_prompt: str = ""

class ChapterGenReq(BaseModel):
    use_reflection: bool = False

class BulkGenReq(BaseModel):
    project_id: str
    chapter_nums: List[int]
    custom_prompt: str = ""
    use_reflection: bool = False

class SaveChapterReq(BaseModel):
    project_id: str
    chapter_num: int
    content: str

class RewriteReq(BaseModel):
    text: str
    style_template: str = ""
    use_reflection: bool = False

class PolishReq(BaseModel):
    text: str
    polish_type: str = "general"
    custom_requirements: str = ""
    use_reflection: bool = False

class SummaryReq(BaseModel):
    text: str
    max_length: int = 200

class ExportReq(BaseModel):
    project_id: str
    format: str = "txt"  # txt, docx, md, html

class GenParamsReq(BaseModel):
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    chapter_target_words: Optional[int] = None
    writing_style: Optional[str] = None
    writing_tone: Optional[str] = None
    character_development: Optional[str] = None
    plot_complexity: Optional[str] = None

class BackendReq(BaseModel):
    name: str
    type: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout: int = 120
    retry_times: int = 3
    enabled: bool = True

class GenreReq(BaseModel):
    name: str
    description: str = ""

class StyleReq(BaseModel):
    name: str
    description: str = ""

class UpdateOutlineReq(BaseModel):
    project_id: str
    outline_text: str

# ==================== Helpers ====================

def _project_to_dict(project: NovelProject) -> Dict:
    """Serialize NovelProject to JSON-safe dict"""
    return {
        "id": getattr(project, 'id', ''),
        "title": project.title,
        "genre": project.genre,
        "sub_genres": project.sub_genres if isinstance(project.sub_genres, list) else [],
        "character_setting": project.character_setting or "",
        "world_setting": project.world_setting or "",
        "plot_idea": project.plot_idea or "",
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "chapters": [
            {
                "num": ch.num,
                "title": ch.title,
                "desc": ch.desc,
                "content": ch.content or "",
                "word_count": ch.word_count,
                "generated_at": ch.generated_at
            }
            for ch in project.chapters
        ],
        "completed_count": project.get_completed_count(),
        "total_words": project.get_total_words(),
    }

def _get_generator() -> NovelGenerator:
    return app_state.get_generator()

# ==================== Health ====================

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

# ==================== Projects ====================

@app.get("/projects")
async def list_projects():
    return ProjectManager.list_projects()

@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    project, msg = ProjectManager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=msg)
    return _project_to_dict(project)

@app.post("/projects")
async def create_project(req: ProjectCreateReq):
    project, msg = ProjectManager.create_project(
        req.title, req.genre, req.sub_genres,
        req.character_setting, req.world_setting, req.plot_idea
    )
    if not project:
        raise HTTPException(status_code=400, detail=msg)
    ProjectManager.save_project(project)
    return _project_to_dict(project)

@app.put("/projects/{project_id}")
async def update_project(project_id: str, req: ProjectCreateReq):
    project, msg = ProjectManager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=msg)
    project.title = req.title
    project.genre = req.genre
    project.sub_genres = req.sub_genres
    project.character_setting = req.character_setting
    project.world_setting = req.world_setting
    project.plot_idea = req.plot_idea
    ProjectManager.save_project(project)
    return _project_to_dict(project)

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    success, msg = ProjectManager.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"message": msg}

@app.post("/projects/update-outline")
async def update_outline(req: UpdateOutlineReq):
    project, msg = ProjectManager.load_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=msg)
    chapters, parse_msg = OutlineParser.parse(req.outline_text)
    if not chapters:
        raise HTTPException(status_code=400, detail=parse_msg)
    # Preserve existing content for chapters that already have it
    old_content = {ch.num: ch for ch in project.chapters}
    for ch in chapters:
        if ch.num in old_content and old_content[ch.num].content:
            ch.content = old_content[ch.num].content
            ch.word_count = old_content[ch.num].word_count
            ch.generated_at = old_content[ch.num].generated_at
    project.chapters = chapters
    ProjectManager.save_project(project)
    return _project_to_dict(project)

# ==================== AI Suggestions ====================

@app.post("/suggest")
async def suggest(req: SuggestionReq):
    gen = _get_generator()
    if req.type == "title":
        content, msg = gen.suggest_title(req.genre, req.sub_genres, req.custom_prompt)
    else:
        content, msg = gen.suggest_content(
            req.type, req.title, req.genre, req.sub_genres,
            req.character_setting, req.world_setting, req.custom_prompt,
            req.num_main_chars, req.num_sub_chars
        )
    return {"content": content, "message": msg}

@app.post("/generate-outline")
async def generate_outline(req: OutlineReq):
    gen = _get_generator()
    content, msg = gen.generate_outline(
        req.title, req.genre, req.sub_genres, req.total_chapters,
        req.character_setting, req.world_setting, req.plot_idea,
        req.custom_outline_prompt
    )
    return {"content": content, "message": msg}

@app.post("/parse-outline")
async def parse_outline(data: Dict[str, str]):
    text = data.get("text", "")
    chapters, msg = OutlineParser.parse(text)
    return {"chapters": [c.to_dict() for c in chapters], "message": msg}

# ==================== Chapter Generation ====================

@app.post("/generate-chapter")
async def generate_chapter(req: ChapterGenReq):
    project, msg = ProjectManager.load_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=msg)

    chapter = next((c for c in project.chapters if c.num == req.chapter_num), None)
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter {req.chapter_num} not found")

    prev_chapters = [c for c in project.chapters if c.num < req.chapter_num and c.content]
    previous_content = ""
    if prev_chapters:
        sorted_prev = sorted(prev_chapters, key=lambda x: x.num)
        previous_content = sorted_prev[-1].content[-3000:] if sorted_prev[-1].content else ""

    gen = _get_generator()
    content, gen_msg = gen.generate_chapter(
        req.chapter_num, chapter.title, chapter.desc, project.title,
        project.character_setting, project.world_setting, project.plot_idea,
        project.genre, project.sub_genres, previous_content,
        custom_prompt=req.custom_prompt, use_reflection=req.use_reflection
    )

    if content:
        chapter.content = content
        chapter.word_count = len(content)
        chapter.generated_at = datetime.now().isoformat()
        ProjectManager.save_project(project)

    return {"content": content, "message": gen_msg, "word_count": len(content) if content else 0}

@app.post("/generate-chapter-stream")
async def generate_chapter_stream(req: ChapterGenReq):
    project, msg = ProjectManager.load_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=msg)

    chapter = next((c for c in project.chapters if c.num == req.chapter_num), None)
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter {req.chapter_num} not found")

    prev_chapters = [c for c in project.chapters if c.num < req.chapter_num and c.content]
    previous_content = ""
    if prev_chapters:
        sorted_prev = sorted(prev_chapters, key=lambda x: x.num)
        previous_content = sorted_prev[-1].content[-3000:] if sorted_prev[-1].content else ""

    gen = _get_generator()

    async def event_generator():
        full_content = ""
        for success, chunk in gen.generate_chapter_stream(
            req.chapter_num, chapter.title, chapter.desc, project.title,
            project.character_setting, project.world_setting, project.plot_idea,
            project.genre, project.sub_genres, previous_content,
            custom_prompt=req.custom_prompt, use_reflection=req.use_reflection
        ):
            if success:
                full_content += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            else:
                yield f"data: {json.dumps({'error': chunk})}\n\n"

        # Auto-save after streaming completes
        if full_content:
            chapter.content = full_content
            chapter.word_count = len(full_content)
            chapter.generated_at = datetime.now().isoformat()
            ProjectManager.save_project(project)

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/save-chapter")
async def save_chapter(req: SaveChapterReq):
    project, msg = ProjectManager.load_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=msg)

    found = False
    for ch in project.chapters:
        if ch.num == req.chapter_num:
            ch.content = req.content
            ch.word_count = len(req.content)
            ch.generated_at = datetime.now().isoformat()
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Chapter {req.chapter_num} not found")

    ProjectManager.save_project(project)
    return {"message": "Chapter saved", "word_count": len(req.content)}

# ==================== Writing Tools ====================

@app.post("/rewrite")
async def rewrite(req: RewriteReq):
    gen = _get_generator()
    content, msg = gen.rewrite_paragraph(req.text, req.style_template, req.use_reflection)
    return {"content": content, "message": msg}

@app.post("/polish")
async def polish(req: PolishReq):
    gen = _get_generator()
    content, msg = gen.polish_text(req.text, req.polish_type, req.custom_requirements, req.use_reflection)
    return {"content": content, "message": msg}

@app.post("/summary")
async def summary(req: SummaryReq):
    gen = _get_generator()
    content, msg = gen.generate_summary(req.text, req.max_length)
    return {"content": content, "message": msg}

@app.post("/export")
async def export_project(req: ExportReq):
    project, msg = ProjectManager.load_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=msg)

    full_text = f"# {project.title}\n\n"
    for ch in project.chapters:
        if ch.content:
            full_text += f"## Chương {ch.num}: {ch.title}\n\n"
            full_text += ch.content + "\n\n"

    if len(full_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="No content to export")

    export_map = {
        "docx": export_to_docx,
        "txt": export_to_txt,
        "md": export_to_markdown,
        "html": export_to_html,
    }
    exporter = export_map.get(req.format)
    if not exporter:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    filepath, exp_msg = exporter(full_text, project.title)
    if not filepath:
        raise HTTPException(status_code=500, detail=exp_msg)

    return FileResponse(filepath, filename=os.path.basename(filepath), media_type="application/octet-stream")

# ==================== Background Task Coroutines ====================

async def generate_bulk_task(task, req: BulkGenReq):
    project, msg = ProjectManager.load_project(req.project_id)
    if not project:
        task.update(status=TaskStatus.FAILED, message=msg)
        return

    gen = _get_generator()
    total = len(req.chapter_nums)
    
    for i, ch_num in enumerate(req.chapter_nums):
        if task.is_cancelled():
            break
            
        task.update(message=f"Generating chapter {ch_num} ({i+1}/{total})", progress=(i / total) * 100)
        
        chapter = next((c for c in project.chapters if c.num == ch_num), None)
        if not chapter:
            logger.error(f"Chapter {ch_num} not found in project {req.project_id}")
            continue

        # Get context from previous chapters
        prev_chapters = [c for c in project.chapters if c.num < ch_num and c.content]
        previous_content = ""
        if prev_chapters:
            sorted_prev = sorted(prev_chapters, key=lambda x: x.num)
            previous_content = sorted_prev[-1].content[-3000:] if sorted_prev[-1].content else ""

        # Run generation
        # Note: NovelGenerator.generate_chapter is currently sync. 
        # In a real async app we should make it async, but for now we run it in a thread if needed.
        # Since this is already in a background task, it's okay for now.
        content, gen_msg = await asyncio.to_thread(
            gen.generate_chapter,
            ch_num, chapter.title, chapter.desc, project.title,
            project.character_setting, project.world_setting, project.plot_idea,
            project.genre, project.sub_genres, previous_content,
            custom_prompt=req.custom_prompt, use_reflection=req.use_reflection
        )

        if content:
            chapter.content = content
            chapter.word_count = len(content)
            chapter.generated_at = datetime.now().isoformat()
            ProjectManager.save_project(project)
        else:
            logger.error(f"Failed to generate chapter {ch_num}: {gen_msg}")

    if not task.is_cancelled():
        task.update(status=TaskStatus.COMPLETED, progress=100.0, message=f"Successfully generated {total} chapters")

# ==================== Projects/Tasks Endpoints Extensions ====================

@app.post("/tasks/generate-bulk")
async def start_bulk_generation(req: BulkGenReq):
    task = await task_manager.create_task(
        name=f"Bulk Generation for {req.project_id}",
        task_type="generate_bulk",
        metadata={"project_id": req.project_id, "chapters": req.chapter_nums}
    )
    
    # Start the task in background
    asyncio.create_task(task_manager.run_task(task.id, generate_bulk_task, req))
    
    return {"task_id": task.id, "message": "Bulk generation started"}

# ==================== Genres ====================

@app.get("/genres")
async def list_genres():
    return GenreManager.list_genres()

@app.post("/genres")
async def add_genre(req: GenreReq):
    success = GenreManager.add_genre(req.name, req.description)
    if not success:
        raise HTTPException(status_code=400, detail="Genre already exists or error")
    return {"message": "Genre added", "name": req.name}

@app.put("/genres/{name}")
async def update_genre(name: str, req: GenreReq):
    success = GenreManager.update_genre(name, req.name, req.description)
    if not success:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"message": "Genre updated"}

@app.delete("/genres/{name}")
async def delete_genre(name: str):
    success = GenreManager.delete_genre(name)
    if not success:
        raise HTTPException(status_code=400, detail="Delete failed")
    return {"message": "Genre deleted"}

# ==================== Sub-Genres ====================

@app.get("/sub-genres")
async def list_all_sub_genres():
    return SubGenreManager.get_sub_genre_names()

@app.get("/sub-genres/by-genre/{genre}")
async def list_sub_genres_by_genre(genre: str):
    return SubGenreManager.get_sub_genres_by_genre(genre)

@app.post("/sub-genres")
async def add_sub_genre(req: GenreReq):
    success = SubGenreManager.add_sub_genre(req.name, req.description)
    if not success:
        raise HTTPException(status_code=400, detail="Sub-genre already exists or error")
    return {"message": "Sub-genre added", "name": req.name}

@app.put("/sub-genres/{name}")
async def update_sub_genre(name: str, req: GenreReq):
    success = SubGenreManager.update_sub_genre(name, req.name, req.description)
    if not success:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"message": "Sub-genre updated"}

@app.delete("/sub-genres/{name}")
async def delete_sub_genre(name: str):
    success = SubGenreManager.delete_sub_genre(name)
    if not success:
        raise HTTPException(status_code=400, detail="Delete failed")
    return {"message": "Sub-genre deleted"}

# ==================== Styles ====================

@app.get("/styles")
async def list_styles():
    return StyleManager.get_style_names()

@app.get("/styles/all")
async def list_styles_full():
    return StyleManager.load_styles()

@app.post("/styles")
async def add_style(req: StyleReq):
    success = StyleManager.add_style(req.name, req.description)
    if not success:
        raise HTTPException(status_code=400, detail="Style already exists or error")
    return {"message": "Style added", "name": req.name}

@app.put("/styles/{name}")
async def update_style(name: str, req: StyleReq):
    success = StyleManager.update_style(name, req.name, req.description)
    if not success:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"message": "Style updated"}

@app.delete("/styles/{name}")
async def delete_style(name: str):
    success = StyleManager.delete_style(name)
    if not success:
        raise HTTPException(status_code=400, detail="Delete failed")
    return {"message": "Style deleted"}

# ==================== Config / Settings ====================

@app.get("/config/backends")
async def config_list_backends():
    return ConfigAPIManager.list_backends()

@app.post("/config/backends")
async def config_add_backend(req: BackendReq):
    result = ConfigAPIManager.add_backend(
        req.name, req.type, req.base_url, req.api_key,
        req.model, req.timeout, req.retry_times, req.enabled
    )
    if result["success"]:
        reinit_api_client()
        app_state.generator = None
    return result

@app.put("/config/backends/{name}")
async def config_update_backend(name: str, req: BackendReq):
    result = ConfigAPIManager.update_backend(
        name, name=req.name, type=req.type, base_url=req.base_url,
        api_key=req.api_key, model=req.model, timeout=req.timeout
    )
    if result["success"]:
        reinit_api_client()
        app_state.generator = None
    return result

@app.delete("/config/backends/{name}")
async def config_delete_backend(name: str):
    result = ConfigAPIManager.delete_backend(name)
    if result["success"]:
        reinit_api_client()
        app_state.generator = None
    return result

@app.post("/config/backends/{name}/test")
async def config_test_backend(name: str):
    return ConfigAPIManager.test_backend(name)

@app.get("/config/generation")
async def config_get_generation():
    cfg = get_config()
    gen = cfg.generation
    return {
        "temperature": gen.temperature,
        "top_p": gen.top_p,
        "max_tokens": gen.max_tokens,
        "chapter_target_words": gen.chapter_target_words,
        "writing_style": gen.writing_style,
        "writing_tone": gen.writing_tone,
        "character_development": gen.character_development,
        "plot_complexity": gen.plot_complexity,
    }

@app.put("/config/generation")
async def config_update_generation(req: GenParamsReq):
    cfg = get_config()
    params = {k: v for k, v in req.model_dump().items() if v is not None}
    success, msg = cfg.update_generation_config(**params)
    if success:
        app_state.generator = None
    return {"success": success, "message": msg}

@app.get("/config/providers")
async def config_list_providers():
    return API_PROVIDERS

# ==================== Cache ====================

@app.get("/cache/stats")
async def cache_stats():
    try:
        api_client = get_api_client()
        stats = api_client.get_cache_stats()
        gen_caches = list_generation_caches()
        gen_size = get_cache_size()
        return {
            "api_cache": stats,
            "generation_cache_count": len(gen_caches),
            "generation_cache_size_kb": round(gen_size / 1024, 1)
        }
    except Exception as e:
        return {"error": str(e)}

@app.delete("/cache")
async def clear_cache():
    try:
        api_client = get_api_client()
        api_client.clear_cache()
        clear_generation_cache()
        return {"message": "All caches cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Task Management ====================

@app.get("/tasks")
async def list_tasks():
    return task_manager.list_tasks()

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()

@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.cancel()
    return {"message": "Task cancellation requested"}

# ==================== Entry ====================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

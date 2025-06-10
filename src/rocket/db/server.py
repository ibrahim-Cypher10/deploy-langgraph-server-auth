from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from typing import List, Optional


load_dotenv()


# ----------------------------
# DB Session
# ----------------------------


# Lazy initialization of database connection
engine = None
SessionLocal: Optional[sessionmaker] = None

def get_db_session() -> Session:
    """Get database session, initializing connection if necessary."""
    global engine, SessionLocal
    if engine is None or SessionLocal is None:
        db_url = os.getenv("SUPABASE_URI", "")
        if not db_url:
            raise ValueError("SUPABASE_URI environment variable not found. Please set it in your .env file or environment.")
        
        # Add connection pooling and timeout settings
        engine = create_engine(
            url=db_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,  # Recycle connections after 30 minutes
            pool_pre_ping=True  # Verify connections before using them
        )
        
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
    
    if SessionLocal is None:
        raise ValueError("Failed to initialize database session")
        
    return SessionLocal()


# ----------------------------
# Pydantic Models
# ----------------------------


class Video(BaseModel):
    id: str
    title: str
    description: str
    channel_title: str
    published_at: str
    duration: str
    view_count: int
    like_count: int
    comment_count: int
    url: str
    analysis_summary: str = ""


class Comment(BaseModel):
    id: str
    text: str
    like_count: int
    reply_count: int
    video_id: str


# ----------------------------
# Database Tools
# ----------------------------


async def db_create_video_record(video: Video) -> str:
    """
    Create a video record in the database.

    Args:
        id: YouTube video ID
        title: YouTube video title
        url: YouTube video URL
        total_comments: Total number of comments
        analysis_summary: Summary of the analysis

    Returns:
        id: YouTube video ID
    """
    with get_db_session() as session:
        video_dict = video.model_dump()
        result = session.execute(
            text(
                """
                INSERT INTO videos (id, title, description, channel_title, published_at, duration, view_count, like_count, comment_count, url, analysis_summary) VALUES (:id, :title, :description, :channel_title, :published_at, :duration, :view_count, :like_count, :comment_count, :url, :analysis_summary)
                RETURNING id
                """
            ),
            video_dict
        )
        session.commit()
        row = result.fetchone()
        if row:
            return str(row[0])
        return ""
    

async def db_upsert_comments_records(comments: List[Comment]):
    """
    Upsert comment records in the database (insert or update on conflict).

    Args:
        comments: List of comment dictionaries

    Returns:
        None
    """
    if not comments:
        return

    with get_db_session() as session:
        # Convert Pydantic models to dictionaries for bulk upsert
        comment_dicts = [comment.model_dump() for comment in comments]

        # PostgreSQL/Supabase UPSERT using ON CONFLICT
        session.execute(
            text("""
                INSERT INTO comments (id, text, like_count, reply_count, video_id)
                VALUES (:id, :text, :like_count, :reply_count, :video_id)
                ON CONFLICT (id)
                DO UPDATE SET
                    text = EXCLUDED.text,
                    like_count = EXCLUDED.like_count,
                    reply_count = EXCLUDED.reply_count,
                    video_id = EXCLUDED.video_id
            """),
            comment_dicts
        )
        session.commit()

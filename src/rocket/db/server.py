from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from typing import List


load_dotenv()


# ----------------------------
# DB Session
# ----------------------------


engine = create_engine(url=os.getenv("SUPABASE_URI"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
# MCP Server
# ----------------------------


mcp = FastMCP("database")


@mcp.tool()
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
    with SessionLocal() as session:
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
        return str(result.fetchone()[0])
    

@mcp.tool()
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

    with SessionLocal() as session:
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

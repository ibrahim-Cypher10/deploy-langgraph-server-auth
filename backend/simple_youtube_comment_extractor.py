"""
Simple YouTube Top-Level Comment Extractor

This module provides a clean, focused way to extract all top-level comments
from a YouTube video using the official YouTube Data API v3.

Features:
- Extracts only top-level comments (no replies)
- Gets upvote counts and reply counts for each comment
- Handles pagination automatically
- Simple, clean interface

Requirements:
- pip install google-api-python-client
- YouTube Data API v3 enabled in Google Cloud Console
- Valid API key from Google Cloud Console
"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()


class YouTubeCommentExtractor:
    """
    Simple YouTube comment extractor for top-level comments only.
    """
    
    def __init__(self, api_key):
        """
        Initialize the comment extractor.
        
        Args:
            api_key (str): Your YouTube Data API key
        """
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
    
    def extract_comments(self, video_id, max_comments=None, order='time'):
        """
        Extract top-level comments from a YouTube video.

        Args:
            video_id (str): YouTube video ID (e.g., 'dQw4w9WgXcQ')
            max_comments (int, optional): Maximum number of comments to return.
                                        If None, extracts all comments.
            order (str): Order of comments. Options: 'time', 'relevance'

        Returns:
            list: List of comment dictionaries with the following structure:
                {
                    'comment_id': str,
                    'text': str,
                    'author': str,
                    'author_channel_id': str,
                    'like_count': int,
                    'reply_count': int,
                    'published_at': str,
                    'updated_at': str
                }
        """
        comments = []
        next_page_token = None

        limit_text = f" (limit: {max_comments})" if max_comments else " (all comments)"
        print(f"Extracting top-level comments for video: {video_id}{limit_text}")

        try:
            while True:
                # Calculate how many comments to request in this batch
                if max_comments:
                    remaining = max_comments - len(comments)
                    if remaining <= 0:
                        break
                    batch_size = min(100, remaining)  # API max is 100 per request
                else:
                    batch_size = 100

                # Request comment threads (we only want the top-level comments)
                request = self.youtube.commentThreads().list(
                    part='snippet',  # Only get snippet, not replies
                    videoId=video_id,
                    maxResults=batch_size,
                    order=order,
                    pageToken=next_page_token
                )

                response = request.execute()

                # Process each comment thread
                for item in response['items']:
                    # Check if we've reached the limit
                    if max_comments and len(comments) >= max_comments:
                        break

                    # Extract top-level comment data
                    top_comment = item['snippet']['topLevelComment']['snippet']

                    comment_data = {
                        'comment_id': item['snippet']['topLevelComment']['id'],
                        'text': top_comment['textDisplay'],
                        'author': top_comment['authorDisplayName'],
                        'author_channel_id': top_comment.get('authorChannelId', {}).get('value', ''),
                        'like_count': top_comment['likeCount'],
                        'reply_count': item['snippet']['totalReplyCount'],
                        'published_at': top_comment['publishedAt'],
                        'updated_at': top_comment['updatedAt']
                    }

                    comments.append(comment_data)

                print(f"Extracted {len(comments)} comments so far...")

                # Check if we've reached the limit
                if max_comments and len(comments) >= max_comments:
                    break

                # Check if there are more pages
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

                # Be respectful to the API - add a small delay
                time.sleep(0.1)

            # Trim to exact limit if specified
            if max_comments and len(comments) > max_comments:
                comments = comments[:max_comments]

            print(f"Finished! Total top-level comments extracted: {len(comments)}")
            return comments
            
        except HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred: {e.content}")
            
            if e.resp.status == 403:
                error_content = e.content.decode('utf-8')
                if 'commentsDisabled' in error_content:
                    print("Comments are disabled for this video.")
                elif 'quotaExceeded' in error_content:
                    print("API quota exceeded. Try again tomorrow or request a quota increase.")
                else:
                    print("Access forbidden. Check your API key and permissions.")
            elif e.resp.status == 404:
                print("Video not found. Check the video ID.")
            
            return []
    
    def extract_comments_to_json(self, video_id, filename=None, max_comments=None, order='time'):
        """
        Extract comments and save directly to a JSON file.

        Args:
            video_id (str): YouTube video ID
            filename (str, optional): Output filename. Auto-generated if None.
            max_comments (int, optional): Maximum number of comments to extract
            order (str): Order of comments

        Returns:
            str: Path to the created JSON file
        """
        comments = self.extract_comments(video_id, max_comments, order)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            limit_suffix = f"_limit{max_comments}" if max_comments else ""
            filename = f"youtube_comments_{video_id}{limit_suffix}_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(comments, f, indent=2, ensure_ascii=False)

        print(f"Comments saved to {filename}")
        return filename
    
    def get_comment_stats(self, video_id, max_comments=None):
        """
        Get basic statistics about the comments.

        Args:
            video_id (str): YouTube video ID
            max_comments (int, optional): Maximum number of comments to analyze

        Returns:
            dict: Statistics about the comments
        """
        comments = self.extract_comments(video_id, max_comments)
        
        if not comments:
            return {}
        
        total_likes = sum(comment['like_count'] for comment in comments)
        total_replies = sum(comment['reply_count'] for comment in comments)
        
        # Find most liked comment
        most_liked = max(comments, key=lambda x: x['like_count'])
        
        # Find comment with most replies
        most_replied = max(comments, key=lambda x: x['reply_count'])
        
        stats = {
            'total_comments': len(comments),
            'total_likes': total_likes,
            'total_replies': total_replies,
            'average_likes_per_comment': total_likes / len(comments),
            'average_replies_per_comment': total_replies / len(comments),
            'most_liked_comment': {
                'text': most_liked['text'][:100] + '...' if len(most_liked['text']) > 100 else most_liked['text'],
                'author': most_liked['author'],
                'likes': most_liked['like_count']
            },
            'most_replied_comment': {
                'text': most_replied['text'][:100] + '...' if len(most_replied['text']) > 100 else most_replied['text'],
                'author': most_replied['author'],
                'replies': most_replied['reply_count']
            }
        }
        
        return stats


def extract_video_id_from_url(url):
    """
    Extract video ID from various YouTube URL formats.
    
    Args:
        url (str): YouTube URL
    
    Returns:
        str: Video ID or None if not found
    """
    import re
    
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
        r'youtube\.com/watch\?.*v=([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def main():
    """
    Example usage of the comment extractor.
    """
    # Configuration
    API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
    
    # Example video - you can use URL or just video ID
    video_input = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll
    # Or just: video_input = "dQw4w9WgXcQ"
    
    # Extract video ID if URL is provided
    if "youtube.com" in video_input or "youtu.be" in video_input:
        video_id = extract_video_id_from_url(video_input)
        if not video_id:
            print("Could not extract video ID from URL")
            return
    else:
        video_id = video_input
    
    print(f"Video ID: {video_id}")
    
    # Initialize the extractor
    extractor = YouTubeCommentExtractor(API_KEY)
    
    # Extract top-level comments (you can specify a limit)
    comments = extractor.extract_comments(video_id, order='time', max_comments=10)
    
    if comments:
        # Display summary
        print(f"\n=== EXTRACTION SUMMARY ===")
        print(f"Total top-level comments: {len(comments)}")
        
        # Show sample comments
        print(f"\n=== SAMPLE COMMENTS ===")
        for i, comment in enumerate(comments[:3], 1):
            print(f"\n{i}. {comment['author']} ({comment['like_count']} likes, {comment['reply_count']} replies)")
            print(f"   {comment['text'][:100]}...")
            print(f"   Published: {comment['published_at']}")
        
        # Get and display statistics
        print(f"\n=== COMMENT STATISTICS ===")
        stats = extractor.get_comment_stats(video_id)
        print(f"Total likes across all comments: {stats['total_likes']:,}")
        print(f"Total replies across all comments: {stats['total_replies']:,}")
        print(f"Average likes per comment: {stats['average_likes_per_comment']:.1f}")
        print(f"Average replies per comment: {stats['average_replies_per_comment']:.1f}")
        
        print(f"\nMost liked comment ({stats['most_liked_comment']['likes']} likes):")
        print(f"  {stats['most_liked_comment']['author']}: {stats['most_liked_comment']['text']}")
        
        print(f"\nMost replied comment ({stats['most_replied_comment']['replies']} replies):")
        print(f"  {stats['most_replied_comment']['author']}: {stats['most_replied_comment']['text']}")
        
        # Save to JSON file
        json_file = extractor.extract_comments_to_json(video_id)
        print(f"\nComments saved to: {json_file}")
        
    else:
        print("No comments extracted. Check your API key, video ID, and ensure comments are enabled.")


if __name__ == "__main__":
    main()

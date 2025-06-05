"""
YouTube Data API v3 Search Example using Official Google API Python Client

This example demonstrates how to search for videos using the YouTube Data API v3
and the official Google API Python Client library.

Requirements:
- pip install google-api-python-client
- YouTube Data API v3 enabled in Google Cloud Console
- Valid API key from Google Cloud Console

Documentation:
- YouTube Data API: https://developers.google.com/youtube/v3
- Python Client: https://github.com/googleapis/google-api-python-client
"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json


def search_youtube_videos(api_key, query, max_results=10, order='relevance'):
    """
    Search for YouTube videos using the YouTube Data API v3.
    
    Args:
        api_key (str): Your YouTube Data API key from Google Cloud Console
        query (str): Search query/keyword
        max_results (int): Maximum number of results to return (1-50)
        order (str): Order of results. Options: 'relevance', 'date', 'rating', 
                    'viewCount', 'title', 'videoCount'
    
    Returns:
        list: List of dictionaries containing video information
    
    Raises:
        HttpError: If the API request fails
    """
    
    # Build the YouTube service object
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    try:
        # Call the search.list method to retrieve results matching the query
        search_response = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=max_results,
            order=order,
            type='video'  # Only return videos (not channels or playlists)
        ).execute()
        
        videos = []
        
        # Extract relevant information from each video
        for search_result in search_response.get('items', []):
            video_info = {
                'video_id': search_result['id']['videoId'],
                'title': search_result['snippet']['title'],
                'description': search_result['snippet']['description'],
                'channel_title': search_result['snippet']['channelTitle'],
                'channel_id': search_result['snippet']['channelId'],
                'published_at': search_result['snippet']['publishedAt'],
                'thumbnail_url': search_result['snippet']['thumbnails']['default']['url'],
                'video_url': f"https://www.youtube.com/watch?v={search_result['id']['videoId']}"
            }
            videos.append(video_info)
        
        return videos
        
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
        raise


def get_video_statistics(api_key, video_ids):
    """
    Get detailed statistics for a list of video IDs.
    
    Args:
        api_key (str): Your YouTube Data API key
        video_ids (list): List of video IDs
    
    Returns:
        dict: Dictionary mapping video IDs to their statistics
    """
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    try:
        # Convert list to comma-separated string (API accepts up to 50 IDs)
        video_ids_str = ','.join(video_ids[:50])
        
        videos_response = youtube.videos().list(
            part='statistics,contentDetails',
            id=video_ids_str
        ).execute()
        
        stats = {}
        for video in videos_response.get('items', []):
            video_id = video['id']
            stats[video_id] = {
                'view_count': video['statistics'].get('viewCount', 0),
                'like_count': video['statistics'].get('likeCount', 0),
                'comment_count': video['statistics'].get('commentCount', 0),
                'duration': video['contentDetails']['duration']
            }
        
        return stats
        
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
        raise


def search_youtube_with_stats(api_key, query, max_results=10, order='relevance'):
    """
    Search for YouTube videos and include detailed statistics.
    
    Args:
        api_key (str): Your YouTube Data API key
        query (str): Search query/keyword
        max_results (int): Maximum number of results to return (1-50)
        order (str): Order of results
    
    Returns:
        list: List of dictionaries containing video information with statistics
    """
    # First, get the basic search results
    videos = search_youtube_videos(api_key, query, max_results, order)
    
    # Extract video IDs for statistics lookup
    video_ids = [video['video_id'] for video in videos]
    
    # Get detailed statistics
    stats = get_video_statistics(api_key, video_ids)
    
    # Merge statistics with video information
    for video in videos:
        video_id = video['video_id']
        if video_id in stats:
            video.update(stats[video_id])
    
    return videos


# Example usage
if __name__ == "__main__":
    # Replace with your actual API key
    API_KEY = "YOUR_YOUTUBE_DATA_API_KEY_HERE"
    
    # Example search
    try:
        results = search_youtube_videos(
            api_key=API_KEY,
            query="python programming tutorial",
            max_results=5,
            order='viewCount'  # Order by view count
        )
        
        print(f"Found {len(results)} videos:")
        for i, video in enumerate(results, 1):
            print(f"\n{i}. {video['title']}")
            print(f"   Channel: {video['channel_title']}")
            print(f"   URL: {video['video_url']}")
            print(f"   Published: {video['published_at']}")
        
        # Example with statistics
        print("\n" + "="*50)
        print("WITH DETAILED STATISTICS:")
        
        detailed_results = search_youtube_with_stats(
            api_key=API_KEY,
            query="python programming tutorial",
            max_results=3
        )
        
        for i, video in enumerate(detailed_results, 1):
            print(f"\n{i}. {video['title']}")
            print(f"   Views: {video.get('view_count', 'N/A')}")
            print(f"   Likes: {video.get('like_count', 'N/A')}")
            print(f"   Comments: {video.get('comment_count', 'N/A')}")
            print(f"   Duration: {video.get('duration', 'N/A')}")
            
    except HttpError as e:
        print(f"Error occurred: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

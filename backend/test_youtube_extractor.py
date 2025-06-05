"""
Test script for YouTube Comment Extractor

This script tests the basic functionality of the YouTube comment extractor
to make sure everything is set up correctly.
"""

from simple_youtube_comment_extractor import YouTubeCommentExtractor
from dotenv import load_dotenv
import os

load_dotenv()

def test_extractor():
    """
    Test the comment extractor with a popular video.
    """
    # Replace with your actual API key
    API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
    
    # Test video ID (Rick Astley - Never Gonna Give You Up)
    # This video is guaranteed to have comments and be publicly accessible
    TEST_VIDEO_ID = "dQw4w9WgXcQ"
    
    print("Testing YouTube Comment Extractor...")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else "API Key not set")
    print(f"Test Video ID: {TEST_VIDEO_ID}")
    print("-" * 50)
    
    try:
        # Initialize the extractor
        extractor = YouTubeCommentExtractor(API_KEY)
        print("✓ Extractor initialized successfully")
        
        # Test with a small limit first
        print("\nTesting with limit of 5 comments...")
        comments = extractor.extract_comments(TEST_VIDEO_ID, max_comments=5)
        
        if comments:
            print(f"✓ Successfully extracted {len(comments)} comments!")
            
            # Display the first comment as a test
            first_comment = comments[0]
            print(f"\nSample comment:")
            print(f"Author: {first_comment['author']}")
            print(f"Likes: {first_comment['like_count']}")
            print(f"Replies: {first_comment['reply_count']}")
            print(f"Text: {first_comment['text'][:100]}...")
            
            print(f"\n✓ All tests passed! Your setup is working correctly.")
            return True
        else:
            print("✗ No comments extracted. Check your setup.")
            return False
            
    except Exception as e:
        print(f"✗ Error occurred: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure your API key is correct")
        print("2. Ensure YouTube Data API v3 is enabled in Google Cloud Console")
        print("3. Check that your API key has the right permissions")
        print("4. Verify you have internet connectivity")
        return False

def troubleshoot_common_issues():
    """
    Help troubleshoot common setup issues.
    """
    print("\n" + "="*60)
    print("TROUBLESHOOTING GUIDE")
    print("="*60)
    
    print("\n1. API Key Issues:")
    print("   - Make sure you copied the entire API key")
    print("   - Check that the key is not restricted to wrong APIs")
    print("   - Verify the key is enabled and not suspended")
    
    print("\n2. Quota Issues:")
    print("   - Default quota is 10,000 units per day")
    print("   - Each comment request uses 1 unit")
    print("   - Check usage at: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas")
    
    print("\n3. Permission Issues:")
    print("   - Ensure YouTube Data API v3 is enabled")
    print("   - Check that your Google Cloud project is active")
    print("   - Verify billing is set up (if required)")
    
    print("\n4. Video Issues:")
    print("   - Make sure the video exists and is public")
    print("   - Check that comments are enabled on the video")
    print("   - Try with a different video ID")
    
    print("\n5. Network Issues:")
    print("   - Check your internet connection")
    print("   - Verify firewall isn't blocking API calls")
    print("   - Try from a different network if possible")

if __name__ == "__main__":
    success = test_extractor()
    
    if not success:
        troubleshoot_common_issues()
    else:
        print(f"\n🎉 Setup complete! You can now use the comment extractor.")
        print(f"\nNext steps:")
        print(f"1. Replace the test video ID with your target video")
        print(f"2. Adjust max_comments limit as needed")
        print(f"3. Run your extraction!")
        
        print(f"\nExample usage:")
        print(f"```python")
        print(f"extractor = YouTubeCommentExtractor('your-api-key')")
        print(f"comments = extractor.extract_comments('video-id', max_comments=100)")
        print(f"```")

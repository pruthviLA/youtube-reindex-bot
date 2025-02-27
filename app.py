import streamlit as st
import openai
import requests
import json
import re
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from textblob import TextBlob

# -------- Load API Keys from Streamlit Secrets --------
YOUTUBE_API_KEY = st.secrets["api_keys"]["YOUTUBE_API_KEY"]
GOOGLE_NEWS_API_KEY = st.secrets["api_keys"]["GOOGLE_NEWS_API_KEY"]
OPENAI_API_KEY = st.secrets["api_keys"]["OPENAI_API_KEY"]

# Initialize APIs
openai.api_key = OPENAI_API_KEY
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# -------- Function to Extract Video ID from Link --------
def extract_video_id(url):
    match = re.search(r"(?<=v=)[^&#]+", url) or re.search(r"(?<=youtu.be/)[^&#]+", url)
    return match.group(0) if match else None

# -------- Fetch YouTube Video Metadata --------
def get_video_metadata(video_id):
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()

    if "items" not in response or not response["items"]:
        return None

    video_data = response["items"][0]["snippet"]
    return {
        "title": video_data["title"],
        "description": video_data["description"],
        "tags": video_data.get("tags", []),
    }

# -------- Fetch YouTube Video Transcript --------
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_transcript = " ".join([entry["text"] for entry in transcript])
        return full_transcript
    except:
        return "Transcript not available."

# -------- Fetch Google News Articles --------
def fetch_google_news(query):
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={GOOGLE_NEWS_API_KEY}"
    response = requests.get(url).json()

    if "articles" in response:
        return [article["title"] for article in response["articles"][:5]]

    return []

# -------- Check for Similarity Using NLP --------
def check_similarity(video_content, news_titles):
    similarities = []
    for news_title in news_titles:
        similarity_score = TextBlob(video_content).sentiment.polarity - TextBlob(news_title).sentiment.polarity
        if abs(similarity_score) < 0.2:
            similarities.append(news_title)
    return similarities

# -------- OpenAI AI-Powered Suggestions --------
def generate_openai_suggestions(video_title, transcript, trending_topics):
    prompt = f"""
    Given a YouTube video with the title: '{video_title}', and the following transcript snippet: '{transcript[:500]}',
    optimize the video metadata based on these trending news topics: {trending_topics}.

    Suggest:
    1. A new click-worthy title that aligns with trending topics.
    2. A well-crafted description incorporating the trends.
    3. The best tags to improve search visibility.

    Format the response as JSON with keys: "title", "description", "tags".
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a YouTube SEO expert."},
                  {"role": "user", "content": prompt}]
    )

    try:
        result = json.loads(response["choices"][0]["message"]["content"])
        return result
    except:
        return None

# -------- Update YouTube Video Metadata --------
def update_video_metadata(video_id, new_title, new_description, new_tags):
    request = youtube.videos().update(
        part="snippet",
        body={
            "id": video_id,
            "snippet": {
                "title": new_title,
                "description": new_description,
                "tags": new_tags,
            },
        },
    )
    response = request.execute()
    return response

# -------- Streamlit UI --------
st.title("🔄 AI-Powered YouTube Re-indexation Bot")

video_url = st.text_input("Enter YouTube Video URL:")

if video_url:
    video_id = extract_video_id(video_url)

    if video_id:
        st.write("Fetching Video Data...")
        video_metadata = get_video_metadata(video_id)
        video_transcript = get_video_transcript(video_id)

        if video_metadata:
            st.write("### 🎥 Current Video Data")
            st.write(f"**Title:** {video_metadata['title']}")
            st.write(f"**Description:** {video_metadata['description']}")
            st.write(f"**Tags:** {', '.join(video_metadata['tags'])}")

            st.write("### 📝 Transcript (First 500 characters):")
            st.write(video_transcript[:500] + "..." if len(video_transcript) > 500 else video_transcript)

            st.write("Fetching related Google News articles...")
            news_titles = fetch_google_news(video_metadata["title"])

            if news_titles:
                st.write("### 📰 Google News Articles Found:")
                for title in news_titles:
                    st.write(f"- {title}")

                video_content = video_metadata["title"] + " " + video_transcript
                matching_news = check_similarity(video_content, news_titles)

                if matching_news:
                    st.write("### 🔥 Trending Topics Detected:")
                    for match in matching_news:
                        st.write(f"➡️ {match}")

                    st.write("🔮 Generating AI-Suggested Metadata...")
                    ai_suggestions = generate_openai_suggestions(video_metadata["title"], video_transcript, matching_news)

                    if ai_suggestions:
                        new_title = st.text_input("🔹 Suggested New Title:", ai_suggestions["title"])
                        new_description = st.text_area("🔹 Suggested New Description:", ai_suggestions["description"])
                        new_tags = st.text_input("🔹 Suggested New Tags (comma-separated):", ", ".join(ai_suggestions["tags"]))

                        if st.button("Update Video Metadata"):
                            response = update_video_metadata(video_id, new_title, new_description, new_tags.split(","))
                            if response:
                                st.success("✅ Video metadata updated successfully!")
                    else:
                        st.error("⚠️ Failed to generate AI suggestions. Try again.")
                else:
                    st.info("No trending topics detected for re-indexing.")
            else:
                st.warning("No relevant news articles found.")
        else:
            st.error("Invalid YouTube Video ID or API issue.")
    else:
        st.error("❌ Invalid YouTube URL. Please enter a correct YouTube link.")

import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from groq import Groq
import re
import os
import traceback
import requests
import streamlit.components.v1 as components

#Streamlit Config

st.set_page_config(
    page_title="YouTube Video Summarizer",
    layout="centered"
)

st.markdown("<div style='margin-top:30px;'></div>", unsafe_allow_html=True)

st.markdown(
    """
    <h1 style="color:#1f77b4; text-align:center; font-family:Arial, sans-serif; font-weight:bold; text-shadow:1px 1px 2px rgba(0,0,0,0.1); margin-bottom:25px;">
        YouTube Video Summarizer
    </h1>
    """,
    unsafe_allow_html=True
)

#Helper Functions

def extract_video_id(url):
    patterns = [
        r"v=([^&]+)",
        r"youtu\.be/([^?&]+)",
        r"youtube\.com/shorts/([^?&]+)"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return url.strip()

def fetch_video_metadata(video_id):
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        r = requests.get(oembed_url)
        if r.status_code == 200:
            data = r.json()
            return {
                "title": data.get("title"),
                "author": data.get("author_name"),
                "thumbnail": data.get("thumbnail_url")
            }
    except:
        pass
    return None

def convert_to_bullets(text):
    lines = text.split("\n")
    out = []
    for line in lines:
        clean = line.strip()

        if re.match(r"^(\*|-)\s+.+", clean):
            out.append(f"<li>{clean[2:].strip()}</li>")
        elif re.match(r"^\d+[\.\)]\s+.+", clean):
            item = re.sub(r"^\d+[\.\)]\s+", "", clean)
            out.append(f"<li>{item}</li>")
        else:
            if clean:
                out.append(f"<p>{clean}</p>")

    return "<ul>" + "".join(out) + "</ul>"

def copy_button_with_alert(text, color="#1f77b4"):
    esc = text.replace("`", "\\`").replace('"', '\\"').replace("'", "\\'")
    
    style_block = f"""
    <style>
        .copy-btn {{
            background-color: {color};
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
            outline: none;
            text-decoration: none;
            margin-top: 10px;
        }}
        .copy-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0,0,0,0.15);
            filter: brightness(110%);
        }}
        .copy-btn:active {{
            transform: translateY(0);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            filter: brightness(90%);
        }}
        svg {{
            width: 16px;
            height: 16px;
        }}
    </style>
    """

    html_content = f"""
    {style_block}
    <button class="copy-btn" onclick="navigator.clipboard.writeText(`{esc}`); alert('Copied to clipboard!');">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
        Copy Content
    </button>
    """
    components.html(html_content, height=60)

def extract_section(title, text):
    pattern = rf"### {title}\n(.+?)(?=###|$)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else "Not found."

#Input Area

url = st.text_input("Paste YouTube URL (or raw video ID)", placeholder="https://youtu.be/abc123 or abc123")
summarize_clicked = st.button("Summarize Video")

if "summary_data" not in st.session_state:
    st.session_state.summary_data = None


#Fetch transcript + Generate summary

if summarize_clicked:
    if not url:
        st.error("Please enter a YouTube URL or video ID.")
        st.stop()

    video_id = extract_video_id(url)
    ytt_api = YouTubeTranscriptApi()

    try:
        with st.spinner("Fetching transcript..."):
            transcript_list = ytt_api.list(video_id)
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(['en', 'en-US'])
            except: pass
            if transcript is None:
                try:
                    transcript = transcript_list.find_transcript(['en', 'en-US'])
                except: pass
            if transcript is None:
                try:
                    transcript = transcript_list.find_generated_transcript(['en', 'en-US'])
                except: pass
            if transcript is None:
                try:
                    transcript = next(iter(transcript_list), None)
                except: pass
            if transcript is None:
                raise TranscriptsDisabled("No usable transcripts found.")

            data = transcript.fetch()
            full_text = " ".join([seg.text for seg in data])

    except TranscriptsDisabled:
        st.error("This video has no transcripts.")
        st.stop()
    except Exception:
        st.error("Failed to retrieve transcript.")
        st.code(traceback.format_exc())
        st.stop()

    st.success("Transcript fetched successfully!")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = f"""
    Summarize the following YouTube transcript.

    Provide:

    ### Short Summary
    3–5 sentences.

    ### Key Bullet Points
    Bullet point list.

    ### Actionable Insights
    Practical insights.

    Transcript:
    {full_text}
    """

    with st.spinner("Generating summary..."):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            summary_raw = response.choices[0].message.content
        except Exception as e:
            st.error("Failed to generate summary.")
            st.write(str(e))
            st.stop()

    metadata = fetch_video_metadata(video_id)

    st.session_state.summary_data = {
        "full_text": full_text,
        "summary_raw": summary_raw,
        "metadata": metadata,
        "video_id": video_id,
        "short_summary": extract_section("Short Summary", summary_raw),
        "bullet_points": extract_section("Key Bullet Points", summary_raw),
        "insights": extract_section("Actionable Insights", summary_raw)
    }

#Display UI Elements

if st.session_state.summary_data:
    data = st.session_state.summary_data
    
    if data['metadata']:
        st.markdown(
            f"""
            <div style="text-align:center; margin-top:20px;">
                <img src="{data['metadata']['thumbnail']}" width="60%" style="border-radius:12px; margin-bottom:15px;" />
                <h3 style="color:#1f77b4; margin-bottom:5px;">{data['metadata']['title']}</h3>
                <p style="color:gray; font-size:16px;">Channel: {data['metadata']['author']}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📝 Short Summary", "📌 Key Bullet Points", "💡 Actionable Insights", "🗒️ Full Transcript", "⬇️ Download"]
    )

    with tab1:
        st.markdown(
            f"<div style='background-color:#e3f2fd; padding:1rem; border-radius:10px; color:#0d47a1;'>{data['short_summary']}</div>",
            unsafe_allow_html=True
        )
        copy_button_with_alert(data['short_summary'], "#1f77b4")

    with tab2:
        bp_html = convert_to_bullets(data['bullet_points'])
        st.markdown(
            f"<div style='background-color:#fff3cd; padding:1rem; border-radius:10px; color:#7a4f01;'>{bp_html}</div>",
            unsafe_allow_html=True
        )
        copy_button_with_alert(data['bullet_points'], "#7a4f01")

    with tab3:
        ins_html = convert_to_bullets(data['insights'])
        st.markdown(
            f"<div style='background-color:#d1ecf1; padding:1rem; border-radius:10px; color:#004b4f;'>{ins_html}</div>",
            unsafe_allow_html=True
        )
        copy_button_with_alert(data['insights'], "#004b4f")

    with tab4:
        st.markdown(
            f"<div style='background:#f8f9fa; padding:1rem; border-radius:10px; color:#333; max-height:350px; overflow-y:auto;'>{data['full_text']}</div>",
            unsafe_allow_html=True
        )
        copy_button_with_alert(data['full_text'], "#333")

    
    with tab5:
        st.download_button(
            "Download Summary as .txt",
            data=data['summary_raw'],
            file_name=f"{data['video_id']}_summary.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.divider()
    if st.button("🔄 Reset"):
        st.session_state.summary_data = None
        st.rerun()

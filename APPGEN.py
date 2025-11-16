import streamlit as st
from moviepy.editor import TextClip, CompositeVideoClip
from gtts import gTTS
import os

st.title("🎬 Free Prompt-to-Video Generator")

# User enters a prompt
prompt = st.text_area("Enter your prompt (this will be turned into a video):")

duration = st.slider("Video duration (seconds)", 5, 60, 15)

if st.button("Generate Video"):
    # Step 1: Generate narration
    tts = gTTS(prompt)
    tts.save("voice.mp3")

    # Step 2: Create text clip
    clip = TextClip(prompt, fontsize=50, color='white', size=(720,1280), method='caption')
    clip = clip.set_duration(duration).set_position('center')

    # Step 3: Combine text + narration
    final = CompositeVideoClip([clip]).set_audio("voice.mp3")
    final.write_videofile("output.mp4", fps=24)

    # Step 4: Download button
    with open("output.mp4", "rb") as f:
        st.download_button("⬇️ Download Video", f, file_name="output.mp4")

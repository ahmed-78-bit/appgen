import streamlit as st
from moviepy.editor import ImageClip, CompositeVideoClip, AudioFileClip
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS

st.title("🎬 Free Prompt-to-Video Generator")

# User enters a prompt
prompt = st.text_area("Enter your prompt (this will be turned into a video):")

duration = st.slider("Video duration (seconds)", 5, 60, 15)

if st.button("Generate Video"):
    # Step 1: Generate narration with gTTS
    tts = gTTS(prompt)
    tts.save("voice.mp3")
    narration = AudioFileClip("voice.mp3")

    # Step 2: Create an image with text using PIL
    img = Image.new("RGB", (720, 1280), color=(0, 0, 0))  # black background
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    text_w, text_h = draw.textsize(prompt, font=font)
    draw.text(((720 - text_w) / 2, (1280 - text_h) / 2), prompt, font=font, fill=(255, 255, 255))
    img.save("frame.png")

    # Step 3: Turn image into video
    clip = ImageClip("frame.png").set_duration(duration)

    # Step 4: Combine with narration
    final = CompositeVideoClip([clip]).set_audio(narration)
    final.write_videofile("output.mp4", fps=24)

    # Step 5: Download button
    with open("output.mp4", "rb") as f:
        st.download_button("⬇️ Download Video", f, file_name="output.mp4")

import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoClip, AudioFileClip
import io
import random

st.set_page_config(page_title="AI‑style Prompt Video", page_icon="🎬")
st.title("🎬 Free AI‑style Prompt‑to‑Video Generator (No APIs)")

# ---------- Controls ----------
prompt = st.text_area("Enter your prompt (text will be animated):", height=120)
duration = st.slider("Video duration (seconds)", 5, 60, 12)
fps = st.slider("Frames per second", 12, 30, 24)
style = st.selectbox(
    "Caption animation style",
    ["Typewriter", "Scrolling", "Fade in/out", "Bounce"]
)
bg_style = st.selectbox(
    "Background style",
    ["Gradient waves", "Soft noise", "Radial glow", "Color stripes"]
)
text_size = st.slider("Text size", 32, 80, 56)
text_color = st.color_picker("Text color", "#FFFFFF")
bg_music = st.file_uploader("Optional: upload background music (mp3)", type=["mp3"])

# Canvas size (vertical 9:16 for TikTok/Shorts)
W, H = 720, 1280

# ---------- Fonts ----------
# Use a basic font to avoid system dependencies. You can replace with a TTF in your repo.
font = ImageFont.load_default()

def paint_background(t, style_name):
    """
    Generate a dynamic background frame as a numpy array (H, W, 3) uint8
    """
    if style_name == "Gradient waves":
        # animated horizontal gradient + sine warp
        y = np.linspace(0, 1, H).reshape(-1, 1)
        x = np.linspace(0, 1, W).reshape(1, -1)
        base = np.stack([
            0.5 + 0.5*np.sin(2*np.pi*(x*1.0 + t*0.15)),
            0.5 + 0.5*np.sin(2*np.pi*(y*1.2 - t*0.10)),
            0.5 + 0.5*np.sin(2*np.pi*((x+y)*0.8 + t*0.08))
        ], axis=2)
        img = (base * 255).astype(np.uint8)
        return img

    elif style_name == "Soft noise":
        # Perlin-ish moving noise via random seeds with temporal blending
        rng = np.random.default_rng(seed=int(t*50) % 999999)
        noise = rng.random((H, W, 3))
        # Temporal smoothing
        alpha = 0.7
        rng2 = np.random.default_rng(seed=int((t-0.033)*50) % 999999)
        noise_prev = rng2.random((H, W, 3))
        img = ((alpha*noise + (1-alpha)*noise_prev)*255).astype(np.uint8)
        return img

    elif style_name == "Radial glow":
        cx, cy = W/2, H/2
        xv, yv = np.meshgrid(np.arange(W), np.arange(H))
        r = np.sqrt((xv-cx)**2 + (yv-cy)**2)
        pulse = 0.5 + 0.5*np.sin(2*np.pi*(r/250 - t*0.3))
        base = np.stack([
            0.2 + 0.6*pulse,
            0.1 + 0.5*(1-pulse),
            0.3 + 0.5*np.sin(2*np.pi*(t*0.2))
        ], axis=2)
        img = np.clip(base*255, 0, 255).astype(np.uint8)
        return img

    elif style_name == "Color stripes":
        xv = np.tile(np.arange(W)[None, :, None], (H, 1, 1))
        bands = (np.sin(2*np.pi*(xv/120 + t*0.25)) + 1)/2
        r = bands
        g = np.roll(bands, shift=80, axis=1)
        b = np.roll(bands, shift=160, axis=1)
        img = np.clip(np.stack([r, g, b], axis=2)*255, 0, 255).astype(np.uint8)
        return img

    # Fallback solid
    return np.zeros((H, W, 3), dtype=np.uint8)

def draw_text_center(img_pil, text, font, fill):
    draw = ImageDraw.Draw(img_pil)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pos = ((W - tw) // 2, (H - th) // 2)
    draw.text(pos, text, font=font, fill=fill)

def make_text_for_time(t, style_name, full_text):
    if style_name == "Typewriter":
        # Reveal characters over time
        speed = max(6, len(full_text)/duration)  # chars/sec heuristic
        n = int(min(len(full_text), t * speed))
        return full_text[:n] if n > 0 else ""

    elif style_name == "Scrolling":
        # Scroll text upward
        lines = full_text.split("\n")
        # Build chunk by time
        visible = int(min(len(lines), 1 + t // 1.5))
        return "\n".join(lines[:visible])

    elif style_name == "Fade in/out":
        # Full text; alpha will be handled in composite
        return full_text

    elif style_name == "Bounce":
        # Keep text, but position will change later
        return full_text

    return full_text

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

text_rgb = hex_to_rgb(text_color)

def make_frame(t):
    # Background
    bg = paint_background(t, bg_style)
    img_pil = Image.fromarray(bg)

    # Prepare font: upscale default by drawing at larger size using multiline
    # If you add a TTF (e.g., "assets/Inter-Bold.ttf"), load with ImageFont.truetype
    # font = ImageFont.truetype("assets/Inter-Bold.ttf", text_size)
    # For default font, emulate size by scaling text with line breaks and limited width
    # Here we keep load_default and trust readability; better with a bundled TTF.

    # Animated text content
    text_now = make_text_for_time(t, style, prompt)

    # Alpha and position effects for certain styles
    draw = ImageDraw.Draw(img_pil)

    if style == "Fade in/out":
        # Compute alpha
        fade = 1.0
        in_dur, out_dur = 2.0, 2.0
        if t < in_dur:
            fade = t / in_dur
        elif t > duration - out_dur:
            fade = max(0.0, (duration - t) / out_dur)

        # Draw onto separate layer to apply alpha
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        bbox = layer_draw.textbbox((0, 0), text_now, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((W - tw) // 2, (H - th) // 2)
        layer_draw.text(pos, text_now, font=font, fill=(*text_rgb, int(255 * fade)))
        img_pil = Image.alpha_composite(img_pil.convert("RGBA"), layer).convert("RGB")

    elif style == "Bounce":
        # Vertical bouncing position
        amplitude = H * 0.15
        y_offset = int(np.sin(2*np.pi*(t / 2.0)) * amplitude)
        bbox = draw.textbbox((0, 0), text_now, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((W - tw) // 2, (H - th) // 2 + y_offset)
        draw.text(pos, text_now, font=font, fill=text_rgb)

    elif style == "Scrolling":
        # Draw multiline scrolling upward
        lines = text_now.split("\n")
        line_h = text_size if hasattr(font, "size") else 28
        total_h = line_h * max(1, len(lines))
        start_y = (H - total_h) // 2
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (W - tw) // 2
            y = start_y + i * line_h
            draw.text((x, y), line, font=font, fill=text_rgb)

    else:
        # Typewriter or default: centered single/multiline
        draw_text_center(img_pil, text_now, font, text_rgb)

    return np.array(img_pil)

def build_video():
    clip = VideoClip(make_frame, duration=duration)
    clip = clip.set_fps(fps)

    # Optional music
    if bg_music:
        with open("bg.mp3", "wb") as f:
            f.write(bg_music.read())
        audio = AudioFileClip("bg.mp3").volumex(0.35)
        clip = clip.set_audio(audio)

    clip.write_videofile("output.mp4", fps=fps)
    return "output.mp4"

generate = st.button("Generate video")
if generate:
    if not prompt.strip():
        st.error("Please enter a prompt.")
    else:
        path = build_video()
        with open(path, "rb") as f:
            st.download_button("⬇️ Download Video", f, file_name="output.mp4")
        st.success("Video generated successfully!")

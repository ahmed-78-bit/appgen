import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoClip, AudioFileClip
import io

st.set_page_config(page_title="AI‑style Prompt Video", page_icon="🎬")
st.title("🎬 Free AI‑style Prompt‑to‑Video Generator (No APIs)")

# ---------- Controls ----------
prompt = st.text_area("Enter your prompt (text will be animated):", height=120)
duration = st.slider("Video duration (seconds)", 5, 60, 12)
fps = st.slider("Frames per second", 12, 30, 24)
style = st.selectbox("Caption animation style", ["Typewriter", "Scrolling", "Fade in/out", "Bounce"])
bg_style = st.selectbox("Background style", ["Gradient waves", "Soft noise", "Radial glow", "Color stripes"])
text_size = st.slider("Text size", 32, 96, 56)
text_color = st.color_picker("Text color", "#FFFFFF")
bg_music = st.file_uploader("Optional: upload background music (mp3)", type=["mp3"])

# Canvas size (vertical 9:16 for TikTok/Shorts)
W, H = 720, 1280

# ---------- Fonts ----------
# If you add a TTF (e.g., assets/Inter-Bold.ttf) to your repo, load it with truetype for crisp text:
# font = ImageFont.truetype("assets/Inter-Bold.ttf", text_size)
# Fallback: default bitmap font (less pretty but dependency-free)
try:
    font = ImageFont.truetype("DejaVuSans.ttf", text_size)  # works on many Linux environments
except Exception:
    font = ImageFont.load_default()

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

TEXT_RGB = hex_to_rgb(text_color)

# ---------- Background generators (return HxWx3 uint8) ----------
def bg_gradient_waves(t):
    xv, yv = np.meshgrid(np.linspace(0, 1, W), np.linspace(0, 1, H))
    r = 0.5 + 0.5 * np.sin(2 * np.pi * (xv * 1.0 + t * 0.15))
    g = 0.5 + 0.5 * np.sin(2 * np.pi * (yv * 1.2 - t * 0.10))
    b = 0.5 + 0.5 * np.sin(2 * np.pi * ((xv + yv) * 0.8 + t * 0.08))
    img = np.stack([r, g, b], axis=2)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)

def bg_soft_noise(t):
    # Temporal blended noise for soft movement; ensure deterministic shape
    rng = np.random.default_rng(seed=(int(t * 33) % 10_000_000))
    noise = rng.random((H, W, 3))
    rng_prev = np.random.default_rng(seed=(int((t - 1 / fps) * 33) % 10_000_000))
    noise_prev = rng_prev.random((H, W, 3))
    alpha = 0.7
    img = alpha * noise + (1 - alpha) * noise_prev
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)

def bg_radial_glow(t):
    xv, yv = np.meshgrid(np.arange(W), np.arange(H))
    cx, cy = W / 2, H / 2
    r = np.sqrt((xv - cx) ** 2 + (yv - cy) ** 2)
    pulse = 0.5 + 0.5 * np.sin(2 * np.pi * (r / 250 - t * 0.3))
    rch = 0.2 + 0.6 * pulse
    gch = 0.1 + 0.5 * (1 - pulse)
    bch = 0.3 + 0.5 * np.sin(2 * np.pi * (t * 0.2))
    img = np.stack([rch, gch, np.clip(bch, 0, 1) * np.ones_like(rch)], axis=2)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)

def bg_color_stripes(t):
    xv = np.tile(np.arange(W)[None, :, None], (H, 1, 1)).astype(np.float32)
    bands = (np.sin(2 * np.pi * (xv / 120 + t * 0.25)) + 1) / 2
    r = bands[..., 0]
    g = np.roll(r, shift=80, axis=1)
    b = np.roll(r, shift=160, axis=1)
    img = np.stack([r, g, b], axis=2)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)

def paint_background(t, style_name):
    if style_name == "Gradient waves":
        return bg_gradient_waves(t)
    elif style_name == "Soft noise":
        return bg_soft_noise(t)
    elif style_name == "Radial glow":
        return bg_radial_glow(t)
    elif style_name == "Color stripes":
        return bg_color_stripes(t)
    return np.zeros((H, W, 3), dtype=np.uint8)

# ---------- Text helpers ----------
def measure_text(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def draw_centered_text(draw, text, font, fill):
    tw, th = measure_text(draw, text, font)
    pos = ((W - tw) // 2, (H - th) // 2)
    draw.text(pos, text, font=font, fill=fill)

def make_text_for_time(t, style_name, full_text):
    if style_name == "Typewriter":
        # Characters per second heuristic; ensure at least 6 cps
        cps = max(6, len(full_text) / max(3, duration / 2))
        n = int(min(len(full_text), t * cps))
        return full_text[:n] if n > 0 else ""
    elif style_name == "Scrolling":
        # Split into lines; reveal lines over time
        lines = full_text.split("\n")
        visible = int(min(len(lines), 1 + t // 1.5))
        return "\n".join(lines[:visible])
    # For Fade/Bounce, full text is used with visual effects
    return full_text

# ---------- Frame builder ----------
def make_frame(t):
    bg = paint_background(t, bg_style)
    img_pil = Image.fromarray(bg)

    text_now = make_text_for_time(t, style, prompt)
    draw = ImageDraw.Draw(img_pil)

    if style == "Fade in/out":
        in_dur, out_dur = 2.0, 2.0
        if t < in_dur:
            fade = t / in_dur
        elif t > duration - out_dur:
            fade = max(0.0, (duration - t) / out_dur)
        else:
            fade = 1.0

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        tw, th = measure_text(layer_draw, text_now, font)
        pos = ((W - tw) // 2, (H - th) // 2)
        layer_draw.text(pos, text_now, font=font, fill=(*TEXT_RGB, int(255 * fade)))
        img_pil = Image.alpha_composite(img_pil.convert("RGBA"), layer).convert("RGB")

    elif style == "Bounce":
        amplitude = int(H * 0.15)
        y_offset = int(np.sin(2 * np.pi * (t / 2.0)) * amplitude)
        tw, th = measure_text(draw, text_now, font)
        pos = ((W - tw) // 2, (H - th) // 2 + y_offset)
        draw.text(pos, text_now, font=font, fill=TEXT_RGB)

    elif style == "Scrolling":
        # Draw multiline centered block, moving slowly upward
        lines = text_now.split("\n")
        line_spacing = int(text_size * 1.2) if hasattr(font, "size") else 28
        total_h = line_spacing * max(1, len(lines))
        base_y = (H - total_h) // 2
        scroll = int(-t * line_spacing * 0.3)  # subtle upward motion
        for i, line in enumerate(lines):
            tw, th = measure_text(draw, line, font)
            x = (W - tw) // 2
            y = base_y + i * line_spacing + scroll
            draw.text((x, y), line, font=font, fill=TEXT_RGB)

    else:
        # Typewriter or default: simple centered draw
        draw_centered_text(draw, text_now, font, TEXT_RGB)

    return np.array(img_pil)

# ---------- Video build ----------
def build_video():
    clip = VideoClip(make_frame, duration=duration).set_fps(fps)

    if bg_music:
        with open("bg.mp3", "wb") as f:
            f.write(bg_music.read())
        try:
            audio = AudioFileClip("bg.mp3").volumex(0.35)
            clip = clip.set_audio(audio)
        except Exception:
            st.warning("Failed to load background music. Generating silent video.")

    clip.write_videofile("output.mp4", fps=fps)
    return "output.mp4"

# ---------- UI trigger ----------
if st.button("Generate video"):
    if not prompt.strip():
        st.error("Please enter a prompt.")
    else:
        path = build_video()
        with open(path, "rb") as f:
            st.download_button("⬇️ Download Video", f, file_name="output.mp4")
        st.success("Video generated successfully!")

import math
from PIL import Image, ImageDraw, ImagePath

def create_app_icon(output_ico_path="assets/app_icon.ico", output_png_path="assets/app_icon.png"):
    # Generate at 1024x1024 for ultra-crisp supersampling
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    radius = size // 2 - 24

    # 1. Background Circle with Radial / Multi-layer Gradient
    # Outer Gold Ring
    gold_color = (255, 204, 0, 255) # #FFCC00
    draw.ellipse([center - radius, center - radius, center + radius, center + radius], fill=gold_color)

    # Inner Marine Navy / Cyan Badge
    inner_radius = radius - 18
    # Draw layered gradient
    steps = 40
    for i in range(steps):
        r = inner_radius - int(i * (inner_radius / steps))
        # Gradient from deep navy (15, 35, 75) to bright ocean blue (28, 115, 185)
        factor = i / steps
        cr = int(18 + factor * 25)
        cg = int(45 + factor * 85)
        cb = int(95 + factor * 110)
        draw.ellipse([center - r, center - r, center + r, center + r], fill=(cr, cg, cb, 255))

    # 2. Ocean Waves (layered curves)
    wave_overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    w_draw = ImageDraw.Draw(wave_overlay)

    # Back Wave (dark cyan)
    back_wave = [
        (100, 780), (220, 740), (360, 770), (520, 730), (680, 760), (840, 720), (924, 760),
        (924, 950), (100, 950)
    ]
    w_draw.polygon(back_wave, fill=(15, 82, 140, 220))

    # Mid Wave (vibrant teal blue)
    mid_wave = [
        (100, 810), (260, 770), (440, 820), (620, 770), (800, 810), (924, 780),
        (924, 950), (100, 950)
    ]
    w_draw.polygon(mid_wave, fill=(0, 168, 204, 230))

    # Front Crest Wave (foam & bright water)
    front_wave = [
        (120, 850), (280, 810), (460, 850), (640, 820), (820, 850), (900, 840),
        (900, 950), (120, 950)
    ]
    w_draw.polygon(front_wave, fill=(225, 245, 254, 240))

    # Mask wave to circle
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius], fill=255)
    img.paste(wave_overlay, (0, 0), mask)

    # 3. Draw Stylized Modern Fishing Boat (Tàu đánh bắt)
    # Hull
    hull_pts = [
        (220, 680),  # bow top
        (280, 760),  # bow bottom
        (540, 760),  # stern bottom
        (560, 690),  # stern top
        (510, 680),  # deck level
        (230, 680)
    ]
    draw.polygon(hull_pts, fill=(245, 247, 250, 255)) # White-steel hull
    # Red waterline stripe
    stripe_pts = [
        (255, 730), (280, 760), (540, 760), (550, 735)
    ]
    draw.polygon(stripe_pts, fill=(229, 57, 53, 255)) # Maritime Red

    # Cabin / Wheelhouse
    cabin_pts = [
        (330, 560), (460, 560), (475, 680), (320, 680)
    ]
    draw.polygon(cabin_pts, fill=(255, 255, 255, 255))
    # Windows
    draw.rectangle([345, 580, 385, 615], fill=(30, 136, 229, 255))
    draw.rectangle([400, 580, 440, 615], fill=(30, 136, 229, 255))
    # Radar Mast & Antenna
    draw.line([(400, 560), (400, 480)], fill=(200, 210, 220, 255), width=10)
    draw.ellipse([375, 465, 425, 495], fill=(255, 255, 255, 255)) # Radar dome
    # Fishing Outriggers (cần câu / giàn câu)
    draw.line([(360, 560), (240, 440)], fill=(255, 215, 0, 255), width=7) # Gold outrigger left
    draw.line([(440, 560), (550, 450)], fill=(255, 215, 0, 255), width=7) # Gold outrigger right

    # 4. Draw Dynamic Yellowfin Tuna (Cá ngừ vây vàng) Leaping
    # Tuna Body (sleek hydrodynamic torpedo shape)
    # Centered around right-upper quadrant leaping towards upper-center
    tuna_overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(tuna_overlay)

    # Main Body Polygon / Curves
    # Head at (520, 410), Belly curve down to (720, 530), Tail at (860, 490)
    body_pts = [
        (510, 390), # Snout tip
        (560, 360), (640, 360), (740, 390), (810, 440), (860, 465), # Dorsal curve
        (875, 470), # Keel base
        (855, 485), (790, 500), (700, 510), (600, 475), (540, 430), # Ventral belly
        (510, 390)
    ]
    # Dark Navy Metallic Blue Back
    t_draw.polygon(body_pts, fill=(24, 43, 73, 255))

    # Silver Belly Layer
    belly_pts = [
        (530, 415), (600, 465), (700, 495), (785, 485), (850, 468),
        (855, 485), (790, 500), (700, 510), (600, 475), (540, 430),
        (530, 415)
    ]
    t_draw.polygon(belly_pts, fill=(200, 215, 230, 255)) # Silver white

    # Yellowfin Tuna Signature Features: Bright Golden-Yellow Fins & Finlets!
    gold_fin = (255, 214, 0, 255) # Bright Yellow

    # Long curved Second Dorsal Fin (Vây lưng vàng dài vút)
    dorsal_fin = [
        (690, 370), (725, 250), (735, 385)
    ]
    t_draw.polygon(dorsal_fin, fill=gold_fin)

    # Long curved Anal Fin (Vây hậu môn vàng dài vút)
    anal_fin = [
        (690, 495), (720, 610), (730, 490)
    ]
    t_draw.polygon(anal_fin, fill=gold_fin)

    # Pectoral Fin (Vây ngực bên thân)
    pec_fin = [
        (580, 420), (660, 450), (640, 425)
    ]
    t_draw.polygon(pec_fin, fill=(255, 193, 7, 255))

    # Crescent / Lunate Caudal Fin (Đuôi hình trăng khuyết đặc trưng cá ngừ)
    tail_pts = [
        (865, 470),
        (920, 390), (940, 370), (925, 415), # Upper tail lobe
        (890, 470),
        (925, 525), (940, 570), (920, 545), # Lower tail lobe
        (865, 470)
    ]
    t_draw.polygon(tail_pts, fill=(255, 204, 0, 255))

    # Golden Finlets on tail keel (Vây phụ con màu vàng đặc trưng)
    for fx, fy in [(760, 395), (785, 415), (810, 435), (835, 450)]:
        t_draw.polygon([(fx, fy), (fx+12, fy-16), (fx+18, fy+4)], fill=gold_fin)
    for fx, fy in [(760, 490), (785, 480), (810, 470), (835, 465)]:
        t_draw.polygon([(fx, fy), (fx+12, fy+16), (fx+18, fy-4)], fill=gold_fin)

    # Eye
    t_draw.ellipse([540, 390, 555, 405], fill=(255, 255, 255, 255))
    t_draw.ellipse([544, 393, 552, 401], fill=(10, 20, 30, 255))

    # Paste Tuna
    img.paste(tuna_overlay, (0, 0), tuna_overlay)

    # Water Splashes around tuna leap
    splash_draw = ImageDraw.Draw(img)
    splash_color = (255, 255, 255, 230)
    splash_pts = [(480, 520, 16), (460, 480, 12), (490, 450, 10), (790, 540, 14), (820, 560, 10)]
    for sx, sy, sr in splash_pts:
        splash_draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=splash_color)

    # 5. Save PNG
    img_resampled = img.resize((512, 512), Image.Resampling.LANCZOS)
    img_resampled.save(output_png_path, "PNG")

    # 6. Save Multi-size ICO
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(output_ico_path, format="ICO", sizes=icon_sizes)
    print(f"Generated {output_png_path} and {output_ico_path} successfully!")

if __name__ == "__main__":
    create_app_icon()

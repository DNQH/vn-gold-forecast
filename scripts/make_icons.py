"""Tạo biểu tượng ứng dụng (đồng xu + thỏi vàng trên nền kem ấm) bằng Pillow. Chạy: python scripts/make_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "docs" / "icons"
S = 1024  # vẽ ở độ phân giải cao rồi thu nhỏ cho mịn


def motif(d: ImageDraw.ImageDraw, cx: int, cy: int, k: float):
    """Thỏi vàng (hình thang) phía sau + đồng xu phía trước; k = tỷ lệ so với canvas 1024."""
    def P(x, y):
        return (cx + x * k, cy + y * k)
    # thỏi vàng
    bar = [P(-330, 190), P(330, 190), P(270, 40), P(-270, 40)]
    d.polygon(bar, fill="#d99a1e", outline="#8a5a0a", width=int(14 * k))
    top = [P(-270, 40), P(270, 40), P(215, -40), P(-215, -40)]
    d.polygon(top, fill="#f3c04f", outline="#8a5a0a", width=int(14 * k))
    # đồng xu
    r, r2, cyc = 215, 160, -235
    c = P(0, cyc)
    d.ellipse([c[0] - r * k, c[1] - r * k, c[0] + r * k, c[1] + r * k], fill="#f3c04f", outline="#8a5a0a", width=int(18 * k))
    d.ellipse([c[0] - r2 * k, c[1] - r2 * k, c[0] + r2 * k, c[1] + r2 * k], outline="#b7791f", width=int(16 * k))
    # dấu "V" cách điệu trên đồng xu (vàng Việt Nam)
    w = int(34 * k)
    d.line([P(-70, -305), P(0, -175), P(70, -305)], fill="#8a5a0a", width=w, joint="curve")


def make(size: int, scale: float, bg_full: bool, name: str, rounded: bool):
    im = Image.new("RGBA", (S, S), "#fdf3dc" if bg_full else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if not bg_full:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill="#fdf3dc")
    # viền vàng mảnh cho dễ nhìn trên màn hình nền sáng
    if not bg_full:
        d.rounded_rectangle([14, 14, S - 15, S - 15], radius=int(S * 0.2), outline="#e8c777", width=14)
    motif(d, S // 2, int(S * 0.6), scale)
    im = im.resize((size, size), Image.LANCZOS)
    if bg_full:
        im = im.convert("RGB")
    im.save(OUT / name)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make(192, 1.0, False, "icon-192.png", True)
    make(512, 1.0, False, "icon-512.png", True)
    make(512, 0.78, True, "maskable-512.png", False)       # nền tràn viền, hình thu nhỏ trong vùng an toàn 80%
    make(180, 0.92, True, "apple-touch-icon-180.png", False)  # iOS tự bo góc, không để trong suốt
    print("OK", sorted(p.name for p in OUT.iterdir()))

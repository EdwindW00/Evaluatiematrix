"""Genereert een kleurrijk, iconisch app-icoon (.ico) voor de Evaluatiematrix-assistent.

Stijl: bold gekleurde starburst/asterisk (verwijst naar 'beoordeling/score') op een
gradient-rondje in de navy huisstijl — herkenbaar en kleurrijk zoals gevraagd, maar een
eigen ontwerp (geen kopie van een bestaand merk-logo).
"""
import math

from PIL import Image, ImageDraw

SIZE = 256
OUT = r"C:\Users\deweerd\Documents\evaluatiematrix-app\app_icon.ico"

PRIMAIR = (26, 78, 140)     # #1A4E8C
ACCENT = (46, 109, 180)     # #2E6DB4
PETAL_KLEUREN = [
    (255, 193, 69),   # goud
    (255, 138, 69),   # oranje
    (255, 99, 97),    # koraal
    (255, 92, 141),   # roze
    (196, 92, 214),   # paars
    (255, 138, 69),
    (255, 193, 69),
    (255, 214, 120),
]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def maak_achtergrond(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            px[x, y] = lerp(PRIMAIR, ACCENT, t) + (255,)

    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    radius = int(size * 0.22)
    mdraw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)

    rond = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rond.paste(img, (0, 0), mask)
    return rond


def teken_starburst(img, cx, cy, lengte, dikte):
    draw = ImageDraw.Draw(img, "RGBA")
    n = len(PETAL_KLEUREN)
    for i, kleur in enumerate(PETAL_KLEUREN):
        hoek = (2 * math.pi * i) / n - math.pi / 2
        x2 = cx + lengte * math.cos(hoek)
        y2 = cy + lengte * math.sin(hoek)
        draw.line([(cx, cy), (x2, y2)], fill=kleur + (255,), width=dikte)
        # ronde uiteinden (cap)
        for px_, py_ in [(cx, cy), (x2, y2)]:
            r = dikte / 2
            draw.ellipse([px_ - r, py_ - r, px_ + r, py_ + r], fill=kleur + (255,))
    # centrumcirkel om alle punten netjes te laten samenkomen
    r = dikte * 0.62
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 214, 120, 255))


def main():
    img = maak_achtergrond(SIZE)
    cx, cy = SIZE / 2, SIZE / 2
    teken_starburst(img, cx, cy, lengte=SIZE * 0.32, dikte=int(SIZE * 0.10))

    sizes = [16, 24, 32, 48, 64, 128, 256]
    img.save(OUT, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Icoon opgeslagen: {OUT}")


if __name__ == "__main__":
    main()

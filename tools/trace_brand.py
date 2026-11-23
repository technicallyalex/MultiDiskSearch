"""Trace the approved raster geometry into transparent SVG application assets.

No font substitution or manual reinterpretation of the MDS letterforms. Run from
the project root using the private Qt runtime. Output paths use even-odd fills.
"""
from pathlib import Path
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]


def simplify(points, tolerance=0.55):
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    distances = []
    for x, y in points[1:-1]:
        t = max(0, min(1, ((x-a[0])*dx + (y-a[1])*dy) / length)) if length else 0
        distances.append((x-a[0]-t*dx)**2 + (y-a[1]-t*dy)**2)
    maximum = max(distances)
    if maximum <= tolerance*tolerance:
        return [a, b]
    split = distances.index(maximum) + 1
    return simplify(points[:split+1], tolerance)[:-1] + simplify(points[split:], tolerance)


def trace(mask):
    edges = {}
    def edge(a, b):
        edges.setdefault(a, []).append(b)
    for x, y in mask:
        if (x, y-1) not in mask: edge((x,y), (x+1,y))
        if (x+1, y) not in mask: edge((x+1,y), (x+1,y+1))
        if (x, y+1) not in mask: edge((x+1,y+1), (x,y+1))
        if (x-1, y) not in mask: edge((x,y+1), (x,y))
    paths = []
    while edges:
        start = next(iter(edges))
        point = start
        contour = []
        while True:
            contour.append(point)
            following = edges[point].pop()
            if not edges[point]: del edges[point]
            point = following
            if point == start: break
        area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(contour,contour[1:]+contour[:1]))) / 2
        if area < 8: continue
        split = len(contour)//2
        points = simplify(contour[:split+1])[:-1] + simplify(contour[split:]+contour[:1])
        paths.append('M' + ' L'.join(f'{x} {y}' for x,y in points) + ' Z')
    return ' '.join(paths)


def main():
    image = QImage(str(ROOT/'design/branding/variations/MDS-A-rounded-shadow-v1.png'))
    if image.isNull() or image.width() != 1774 or image.height() != 887:
        raise RuntimeError('Expected the approved 1774×887 concept sheet.')
    md, silhouette, wordmark = set(), set(), set()
    for y in range(188):
        for x in range(1574):
            color = image.pixelColor(x+108,y+194)
            r,g,b = color.red(), color.green(), color.blue()
            if x < 526:
                if b > 55 and b > r*1.3 and b > g*1.15:
                    silhouette.add((x,y))
                if r >= 60 and g >= 100 and b >= 180:
                    md.add((x,y))
            elif min(r,g,b) > 150:
                wordmark.add((x,y))
    shadow = silhouette - md
    definitions = '<defs><linearGradient id="shadow" x1="340" y1="94" x2="526" y2="94" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#1242bc"/><stop offset="0.5" stop-color="#2c4e98"/><stop offset="1" stop-color="#414d68" stop-opacity="0.8"/></linearGradient></defs>'
    shapes = f'<path d="{trace(shadow)}" fill="url(#shadow)" fill-rule="evenodd"/><path d="{trace(md)}" fill="#699aff" fill-rule="evenodd"/>'
    text = f'<path d="{trace(wordmark)}" fill="#f5f5f4" fill-rule="evenodd"/>'
    def save(name, width, height, body):
        (ROOT/'assets/brand'/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{definitions}{body}</svg>\n',encoding='utf-8')
    save('mds-mark.svg',526,188,shapes)
    save('mds-lockup.svg',1574,188,shapes+text)
    save('mds-icon.svg',256,256,'<rect width="256" height="256" rx="48" fill="#090c12"/><g transform="translate(27 92) scale(0.384)">'+shapes+'</g>')
    print('Traced approved MDS geometry and wordmark to transparent SVG assets.')


if __name__ == '__main__':
    main()

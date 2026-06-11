#!/usr/bin/env python3
"""
DXF to TRUMPF GEO Converter
Converts AutoCAD DXF files to TRUMPF TruLaser GEO format (v1.03)
Supports: LINE, ARC, CIRCLE, LWPOLYLINE (incl. bulge/arcs), POLYLINE, SPLINE, ELLIPSE
"""

import ezdxf
import math
import sys
import os
from datetime import datetime
import argparse


def normalize_angle(a):
    while a < 0: a += 360
    while a >= 360: a -= 360
    return a


def arc_midpoint(cx, cy, r, sa_deg, ea_deg, ccw):
    """Point in the middle of an arc (on the curve)."""
    if not ccw:
        sa_deg, ea_deg = ea_deg, sa_deg
    diff = ea_deg - sa_deg
    if diff <= 0:
        diff += 360
    mid_deg = sa_deg + diff / 2
    return (cx + r * math.cos(math.radians(mid_deg)),
            cy + r * math.sin(math.radians(mid_deg)))


def arc_tangent_corner(xs, ys, xe, ye, cx, cy):
    """
    Return the ARC CENTER — TRUMPF GEO ARC format is:
    ARC(endpoint1, CENTER, endpoint2, direction)
    The middle point IS the arc center, not a point on the curve.
    """
    return cx, cy


def bulge_to_arc_params(x1, y1, x2, y2, bulge):
    """
    Convert LWPOLYLINE bulge to arc parameters.
    Returns (cx, cy, r, start_angle_deg, end_angle_deg, ccw)
    bulge = tan(included_angle / 4), positive = CCW, negative = CW
    """
    d = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if d < 1e-10:
        return None
    r = d * (1 + bulge ** 2) / (4 * abs(bulge))
    # sagitta height
    s = bulge * d / 2
    # midpoint of chord
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    # unit vector perpendicular to chord
    ux = -(y2 - y1) / d
    uy = (x2 - x1) / d
    # center is offset from midpoint
    h = r - abs(s)
    sign = 1 if bulge > 0 else -1
    cx = mx + sign * h * ux
    cy = my + sign * h * uy
    sa = math.degrees(math.atan2(y1 - cy, x1 - cx)) % 360
    ea = math.degrees(math.atan2(y2 - cy, x2 - cx)) % 360
    ccw = bulge > 0
    return cx, cy, r, sa, ea, ccw


def arc_segments_from_entity(entity):
    """
    Parse a DXF ARC entity into (xs,ys, xm,ym, xe,ye, ccw).
    DXF ARCs are always CCW.
    """
    cx = entity.dxf.center.x
    cy = entity.dxf.center.y
    r = entity.dxf.radius
    sa = entity.dxf.start_angle
    ea = entity.dxf.end_angle
    sx = cx + r * math.cos(math.radians(sa))
    sy = cy + r * math.sin(math.radians(sa))
    ex = cx + r * math.cos(math.radians(ea))
    ey = cy + r * math.sin(math.radians(ea))
    tx, ty = arc_tangent_corner(sx, sy, ex, ey, cx, cy)
    return (sx, sy, tx, ty, ex, ey, True)


def spline_to_polyline(entity, tolerance=0.1):
    try:
        return [(p.x, p.y) for p in entity.flattening(tolerance)]
    except Exception:
        try:
            return [(p[0], p[1]) for p in entity.control_points]
        except Exception:
            return []


class GeoConverter:
    def __init__(self, source_file):
        self.source_file = source_file
        self.points = {}
        self.point_idx = 1
        self.contours = []

    def get_or_add_point(self, x, y, z=0.0, tol=1e-6):
        for idx, (px, py, _) in self.points.items():
            if abs(px - x) < tol and abs(py - y) < tol:
                return idx
        idx = self.point_idx
        self.points[idx] = (x, y, z)
        self.point_idx += 1
        return idx

    def add_contour(self, segments):
        """segments: list of ('LIN',...), ('ARC',...), or ('CIR', cx,cy,r)"""
        if not segments:
            return
        elements = []
        for seg in segments:
            if seg[0] == 'LIN':
                _, x1, y1, x2, y2 = seg
                if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9:
                    continue
                p1 = self.get_or_add_point(x1, y1)
                p2 = self.get_or_add_point(x2, y2)
                elements.append(('LIN', p1, p2))
            elif seg[0] == 'ARC':
                _, xs, ys, xm, ym, xe, ye, ccw = seg
                ps = self.get_or_add_point(xs, ys)
                pm = self.get_or_add_point(xm, ym)
                pe = self.get_or_add_point(xe, ye)
                elements.append(('ARC', ps, pm, pe, ccw))
            elif seg[0] == 'CIR':
                _, cx, cy, r = seg
                pc = self.get_or_add_point(cx, cy)
                elements.append(('CIR', pc, r))
        if elements:
            self.contours.append(elements)

    def process_lwpolyline(self, entity):
        """Handle LWPOLYLINE with full bulge support."""
        pts = list(entity.get_points(format='xyseb'))  # x, y, start_w, end_w, bulge
        if not pts:
            return
        n = len(pts)
        segments = []

        indices = list(range(n))
        if entity.closed:
            indices.append(0)  # close back to first point

        for i in range(len(indices) - 1):
            cur = pts[indices[i]]
            nxt = pts[indices[i + 1]]
            x1, y1, bulge = cur[0], cur[1], cur[4]
            x2, y2 = nxt[0], nxt[1]

            if abs(bulge) < 1e-10:
                segments.append(('LIN', x1, y1, x2, y2))
            else:
                result = bulge_to_arc_params(x1, y1, x2, y2, bulge)
                if result is None:
                    segments.append(('LIN', x1, y1, x2, y2))
                    continue
                cx, cy, r, sa, ea, ccw = result
                sx = cx + r * math.cos(math.radians(sa))
                sy = cy + r * math.sin(math.radians(sa))
                ex = cx + r * math.cos(math.radians(ea))
                ey = cy + r * math.sin(math.radians(ea))
                # TRUMPF GEO ARC format uses the tangent corner as middle point
                tx, ty = arc_tangent_corner(sx, sy, ex, ey, cx, cy)
                segments.append(('ARC', sx, sy, tx, ty, ex, ey, ccw))

        self.add_contour(segments)

    def process_dxf(self, dxf_path):
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        for entity in msp:
            etype = entity.dxftype()

            if etype == 'LINE':
                s, e = entity.dxf.start, entity.dxf.end
                self.add_contour([('LIN', s.x, s.y, e.x, e.y)])

            elif etype == 'ARC':
                xs, ys, xm, ym, xe, ye, ccw = arc_segments_from_entity(entity)
                self.add_contour([('ARC', xs, ys, xm, ym, xe, ye, ccw)])

            elif etype == 'CIRCLE':
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                # Use native CIR element — most efficient for TRUMPF
                self.add_contour([('CIR', cx, cy, r)])

            elif etype == 'LWPOLYLINE':
                self.process_lwpolyline(entity)

            elif etype == 'POLYLINE':
                vlist = list(entity.points())
                segs = []
                for i in range(len(vlist) - 1):
                    segs.append(('LIN', vlist[i].x, vlist[i].y, vlist[i+1].x, vlist[i+1].y))
                if entity.is_closed and len(vlist) > 1:
                    segs.append(('LIN', vlist[-1].x, vlist[-1].y, vlist[0].x, vlist[0].y))
                self.add_contour(segs)

            elif etype == 'SPLINE':
                pts = spline_to_polyline(entity)
                if len(pts) >= 2:
                    segs = [('LIN', pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
                            for i in range(len(pts) - 1)]
                    self.add_contour(segs)

            elif etype == 'ELLIPSE':
                try:
                    flat = list(entity.flattening(0.1))
                    segs = [('LIN', flat[i].x, flat[i].y, flat[i+1].x, flat[i+1].y)
                            for i in range(len(flat) - 1)]
                    self.add_contour(segs)
                except Exception:
                    pass

    def normalize_to_origin(self):
        """Shift all points so bounding box starts at (0, 0)."""
        if not self.points:
            return
        xs = [p[0] for p in self.points.values()]
        ys = [p[1] for p in self.points.values()]
        ox, oy = min(xs), min(ys)
        if abs(ox) < 1e-9 and abs(oy) < 1e-9:
            return  # already normalized
        self.points = {
            idx: (x - ox, y - oy, z)
            for idx, (x, y, z) in self.points.items()
        }

    def compute_bbox(self):
        if not self.points:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points.values()]
        ys = [p[1] for p in self.points.values()]
        return (min(xs), min(ys), 0.0), (max(xs), max(ys), 0.0)

    def compute_area(self):
        mn, mx = self.compute_bbox()
        return abs((mx[0] - mn[0]) * (mx[1] - mn[1]))

    def write_geo(self, out_path, dxf_filename):
        self.normalize_to_origin()
        now = datetime.now().strftime("%d.%m.%Y")
        mn, mx = self.compute_bbox()
        area = self.compute_area()
        cx = (mn[0] + mx[0]) / 2
        cy = (mn[1] + mx[1]) / 2

        lines = [
            "#~1", "1.03", "1", now,
            f"{mn[0]:.9f} {mn[1]:.9f} {mn[2]:.9f}",
            f"{mx[0]:.9f} {mx[1]:.9f} {mx[2]:.9f}",
            f"{area:.9f}", "1", "0.001000000", "0", "1", "##~~",
            "#~11",
            "", "", "", "", "", "",
            "0.000000000",
            "", "", "",
            "0", "0", "0", "0", "0", "0", "0", "0", "0", "",
            "##~~", "#~END",
            "#~3", "", "LASER", "",
            "0.000000000 0.000000000 1.000000000",
            "1.000000000 0.000000000 0.000000000 0.000000000",
            "0.000000000 1.000000000 0.000000000 0.000000000",
            "0.000000000 0.000000000 1.000000000 0.000000000",
            "0.000000000 0.000000000 0.000000000 1.000000000",
            f"{mn[0]:.9f} {mn[1]:.9f} {mn[2]:.9f}",
            f"{mx[0]:.9f} {mx[1]:.9f} {mx[2]:.9f}",
            f"{cx:.9f} {cy:.9f} 0.000000000",
            f"{area:.9f}",
            str(len(self.contours)),
            "0", "0", "0", "0", "##~~",
            "#~30", "ANSI_CODEPAGE@1252", "PART_VERSION@3",
            f"SOURCE_FILE_NAME@{os.path.abspath(dxf_filename).replace('/', chr(92))}",
            "#~TTINFO_END",
            "#~31",
        ]

        for idx in sorted(self.points.keys()):
            x, y, z = self.points[idx]
            lines += ["P", str(idx), f"{x:.9f} {y:.9f} {z:.9f}", "|~"]
        lines.append("##~~")

        # Count how many inner contours (holes) follow each outer contour
        # Outer contour = multi-element; inner = CIR or single closed shape
        # Strategy: first non-CIR contour = outer, all CIR = inner
        # field2 = number of inner contours in this group
        # For simplicity: outer contour gets count of all subsequent CIR contours
        # (works for typical single-part DXFs)
        inner_count = sum(1 for c in self.contours
                         if len(c) == 1 and c[0][0] == 'CIR')
        outer_count = len(self.contours) - inner_count

        for i, contour in enumerate(self.contours):
            pts_in = set()
            is_circle = len(contour) == 1 and contour[0][0] == 'CIR'
            cir_r = contour[0][2] if is_circle else 0
            for el in contour:
                if el[0] == 'LIN':
                    pts_in.update([el[1], el[2]])
                elif el[0] == 'ARC':
                    pts_in.update([el[1], el[2], el[3]])
                elif el[0] == 'CIR':
                    pts_in.add(el[1])

            if pts_in:
                cxs = [self.points[p][0] for p in pts_in if p in self.points]
                cys = [self.points[p][1] for p in pts_in if p in self.points]
                if is_circle:
                    cmn = (cxs[0] - cir_r, cys[0] - cir_r)
                    cmx = (cxs[0] + cir_r, cys[0] + cir_r)
                    cc = (cxs[0], cys[0])
                    ca = math.pi * cir_r * cir_r
                else:
                    cmn = (min(cxs), min(cys))
                    cmx = (max(cxs), max(cys))
                    cc = ((cmn[0] + cmx[0]) / 2, (cmn[1] + cmx[1]) / 2)
                    ca = abs((cmx[0] - cmn[0]) * (cmx[1] - cmn[1]))
            else:
                cmn = cmx = cc = (0.0, 0.0)
                ca = 0.0
                is_circle = False

            # field2: for outer contour = number of inner contours; for inner = 0
            # last_flag: 0 for outer, 1 for inner
            if is_circle:
                field2 = "0"
                last_flag = "1"
            else:
                field2 = str(inner_count)
                last_flag = "0"

            lines += [
                "#~33", "",
                f"{i+1} 24 {'1' if is_circle else '0'}", field2,
                "0.000000000 0.000000000 1.000000000",
                f"{cmn[0]:.9f} {cmn[1]:.9f} 0.000000000",
                f"{cmx[0]:.9f} {cmx[1]:.9f} 0.000000000",
                f"{cc[0]:.9f} {cc[1]:.9f} 0.000000000",
                f"{ca:.9f}", last_flag, "##~~", "#~331",
            ]
            for el in contour:
                if el[0] == 'LIN':
                    lines += ["LIN", "1 0", f"{el[1]} {el[2]}", "|~"]
                elif el[0] == 'ARC':
                    _, ps, pm, pe, ccw = el
                    lines += ["ARC", "1 0", f"{pm} {ps} {pe}", "1" if ccw else "-1", "|~"]
                elif el[0] == 'CIR':
                    _, pc, r = el
                    lines += ["CIR", "1 0", str(pc), f"{r:.9f}", "|~"]
            lines += ["##~~", "#~KONT_END"]

        lines += ["#~END", "#~EOF"]

        with open(out_path, 'w', newline='', encoding='cp1252', errors='replace') as f:
            for line in lines:
                f.write(line + '\r\n')

        return len(self.points), len(self.contours)


def convert(dxf_path, out_path=None):
    if out_path is None:
        out_path = os.path.splitext(dxf_path)[0] + ".GEO"
    conv = GeoConverter(source_file=dxf_path)
    conv.process_dxf(dxf_path)
    npts, nctrs = conv.write_geo(out_path, dxf_path)
    print(f"OK: {os.path.basename(dxf_path)} -> {os.path.basename(out_path)}  "
          f"({npts} points, {nctrs} contours)")
    return out_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DXF to TRUMPF GEO Converter')
    parser.add_argument('input', nargs='+', help='DXF file(s)')
    parser.add_argument('-o', '--output', help='Output file (single input only)')
    args = parser.parse_args()
    for f in args.input:
        out = args.output if (len(args.input) == 1 and args.output) else None
        try:
            convert(f, out)
        except Exception as e:
            print(f"ERROR: {f}: {e}", file=sys.stderr)
            sys.exit(1)

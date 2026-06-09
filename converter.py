#!/usr/bin/env python3
"""
DXF to TRUMPF GEO Converter
Converts AutoCAD DXF files to TRUMPF TruLaser GEO format (v1.03)
Supports: LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE, SPLINE (approximated)
"""

import ezdxf
from ezdxf.math import Vec3
import math
import sys
import os
from datetime import datetime
import argparse


def normalize_angle(angle_deg):
    """Normalize angle to [0, 360)"""
    while angle_deg < 0:
        angle_deg += 360
    while angle_deg >= 360:
        angle_deg -= 360
    return angle_deg


def arc_points_and_midpoint(cx, cy, r, start_deg, end_deg, ccw=True):
    """
    Given arc center, radius, start/end angles, compute:
      - start point, mid point (on arc), end point
    ccw: counter-clockwise direction (TRUMPF ARC direction flag 1=ccw)
    """
    if not ccw:
        start_deg, end_deg = end_deg, start_deg

    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)

    sx = cx + r * math.cos(start_rad)
    sy = cy + r * math.sin(start_rad)
    ex = cx + r * math.cos(end_rad)
    ey = cy + r * math.sin(end_rad)

    # midpoint angle
    diff = end_deg - start_deg
    if diff <= 0:
        diff += 360
    mid_deg = start_deg + diff / 2
    mid_rad = math.radians(mid_deg)
    mx = cx + r * math.cos(mid_rad)
    my = cy + r * math.sin(mid_rad)

    return (sx, sy), (mx, my), (ex, ey)


def spline_to_polyline(entity, tolerance=0.1):
    """Approximate a SPLINE entity with line segments"""
    try:
        points = list(entity.flattening(tolerance))
        return [(p.x, p.y) for p in points]
    except Exception:
        # Fallback: use control points
        try:
            return [(p[0], p[1]) for p in entity.control_points]
        except Exception:
            return []


class GeoConverter:
    def __init__(self, source_file):
        self.source_file = source_file
        self.points = {}        # index -> (x, y, z)
        self.point_idx = 1
        self.contours = []      # list of contour objects

    def get_or_add_point(self, x, y, z=0.0, tol=1e-6):
        """Add a point or return existing index if close enough"""
        for idx, (px, py, pz) in self.points.items():
            if abs(px - x) < tol and abs(py - y) < tol:
                return idx
        idx = self.point_idx
        self.points[idx] = (x, y, z)
        self.point_idx += 1
        return idx

    def add_line_contour(self, segments):
        """
        segments: list of (type, data)
          type 'LIN': data = (x1,y1, x2,y2)
          type 'ARC': data = (xs,ys, xm,ym, xe,ye, ccw)
        """
        if not segments:
            return
        elements = []
        for seg_type, data in segments:
            if seg_type == 'LIN':
                x1, y1, x2, y2 = data
                p1 = self.get_or_add_point(x1, y1)
                p2 = self.get_or_add_point(x2, y2)
                elements.append(('LIN', p1, p2))
            elif seg_type == 'ARC':
                xs, ys, xm, ym, xe, ye, ccw = data
                ps = self.get_or_add_point(xs, ys)
                pm = self.get_or_add_point(xm, ym)
                pe = self.get_or_add_point(xe, ye)
                elements.append(('ARC', ps, pm, pe, ccw))
        if elements:
            self.contours.append(elements)

    def process_dxf(self, dxf_path):
        """Parse DXF and collect geometry"""
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        for entity in msp:
            etype = entity.dxftype()

            if etype == 'LINE':
                s = entity.dxf.start
                e = entity.dxf.end
                self.add_line_contour([('LIN', (s.x, s.y, e.x, e.y))])

            elif etype == 'ARC':
                cx = entity.dxf.center.x
                cy = entity.dxf.center.y
                r = entity.dxf.radius
                sa = entity.dxf.start_angle
                ea = entity.dxf.end_angle
                # DXF ARC is always CCW
                (sx, sy), (mx, my), (ex, ey) = arc_points_and_midpoint(cx, cy, r, sa, ea, ccw=True)
                self.add_line_contour([('ARC', (sx, sy, mx, my, ex, ey, True))])

            elif etype == 'CIRCLE':
                cx = entity.dxf.center.x
                cy = entity.dxf.center.y
                r = entity.dxf.radius
                # Full circle: split into two 180° arcs
                (sx, sy), (mx, my), (ex, ey) = arc_points_and_midpoint(cx, cy, r, 0, 180, ccw=True)
                (sx2, sy2), (mx2, my2), (ex2, ey2) = arc_points_and_midpoint(cx, cy, r, 180, 360, ccw=True)
                self.add_line_contour([
                    ('ARC', (sx, sy, mx, my, ex, ey, True)),
                    ('ARC', (sx2, sy2, mx2, my2, ex2, ey2, True)),
                ])

            elif etype in ('LWPOLYLINE', 'POLYLINE'):
                pts = []
                if etype == 'LWPOLYLINE':
                    pts = list(entity.vertices())
                    # Check for bulge (arcs in polylines)
                    segs = []
                    verts = list(entity.vertices_in_wcs() if hasattr(entity, 'vertices_in_wcs') else entity.get_points())
                    # Use flattening for simplicity
                    flat = list(entity.explode() if hasattr(entity, 'explode') else [])
                    if not flat:
                        pts2d = [(v[0], v[1]) for v in entity.get_points()]
                        for i in range(len(pts2d) - 1):
                            x1, y1 = pts2d[i]
                            x2, y2 = pts2d[i + 1]
                            segs.append(('LIN', (x1, y1, x2, y2)))
                        if entity.closed and len(pts2d) > 1:
                            x1, y1 = pts2d[-1]
                            x2, y2 = pts2d[0]
                            segs.append(('LIN', (x1, y1, x2, y2)))
                        self.add_line_contour(segs)
                    else:
                        for sub in flat:
                            self._process_sub_entity(sub)
                else:
                    # POLYLINE
                    segs = []
                    vlist = list(entity.points())
                    for i in range(len(vlist) - 1):
                        x1, y1 = vlist[i].x, vlist[i].y
                        x2, y2 = vlist[i + 1].x, vlist[i + 1].y
                        segs.append(('LIN', (x1, y1, x2, y2)))
                    if entity.is_closed and len(vlist) > 1:
                        x1, y1 = vlist[-1].x, vlist[-1].y
                        x2, y2 = vlist[0].x, vlist[0].y
                        segs.append(('LIN', (x1, y1, x2, y2)))
                    self.add_line_contour(segs)

            elif etype == 'SPLINE':
                pts = spline_to_polyline(entity)
                if len(pts) >= 2:
                    segs = []
                    for i in range(len(pts) - 1):
                        x1, y1 = pts[i]
                        x2, y2 = pts[i + 1]
                        segs.append(('LIN', (x1, y1, x2, y2)))
                    self.add_line_contour(segs)

            elif etype == 'ELLIPSE':
                # Approximate ellipse with line segments
                try:
                    pts = list(entity.flattening(0.1))
                    segs = []
                    for i in range(len(pts) - 1):
                        segs.append(('LIN', (pts[i].x, pts[i].y, pts[i+1].x, pts[i+1].y)))
                    self.add_line_contour(segs)
                except Exception:
                    pass

    def _process_sub_entity(self, entity):
        """Process a sub-entity (from exploded polyline)"""
        etype = entity.dxftype()
        if etype == 'LINE':
            s = entity.dxf.start
            e = entity.dxf.end
            self.add_line_contour([('LIN', (s.x, s.y, e.x, e.y))])
        elif etype == 'ARC':
            cx = entity.dxf.center.x
            cy = entity.dxf.center.y
            r = entity.dxf.radius
            sa = entity.dxf.start_angle
            ea = entity.dxf.end_angle
            (sx, sy), (mx, my), (ex, ey) = arc_points_and_midpoint(cx, cy, r, sa, ea, ccw=True)
            self.add_line_contour([('ARC', (sx, sy, mx, my, ex, ey, True))])

    def compute_bbox(self):
        if not self.points:
            return (0, 0, 0), (0, 0, 0)
        xs = [p[0] for p in self.points.values()]
        ys = [p[1] for p in self.points.values()]
        return (min(xs), min(ys), 0.0), (max(xs), max(ys), 0.0)

    def compute_area(self):
        """Rough bounding box area"""
        mn, mx = self.compute_bbox()
        return abs((mx[0] - mn[0]) * (mx[1] - mn[1]))

    def write_geo(self, out_path, dxf_filename):
        """Write TRUMPF GEO v1.03 file"""
        now = datetime.now().strftime("%d.%m.%Y")
        mn, mx = self.compute_bbox()
        area = self.compute_area()
        cx = (mn[0] + mx[0]) / 2
        cy = (mn[1] + mx[1]) / 2

        lines = []

        # Section #~1: File header
        lines += [
            "#~1",
            "1.03",
            "1",
            now,
            f"{mn[0]:.9f} {mn[1]:.9f} {mn[2]:.9f}",
            f"{mx[0]:.9f} {mx[1]:.9f} {mx[2]:.9f}",
            f"{area:.9f}",
            "1",
            "0.001000000",
            "0",
            "1",
            "##~~",
        ]

        # Section #~11: Material/tech (empty defaults)
        lines += [
            "#~11",
            "", "", "", "", "", "",
            "0.000000000",
            "", "", "",
            "0", "0", "0", "0", "0", "0", "0", "0", "0",
            "",
            "##~~",
            "#~END",
        ]

        # Section #~3: Part info
        lines += [
            "#~3",
            "",
            "LASER",
            "",
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
            "0", "0", "0", "0",
            "##~~",
        ]

        # Section #~30: Metadata
        abs_path = os.path.abspath(dxf_filename).replace('/', '\\')
        lines += [
            "#~30",
            "ANSI_CODEPAGE@1252",
            "PART_VERSION@3",
            f"SOURCE_FILE_NAME@{abs_path}",
            "#~TTINFO_END",
        ]

        # Section #~31: Points
        lines.append("#~31")
        for idx in sorted(self.points.keys()):
            x, y, z = self.points[idx]
            lines += [
                "P",
                str(idx),
                f"{x:.9f} {y:.9f} {z:.9f}",
                "|~",
            ]
        lines.append("##~~")

        # Section #~33: Contours
        for i, contour in enumerate(self.contours):
            # Compute contour bbox
            pts_in_contour = set()
            for el in contour:
                if el[0] == 'LIN':
                    pts_in_contour.add(el[1])
                    pts_in_contour.add(el[2])
                elif el[0] == 'ARC':
                    pts_in_contour.add(el[1])
                    pts_in_contour.add(el[2])
                    pts_in_contour.add(el[3])

            if pts_in_contour:
                cxs = [self.points[p][0] for p in pts_in_contour if p in self.points]
                cys = [self.points[p][1] for p in pts_in_contour if p in self.points]
                cmn = (min(cxs), min(cys))
                cmx = (max(cxs), max(cys))
                cc = ((cmn[0] + cmx[0]) / 2, (cmn[1] + cmx[1]) / 2)
                ca = abs((cmx[0] - cmn[0]) * (cmx[1] - cmn[1]))
            else:
                cmn = cmx = cc = (0.0, 0.0)
                ca = 0.0

            lines += [
                "#~33",
                "",
                f"{i+1} {len(contour)} 0",
                "0",
                "0.000000000 0.000000000 1.000000000",
                f"{cmn[0]:.9f} {cmn[1]:.9f} 0.000000000",
                f"{cmx[0]:.9f} {cmx[1]:.9f} 0.000000000",
                f"{cc[0]:.9f} {cc[1]:.9f} 0.000000000",
                f"{ca:.9f}",
                "0",
                "##~~",
                "#~331",
            ]

            for el in contour:
                if el[0] == 'LIN':
                    _, p1, p2 = el
                    lines += [
                        "LIN",
                        "1 0",
                        f"{p1} {p2}",
                        "|~",
                    ]
                elif el[0] == 'ARC':
                    _, ps, pm, pe, ccw = el
                    direction = "1" if ccw else "0"
                    lines += [
                        "ARC",
                        "1 0",
                        f"{ps} {pm} {pe}",
                        direction,
                        "|~",
                    ]

            lines += ["##~~", "#~KONT_END"]

        lines += ["#~END", "#~EOF"]

        with open(out_path, 'w', newline='\r\n', encoding='cp1252', errors='replace') as f:
            for line in lines:
                f.write(line + '\r\n')

        return len(self.points), len(self.contours)


def convert(dxf_path, out_path=None):
    if out_path is None:
        base = os.path.splitext(dxf_path)[0]
        out_path = base + ".GEO"

    conv = GeoConverter(source_file=dxf_path)
    conv.process_dxf(dxf_path)
    npts, ncontours = conv.write_geo(out_path, dxf_path)
    print(f"OK: {os.path.basename(dxf_path)} -> {os.path.basename(out_path)}  "
          f"({npts} points, {ncontours} contours)")
    return out_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DXF to TRUMPF GEO Converter')
    parser.add_argument('input', nargs='+', help='DXF file(s) to convert')
    parser.add_argument('-o', '--output', help='Output GEO file (single file only)')
    args = parser.parse_args()

    for f in args.input:
        out = args.output if (len(args.input) == 1 and args.output) else None
        try:
            convert(f, out)
        except Exception as e:
            print(f"ERROR: {f}: {e}", file=sys.stderr)
            sys.exit(1)

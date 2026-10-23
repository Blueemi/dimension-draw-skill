"""dimdraw: Apple-style dimensional drawings as self-contained SVG (+ PNG/PDF).

    from dimdraw import Sheet
    sh = Sheet(size="D", product="Widget", page=1)
    v = sh.view(x=300, y=280, scale=1.5)
    body = v.rect(0, 0, 70, 150, r=10)
    v.dim_h(body.tl, body.tr, offset=12, label="PRODUCT\\nWIDTH")
    sh.save("out/widget.svg")
"""

from .sheet import Sheet, SIZES, STYLE, PRESETS, save_pdf  # noqa: F401
from .geom import Path, rect_path, circle_path, slot_path, polygon_path  # noqa: F401
from .view import View, Shape, PROJECTION, project  # noqa: F401
from .mesh import (Model, Mesh, section, resample, superellipse, spline, load_stl,  # noqa: F401
                   load_obj, save_stl)
from . import mesh  # noqa: F401

__all__ = ["Sheet", "save_pdf", "PRESETS", "View", "Shape", "Path", "SIZES", "STYLE", "rect_path", "circle_path",
           "slot_path", "polygon_path", "PROJECTION", "project", "Model", "Mesh",
           "section", "resample", "superellipse", "spline", "load_stl", "load_obj", "save_stl", "mesh"]

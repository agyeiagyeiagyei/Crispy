# -*- coding: utf-8 -*-
"""Corner Radii — Glyphs Reporter plugin.

Audits existing rounded corners: fits a circle to each detected round,
draws its radius, and previews a scaled version as a thin blue line —
the transformation on the corner, live, before anything is written.

- Blue line   = proposed radius (current factor applied), per class
- Gray circle = current fitted radius (for comparison)
- Amber ring  = round that isn't very circular (large fit residual)

Outer corners (exterior contours) and inner corners (counters) get
independent factors. Apply writes scaled node positions into the SAME
node slots, so masters stay interpolation-compatible. Scope: current
glyph or all glyphs, across any ticked masters.
"""

from __future__ import division, print_function, unicode_literals

import os
import sys
import time

import objc
from AppKit import NSBezierPath, NSColor, NSTimer
from GlyphsApp import *
from GlyphsApp.plugins import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cornerfit  # noqa: E402

try:
    from vanilla import (
        Button,
        CheckBox,
        EditText,
        FloatingWindow,
        PopUpButton,
        TextBox,
    )
except ImportError:  # vanilla ships with Glyphs; guard for dev linting
    FloatingWindow = None


BLUE = (0.10, 0.45, 0.95)
AMBER = (0.95, 0.62, 0.10)
GRAY = (0.45, 0.45, 0.45)

# A round whose circle-fit residual exceeds this fraction of its radius
# is flagged "not very circular".
RESIDUAL_FLAG = 0.08

_DEBUG_LOG = "/tmp/cornerradii-debug.log"


def _dbg(msg):
    """Load-path instrumentation while the plugin is young."""
    try:
        import traceback as _tb
        with open(_DEBUG_LOG, "a") as f:
            f.write("%s\n" % msg)
            if msg == "EXCEPTION":
                f.write(_tb.format_exc())
    except Exception:
        pass


def _rgba(rgb, a):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], a)


class CornerRadii(ReporterPlugin):
    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({"en": "Corner Radii"})
        self.keyboardShortcut = None
        self.outerFactor = 1.0
        self.innerFactor = 1.0
        self.baselineOnly = False
        self.showCircles = True
        self.showHandles = True
        self.showOutlines = True
        self.flagOverlaps = True
        self.glyphScope = "current"          # "current" | "all"
        self.masterSelections = {}           # masterId -> bool (default True)
        self._panel = None
        self._masterRows = {}                # masterId -> CheckBox widget
        self._lastLayer = None               # fallback for target resolution
        # Draw whenever foreground() is invoked — Glyphs itself gates that
        # on the View toggle. activate()/deactivate() (if this build calls
        # them) only drive panel show/hide + the master switch below.
        self._active = True

    @objc.python_method
    def start(self):
        _dbg("start() called")
        self._lastForegroundAt = 0.0
        if FloatingWindow is not None:
            # Build hidden — the reporter's draw heartbeat (View toggle)
            # orders the panel front on the first foreground() call.
            self._build_panel()
        self._startHeartbeat()

    @objc.python_method
    def _startHeartbeat(self):
        """Panel visibility is driven by the reporter's draw heartbeat:
        foreground() fires only while View → Corner Radii is enabled (and
        an Edit view is focused), so show the panel when those calls are
        recent, hide it ~1.5s after they stop. activate()/deactivate() are
        NOT called by this Glyphs build for View toggles (verified), so
        this is the only reliable tie."""
        try:
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.75, self, objc.selector(self._panelHeartbeat_), None, True
            )
        except Exception:
            _dbg("EXCEPTION")

    @objc.python_method
    def _nswindow(self):
        """The panel's real NSWindow. Visibility MUST go through this:
        vanilla's wrapper forwards isVisible but NOT orderOut_ /
        makeKeyAndOrderFront_ — calling those on the vanilla object
        raises AttributeError, which the try/excepts below silently
        swallowed, leaving the panel impossible to hide once opened."""
        if self._panel is None:
            return None
        return self._panel.getNSWindow()

    # NOTE: NOT @objc.python_method — NSTimer needs this as a real ObjC
    # selector. The trailing underscore gives it the required single colon
    # (and keeps the class-transform's arg-count check happy).
    def _panelHeartbeat_(self, timer):
        ns = self._nswindow()
        if ns is None:
            return
        try:
            idle = time.time() - self._lastForegroundAt
            if idle > 1.5 and ns.isVisible():
                ns.orderOut_(None)
        except Exception:
            pass

    @objc.python_method
    def activate(self):
        """Reporter toggled ON (View menu) — show overlay AND panel."""
        _dbg("activate() called")
        self._active = True
        if FloatingWindow is None:
            return
        if self._panel is None:
            self._build_panel()
        ns = self._nswindow()
        if ns is not None:
            try:
                ns.makeKeyAndOrderFront_(None)
            except Exception:
                pass
        self._redraw()

    @objc.python_method
    def deactivate(self):
        """Reporter toggled OFF — hide overlay AND panel."""
        _dbg("deactivate() called")
        self._active = False
        ns = self._nswindow()
        if ns is not None:
            try:
                ns.orderOut_(None)
            except Exception:
                pass
        self._redraw()

    # ------------------------------------------------------------------
    # font / layer resolution (robust — undo can shift the active layer)
    # ------------------------------------------------------------------

    @objc.python_method
    def _currentFont(self):
        try:
            if Glyphs.font is not None:
                return Glyphs.font
        except Exception:
            pass
        try:
            doc = Glyphs.currentDocument
            if doc is not None:
                return doc.font
        except Exception:
            pass
        if self._lastLayer is not None:
            try:
                return self._lastLayer.parent.font
            except Exception:
                pass
        return None

    @objc.python_method
    def _currentGlyph(self):
        if self._lastLayer is not None:
            try:
                return self._lastLayer.parent
            except Exception:
                pass
        try:
            layer = self.controller.activeLayer()
            if layer is not None:
                return layer.parent
        except Exception:
            pass
        try:
            layer = Glyphs.currentDocument.selectedLayers[0]
            return layer.parent
        except Exception:
            pass
        return None

    @objc.python_method
    def _targets(self):
        """[(glyph, layer)] to transform, from glyph scope + ticked masters."""
        font = self._currentFont()
        if font is None:
            _dbg("_targets: no font")
            return []
        master_ids = [
            m.id for m in font.masters if self.masterSelections.get(m.id, True)
        ]
        if self.glyphScope == "all":
            glyphs = list(font.glyphs)
        else:
            glyph = self._currentGlyph()
            if glyph is None:
                _dbg("_targets: no current glyph (scope=current)")
                return []
            glyphs = [glyph]
        targets = []
        for g in glyphs:
            for mid in master_ids:
                try:
                    targets.append((g, g.layers[mid]))
                except Exception:
                    pass
        return targets

    # ------------------------------------------------------------------
    # panel
    # ------------------------------------------------------------------

    @objc.python_method
    def _build_panel(self):
        w = FloatingWindow((320, 400), "Corner Radii", closable=False)
        self._panel = w
        y = 12
        w.outerLabel = TextBox((12, y, 70, 20), "Outer ×")
        w.outerField = EditText((82, y, 56, 22), "%.2f" % self.outerFactor,
                                callback=self._outerFieldChanged)
        w.outerMinus = Button((146, y, 30, 22), "−", callback=self._outerMinus)
        w.outerPlus = Button((180, y, 30, 22), "+", callback=self._outerPlus)
        y += 32
        w.innerLabel = TextBox((12, y, 70, 20), "Inner ×")
        w.innerField = EditText((82, y, 56, 22), "%.2f" % self.innerFactor,
                                callback=self._innerFieldChanged)
        w.innerMinus = Button((146, y, 30, 22), "−", callback=self._innerMinus)
        w.innerPlus = Button((180, y, 30, 22), "+", callback=self._innerPlus)
        y += 32
        w.showLabel = TextBox((12, y, 50, 20), "Show:")
        w.showCirclesBox = CheckBox((64, y, 70, 20), "Circles",
                                    value=self.showCircles,
                                    callback=self._showCirclesChanged)
        w.showHandlesBox = CheckBox((140, y, 74, 20), "Handles",
                                    value=self.showHandles,
                                    callback=self._showHandlesChanged)
        w.showOutlinesBox = CheckBox((220, y, 76, 20), "Outlines",
                                     value=self.showOutlines,
                                     callback=self._showOutlinesChanged)
        y += 26
        w.flagOverlapBox = CheckBox((12, y, 220, 20), "Flag outer/inner overlaps",
                                    value=self.flagOverlaps,
                                    callback=self._flagOverlapsChanged)
        y += 26
        w.baselineBox = CheckBox((12, y, 220, 20), "Baseline corners only",
                                 value=self.baselineOnly,
                                 callback=self._baselineChanged)
        y += 28
        w.scopeLabel = TextBox((12, y, 70, 20), "Apply to")
        w.scopePop = PopUpButton((82, y, 140, 22),
                                 ["Current glyph", "All glyphs"],
                                 callback=self._scopeChanged)
        y += 28
        w.mastersLabel = TextBox((12, y, 200, 20), "Masters:")
        y += 22
        self._mastersY = y
        self._mastersBlockY = y
        self._refreshMasters()
        w.open()
        ns = self._nswindow()
        # Keep the window out of macOS session restoration so it can't
        # resurrect at launch independent of the View toggle.
        ns.setRestorable_(False)
        ns.disableSnapshotRestoration()
        # Build hidden, per start()'s contract — foreground() orders the
        # panel front once View → Corner Radii is actually enabled, and
        # the heartbeat hides it again when those draws stop.
        ns.orderOut_(None)

    @objc.python_method
    def _refreshMasters(self):
        """(Re)build the master tick-box list, preserving selections."""
        if self._panel is None:
            return
        font = self._currentFont()
        w = self._panel
        # drop previous rows
        for mid, cb in list(self._masterRows.items()):
            try:
                delattr(w, "master_%s" % mid.replace("-", "_"))
            except Exception:
                pass
        self._masterRows = {}
        if font is None:
            return
        y = self._mastersBlockY
        for m in font.masters:
            selected = self.masterSelections.get(m.id, True)
            self.masterSelections[m.id] = selected
            cb = CheckBox(
                (24, y, 280, 20),
                m.name,
                value=selected,
                callback=self._masterToggled,
            )
            attr = "master_%s" % m.id.replace("-", "_")
            setattr(w, attr, cb)
            self._masterRows[m.id] = cb
            y += 22
        # (re)place the action row below the list
        if not hasattr(w, "applyButton"):
            w.applyButton = Button((12, y, 100, 26), "Apply", callback=self._apply)
            w.resetButton = Button((122, y, 100, 26), "Reset ×", callback=self._reset)
        else:
            w.applyButton.setPosSize((12, y, 100, 26))
            w.resetButton.setPosSize((122, y, 100, 26))
        try:
            w.resize((320, y + 40))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # panel callbacks
    # ------------------------------------------------------------------

    @objc.python_method
    def _readField(self, field, fallback):
        try:
            return max(0.01, float(field.get()))
        except (TypeError, ValueError):
            return fallback

    @objc.python_method
    def _syncFields(self):
        if self._panel is not None:
            self._panel.outerField.set("%.2f" % self.outerFactor)
            self._panel.innerField.set("%.2f" % self.innerFactor)

    @objc.python_method
    def _outerFieldChanged(self, sender):
        self.outerFactor = self._readField(sender, self.outerFactor)
        self._syncFields()
        self._redraw()

    @objc.python_method
    def _innerFieldChanged(self, sender):
        self.innerFactor = self._readField(sender, self.innerFactor)
        self._syncFields()
        self._redraw()

    @objc.python_method
    def _outerMinus(self, sender):
        self.outerFactor = max(0.01, round(self.outerFactor - 0.05, 3))
        self._syncFields()
        self._redraw()

    @objc.python_method
    def _outerPlus(self, sender):
        self.outerFactor = round(self.outerFactor + 0.05, 3)
        self._syncFields()
        self._redraw()

    @objc.python_method
    def _innerMinus(self, sender):
        self.innerFactor = max(0.01, round(self.innerFactor - 0.05, 3))
        self._syncFields()
        self._redraw()

    @objc.python_method
    def _innerPlus(self, sender):
        self.innerFactor = round(self.innerFactor + 0.05, 3)
        self._syncFields()
        self._redraw()

    @objc.python_method
    def _baselineChanged(self, sender):
        self.baselineOnly = bool(sender.get())
        self._redraw()

    @objc.python_method
    def _showCirclesChanged(self, sender):
        self.showCircles = bool(sender.get())
        self._redraw()

    @objc.python_method
    def _showHandlesChanged(self, sender):
        self.showHandles = bool(sender.get())
        self._redraw()

    @objc.python_method
    def _showOutlinesChanged(self, sender):
        self.showOutlines = bool(sender.get())
        self._redraw()

    @objc.python_method
    def _flagOverlapsChanged(self, sender):
        self.flagOverlaps = bool(sender.get())
        self._redraw()

    @objc.python_method
    def _scopeChanged(self, sender):
        self.glyphScope = "all" if sender.get() == "All glyphs" else "current"

    @objc.python_method
    def _masterToggled(self, sender):
        for mid, cb in self._masterRows.items():
            if cb is sender:
                self.masterSelections[mid] = bool(sender.get())
                break

    @objc.python_method
    def _reset(self, sender):
        self.outerFactor = self.innerFactor = 1.0
        self._syncFields()
        self._redraw()

    @objc.python_method
    def _redraw(self):
        self._refreshMasters()
        try:
            self.controller.redraw()
        except Exception:
            try:
                Glyphs.redraw()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------

    @objc.python_method
    def _visible_corners(self, layer):
        corners = cornerfit.find_corners(layer.paths)
        if self.baselineOnly:
            corners = [c for c in corners if c["baseline"]]
        return corners

    @objc.python_method
    def foreground(self, layer):
        """Glyphs 3 reporter draw entry (verified against working reporters
        on this machine — `drawForegroundForLayer_*` is Glyphs 2 API)."""
        if not self._active:
            return
        self._lastLayer = layer
        # The draw heartbeat IS the View-toggle signal: foreground only
        # fires while the reporter is enabled, so (re)show the panel here.
        self._lastForegroundAt = time.time()
        ns = self._nswindow()
        if ns is not None and not ns.isVisible():
            try:
                ns.makeKeyAndOrderFront_(None)
            except Exception:
                pass
        corners = self._visible_corners(layer)
        try:
            scale = self.getScale()
        except Exception:
            scale = 1.0
        for corner in corners:
            try:
                factor = (
                    self.innerFactor if corner["class"] == "counter" else self.outerFactor
                )
                if self.showCircles:
                    self._draw_fitted_circle(corner, scale)
                    self._draw_label(corner, factor, scale)
                if self.showOutlines:
                    self._draw_outline(layer, corner, factor, scale)
                if self.showHandles:
                    self._draw_handles(layer, corner, factor, scale)
            except Exception:
                _dbg("EXCEPTION")
        if self.flagOverlaps:
            self._draw_overlap_flags(layer, corners, scale)

    @objc.python_method
    def _draw_overlap_flags(self, layer, corners, scale):
        """Fill the lens where an OUTER round's scaled circle overlaps an
        INNER (counter) round's — radius growth colliding with a counter."""
        outer = [c for c in corners
                 if c["class"] == "outer" and c.get("center") and c.get("radius")]
        inner = [c for c in corners
                 if c["class"] == "counter" and c.get("center") and c.get("radius")]
        if not outer or not inner:
            return
        _rgba((0.95, 0.25, 0.15), 0.35).set()
        for o in outer:
            r1 = o["radius"] * self.outerFactor
            for i in inner:
                r2 = i["radius"] * self.innerFactor
                pts = cornerfit.circle_circle_lens(o["center"], r1, i["center"], r2)
                if not pts:
                    continue
                path = NSBezierPath.bezierPath()
                path.moveToPoint_(pts[0])
                for pt in pts[1:]:
                    path.lineToPoint_(pt)
                path.closePath()
                path.fill()

    # Older Glyphs builds call the non-options variant.
    @objc.python_method
    def drawForegroundForLayer_(self, layer):
        self.foreground(layer)

    @objc.python_method
    def _draw_fitted_circle(self, corner, scale):
        center, radius = corner.get("center"), corner.get("radius")
        if not center or not radius:
            return
        residual = corner.get("residual") or 0.0
        flagged = radius > 0 and (residual / radius) > RESIDUAL_FLAG
        color = _rgba(AMBER, 0.55) if flagged else _rgba(GRAY, 0.40)
        color.set()
        path = NSBezierPath.bezierPath()
        path.appendBezierPathWithOvalInRect_(
            (
                (center[0] - radius, center[1] - radius),
                (radius * 2.0, radius * 2.0),
            )
        )
        path.setLineWidth_(0.8 / scale)
        path.stroke()

    @objc.python_method
    def _draw_outline(self, layer, corner, factor, scale):
        positions = cornerfit.transformed_positions(
            layer.paths[corner["path_index"]], corner, factor
        )
        if not positions:
            return
        # the changed curve OUTLINE: stub in, cubic segment(s) through
        # the scaled handles, stub out — the shape as it would be applied.
        outline = NSBezierPath.bezierPath()
        outline.setLineWidth_(1.0 / scale)
        prev_pt = corner.get("prev")
        nxt_pt = corner.get("next")
        t1_idx = corner["segments"][0]["p0"] if corner.get("segments") else None
        start = positions.get(t1_idx) if t1_idx is not None else None
        if prev_pt is not None:
            outline.moveToPoint_(prev_pt)
        elif start is not None:
            outline.moveToPoint_(start)
        if start is not None and prev_pt is not None:
            outline.lineToPoint_(start)
        for seg in corner.get("segments", []):
            hs = [positions[i] for i in seg["handles"] if i in positions]
            p1 = positions.get(seg["p1"])
            if p1 is None:
                continue
            if len(hs) == 2:
                outline.curveToPoint_controlPoint1_controlPoint2_(p1, hs[0], hs[1])
            else:
                outline.lineToPoint_(p1)
        if nxt_pt is not None:
            outline.lineToPoint_(nxt_pt)
        _rgba(BLUE, 0.85).set()
        outline.stroke()

    @objc.python_method
    def _draw_handles(self, layer, corner, factor, scale):
        positions = cornerfit.transformed_positions(
            layer.paths[corner["path_index"]], corner, factor
        )
        if not positions:
            return
        # control polygon: tangent→handle lines + hollow handle markers,
        # filled dots at the scaled on-curve (tangent/mid) positions.
        polygon = NSBezierPath.bezierPath()
        polygon.setLineWidth_(0.7 / scale)
        _rgba(BLUE, 0.45).set()
        for seg in corner.get("segments", []):
            hs = [positions[i] for i in seg["handles"] if i in positions]
            p0 = positions.get(seg["p0"])
            p1 = positions.get(seg["p1"])
            if p0 is not None and hs:
                polygon.moveToPoint_(p0)
                polygon.lineToPoint_(hs[0])
            if p1 is not None and hs:
                polygon.moveToPoint_(hs[-1])
                polygon.lineToPoint_(p1)
            for (hx, hy) in hs:
                marker = NSBezierPath.bezierPath()
                r = 1.8 / scale
                marker.appendBezierPathWithOvalInRect_(((hx - r, hy - r), (r * 2.0, r * 2.0)))
                marker.setLineWidth_(0.8 / scale)
                marker.stroke()
        polygon.stroke()
        oncurve_idxs = {seg["p0"] for seg in corner.get("segments", [])}
        oncurve_idxs |= {seg["p1"] for seg in corner.get("segments", [])}
        _rgba(BLUE, 0.9).set()
        for idx in oncurve_idxs:
            pt = positions.get(idx)
            if pt is None:
                continue
            dot = NSBezierPath.bezierPath()
            r = 2.2 / scale
            dot.appendBezierPathWithOvalInRect_(((pt[0] - r, pt[1] - r), (r * 2.0, r * 2.0)))
            dot.fill()

    @objc.python_method
    def _draw_label(self, corner, factor, scale):
        base = corner.get("radius")
        if base is None:
            return
        value = base * factor
        self.drawTextAtPoint(
            "%.0f" % value,
            corner["label_pos"],
            fontColor=_rgba(BLUE, 0.9),
        )

    # ------------------------------------------------------------------
    # apply
    # ------------------------------------------------------------------

    @objc.python_method
    def _apply(self, sender):
        self._refreshMasters()
        targets = self._targets()
        if not targets:
            _dbg("apply: no targets")
            return
        writes = 0
        layers_touched = 0
        for glyph, layer in targets:
            try:
                corners = self._visible_corners(layer)
            except Exception:
                _dbg("EXCEPTION")
                continue
            if not corners:
                continue
            changed = False
            # one undo step per layer — grouped, always closed (this is what
            # keeps Apply working after an undo: no dangling change group)
            try:
                layer.beginChanges()
            except Exception:
                pass
            try:
                for corner in corners:
                    factor = (
                        self.innerFactor
                        if corner["class"] == "counter"
                        else self.outerFactor
                    )
                    positions = cornerfit.transformed_positions(
                        layer.paths[corner["path_index"]], corner, factor
                    )
                    nodes = layer.paths[corner["path_index"]].nodes
                    for idx, (x, y) in positions.items():
                        nodes[idx].position = (x, y)
                        writes += 1
                    changed = changed or bool(positions)
            except Exception:
                _dbg("EXCEPTION")
            finally:
                try:
                    layer.endChanges()
                except Exception:
                    _dbg("EXCEPTION")
            layers_touched += 1 if changed else 0
        _dbg("apply: %d node writes across %d layers (targets=%d)" % (writes, layers_touched, len(targets)))
        self._redraw()

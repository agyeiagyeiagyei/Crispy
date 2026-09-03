# -*- coding: utf-8 -*-
"""Width Matcher — Glyphs 3 Reporter plugin.

Create a new master whose advance widths match another master's, by hand:

- Pick a REFERENCE master in the panel.
- Axis sliders define a working instance (kept in the font as the
  "Width Matcher Preview" instance — the same object Glyphs would
  interpolate for the Preview area, so what you see is what you get).
  Sliders span from the master minimum up to 3x the master maximum,
  so instances can extrapolate past the top of the design space.
- The panel shows an overlay preview of the current glyph — reference
  master (gray) vs. generated instance (blue), centered on the
  reference's ink — with markers at both advance boxes, plus numeric
  advance AND ink (outline extent) readouts. The ink delta is the
  matching target: sidebearings come from the reference.
- "Save as Master" interpolates the working instance and appends it to
  the font's masters, copying every glyph's interpolated layer across
  and setting each layer's sidebearings to the reference master's
  (LSB/RSB; empty glyphs take the reference advance verbatim).

Matching itself is manual: nudge the sliders until the ink delta reads
zero.
Width/outline data comes from `instance.interpolatedFont` (Glyphs' own
engine, brace layers and extrapolation included).

NOTE on regen triggering: the original design debounced regeneration
through NSTimer, but in this Glyphs build the timer callback never
fired (debug log: hundreds of "regen scheduled", zero "regen timer
fired"). Regeneration is therefore synchronous, throttled to at most
one run per 0.5 s during slider drags, with foreground() catching any
trailing dirty state once the drag settles.
"""

from __future__ import division, print_function, unicode_literals

import copy as _copy
import time
import traceback

import objc
from AppKit import NSApp, NSBezierPath, NSColor, NSImage, NSImageView, NSTimer
from GlyphsApp import *
from GlyphsApp.plugins import *

try:
    from vanilla import (
        Button,
        EditText,
        FloatingWindow,
        Group,
        PopUpButton,
        Slider,
        TextBox,
    )
except ImportError:  # vanilla ships with Glyphs; guard for dev linting
    FloatingWindow = None


# Spacing contracts for the saved master. Mode 0 is the original
# behaviour; the rest pin the ADVANCE and let the sidebearings land
# wherever the generated ink requires — same width, different spacing.
SPACING_REF_SB = 0
SPACING_ADV_PROPORTIONAL = 1
SPACING_ADV_CENTRED = 2
SPACING_ADV_KEEP_LSB = 3
SPACING_MODES = [
    "Reference sidebearings",
    "Reference advance - proportional",
    "Reference advance - centred",
    "Reference advance - keep LSB",
]

REF_GRAY = (0.65, 0.65, 0.65)
GEN_BLUE = (0.10, 0.45, 0.95)
OK_GREEN = (0.15, 0.60, 0.25)
AMBER = (0.95, 0.62, 0.10)

WORKING_INSTANCE_NAME = "Width Matcher Preview"

# Synchronous regen is throttled: never more than one run per this many
# seconds during a slider drag; a trailing dirty flag is picked up by
# foreground() once the user pauses for REGEN_IDLE seconds.
REGEN_THROTTLE = 0.5
REGEN_IDLE = 0.35

# Panel preview size (points).
PREVIEW_W = 296
PREVIEW_H = 220

_DEBUG_LOG = "/tmp/widthmatcher-debug.log"


def _dbgexc(prefix=""):
    """Log the CURRENT exception with its traceback.

    Bare ``_dbg("EXCEPTION")`` records that something failed but not what,
    which is useless when the failure is a panel that silently never opens.
    """
    try:
        _dbg("%s%s" % (prefix, traceback.format_exc()))
    except Exception:
        pass


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


class WidthMatcher(ReporterPlugin):
    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({"en": "Width Matcher"})
        self.keyboardShortcut = None
        self.referenceMasterId = None
        self.axisValues = []               # one float per font axis
        self._panel = None
        self._panelFont = None             # font the panel rows were built for
        self._previewView = None           # NSImageView inside the panel
        self._lastLayer = None
        self._previewGlyphName = None
        self._active = True
        self._widthCache = {}              # glyphName -> generated advance width
        self._interpFont = None            # last interpolated font (outline source)
        self._interpMasterId = None
        self._dirty = False                # axis values changed since last regen
        self._lastChangeAt = 0.0
        self._lastRegenAt = 0.0
        self._axisRows = []                # [(label, slider, field), ...]
        self._masterItems = []             # popup titles, index-aligned w/ masters
        self._masterName = None            # last used new-master name (persists)
        self._spacingMode = SPACING_REF_SB  # how the saved master gets spaced
        self._advOffset = 0.0              # units added to the target advance
        self._panelClosedByUser = False    # red X kills the vanilla window
        self._loggedForeground = False      # one-shot foreground trace

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
        """Same contract as CornerRadii: foreground() fires only while
        View → Width Matcher is enabled, so the panel shows when those
        calls are recent and hides ~1.5 s after they stop."""
        try:
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.75, self, objc.selector(self._panelHeartbeat_), None, True
            )
        except Exception:
            _dbg("EXCEPTION")

    # NOTE: NOT @objc.python_method — NSTimer needs this as a real ObjC
    # selector. The trailing underscore gives it the required single colon.
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
    def _nswindow(self):
        """The panel's real NSWindow (see CornerRadii: vanilla forwards
        isVisible but not orderOut_/makeKeyAndOrderFront_)."""
        if self._panel is None:
            return None
        return self._panel.getNSWindow()

    @objc.python_method
    def _panelClosed(self, sender):
        """Red X = toggle the reporter off via its own View menu item,
        exactly like CornerRadii — a plain close would be re-shown by the
        next foreground() draw. The vanilla window is dead after a close,
        so flag it: the next foreground() rebuilds the panel from scratch
        (state lives on self, not in the window)."""
        self._panelClosedByUser = True
        def find_item(menu, depth=0):
            for item in menu.itemArray():
                if item.title() in (self.menuName, "Show " + self.menuName) \
                        and item.action():
                    return item
                sub = item.submenu()
                if sub is not None and depth < 3:
                    found = find_item(sub, depth + 1)
                    if found is not None:
                        return found
            return None

        try:
            main = NSApp.mainMenu()
            main.update()
            item = find_item(main)
            if item is not None:
                NSApp.sendAction_to_from_(item.action(), item.target(), item)
        except Exception:
            _dbg("EXCEPTION")

    @objc.python_method
    def activate(self):
        """Reporter toggled ON (View menu) — set active state only.
        Do NOT show the panel here: Glyphs calls activate() on ALL reporter
        plugins at app launch, which would open every panel on startup.
        foreground() shows the panel only when the View toggle is on."""
        _dbg("activate() called")
        self._active = True
        if FloatingWindow is None:
            return
        if self._panel is None:
            self._build_panel()
        self._redraw()

    @objc.python_method
    def deactivate(self):
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
    # font / layer resolution
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
        return None

    @objc.python_method
    def _masterAxes(self, master):
        """Axis coordinates of a master as a plain list of floats."""
        try:
            return [float(v) for v in master.axes]
        except Exception:
            pass
        try:
            return [float(v) for v in master.axesValues()]
        except Exception:
            _dbg("EXCEPTION")
        return []

    @objc.python_method
    def _referenceMaster(self, font):
        if self.referenceMasterId is not None:
            for m in font.masters:
                if m.id == self.referenceMasterId:
                    return m
        try:
            m = font.selectedFontMaster
            if m is not None:
                self.referenceMasterId = m.id
                return m
        except Exception:
            pass
        if len(font.masters):
            self.referenceMasterId = font.masters[0].id
            return font.masters[0]
        return None

    # ------------------------------------------------------------------
    # working instance + interpolation
    # ------------------------------------------------------------------

    @objc.python_method
    def _workingInstance(self, font):
        """The preview instance, kept in font.instances so the user sees
        it in Font Info and Glyphs' own interpolation applies. Created
        once per font, reused across slider moves."""
        for inst in font.instances:
            try:
                if inst.name == WORKING_INSTANCE_NAME:
                    return inst
            except Exception:
                pass
        try:
            inst = GSInstance()
            inst.name = WORKING_INSTANCE_NAME
            try:
                inst.active = True
            except Exception:
                pass
            font.instances.append(inst)
            _dbg("working instance created")
            return inst
        except Exception:
            _dbg("EXCEPTION")
        return None

    @objc.python_method
    def _applyAxisValues(self, inst):
        try:
            inst.axes = list(self.axisValues)
            readback = [float(v) for v in inst.axes]
            if readback != list(self.axisValues):
                _dbg("axes set drifted: wanted %r got %r"
                     % (list(self.axisValues), readback))
        except Exception:
            _dbg("EXCEPTION")

    @objc.python_method
    def _requestRegen(self):
        """Mark dirty and run a synchronous regen unless one happened
        very recently — during a continuous slider drag this yields one
        interpolation per REGEN_THROTTLE seconds; foreground() catches
        the trailing dirty state once the drag pauses."""
        self._dirty = True
        self._lastChangeAt = time.time()
        if time.time() - self._lastRegenAt >= REGEN_THROTTLE:
            self._runRegen()

    @objc.python_method
    def _runRegen(self):
        self._dirty = False
        self._lastRegenAt = time.time()
        self._regenWidths()
        self._updatePreview()

    @objc.python_method
    def _regenWidths(self):
        """Re-interpolate the working instance and cache per-glyph
        advance widths. Keeps the interpolated font around as the
        outline source for the panel preview."""
        font = self._currentFont()
        if font is None:
            _dbg("regen: no current font")
            return
        inst = self._workingInstance(font)
        if inst is None:
            _dbg("regen: no working instance")
            return
        self._applyAxisValues(inst)
        t0 = time.time()
        try:
            interp = inst.interpolatedFont
        except Exception:
            _dbg("EXCEPTION")
            return
        if interp is None or not len(interp.masters):
            _dbg("regen: interpolatedFont returned no masters")
            return
        mid = interp.masters[0].id
        cache = {}
        for g in interp.glyphs:
            try:
                layer = g.layers[mid]
                if layer is None and len(g.layers):
                    layer = g.layers[0]
                if layer is not None:
                    cache[g.name] = float(layer.width)
            except Exception:
                _dbg("EXCEPTION")
        self._widthCache = cache
        self._interpFont = interp
        self._interpMasterId = mid
        _dbg("regen: %d widths in %.2fs" % (len(cache), time.time() - t0))

    @objc.python_method
    def _interpLayer(self, glyphName):
        """The generated instance's layer for a glyph, or None."""
        if self._interpFont is None or self._interpMasterId is None:
            return None
        try:
            g = self._interpFont.glyphs[glyphName]
            if g is None:
                return None
            layer = g.layers[self._interpMasterId]
            if layer is None and len(g.layers):
                layer = g.layers[0]
            return layer
        except Exception:
            _dbg("EXCEPTION")
        return None

    # ------------------------------------------------------------------
    # panel
    # ------------------------------------------------------------------

    @objc.python_method
    def _build_panel(self):
        w = FloatingWindow((320, 120), "Width Matcher", closable=True)
        self._panel = w
        # The red X means "turn the reporter off", not "hide the panel".
        w.bind("close", self._panelClosed)
        y = 12
        w.refLabel = TextBox((12, y, 70, 20), "Reference:")
        w.refPop = PopUpButton((82, y, 226, 22), [""],
                               callback=self._referenceChanged)
        y += 30
        self._axesY = y
        _dbg("panel: building rows")
        try:
            self._syncPanelToFont(self._currentFont())
        except Exception:
            # A failure building the rows must NOT stop w.open() — otherwise
            # the reporter has no window at all and no way back, which reads
            # to the user as "nothing happens when I turn it on".
            _dbgexc("panel: row build FAILED: ")
        w.open()
        _dbg("panel: opened")
        ns = self._nswindow()
        # Keep the window out of macOS session restoration.
        ns.setRestorable_(False)
        ns.disableSnapshotRestoration()
        # Build hidden, per start()'s contract.
        ns.orderOut_(None)

    @objc.python_method
    def _syncPanelToFont(self, font):
        """(Re)build the master popup, one slider row per font axis, the
        preview, and the readout/action block. Called on font change."""
        if self._panel is None:
            return
        w = self._panel
        # drop previous axis rows and bottom block
        for i, (label, slider, field) in enumerate(self._axisRows):
            for ctrl in (label, slider, field):
                try:
                    ctrl.getNSView().removeFromSuperview()
                except Exception:
                    pass
            # vanilla refuses setattr over an existing attribute
            # ("can't replace vanilla attribute") — delete them too
            for attr in ("axisLabel_%d" % i, "axisSlider_%d" % i,
                         "axisField_%d" % i):
                try:
                    delattr(w, attr)
                except Exception:
                    pass
        self._axisRows = []
        if self._previewView is not None:
            try:
                self._previewView.removeFromSuperview()
            except Exception:
                pass
            self._previewView = None
        for attr in ("previewBox", "readoutAdv", "readoutInk", "readoutPlan",
                     "spacingLabel", "spacingPop", "offsetLabel", "offsetField",
                     "offsetHint", "refEcho", "nameLabel",
                     "nameField", "saveButton", "statusLine"):
            if hasattr(w, attr):
                try:
                    getattr(w, attr).getNSView().removeFromSuperview()
                except Exception:
                    pass
                delattr(w, attr)
        if font is None:
            return

        # reference master popup
        self._masterItems = [m.name for m in font.masters]
        try:
            w.refPop.setItems(self._masterItems)
        except Exception:
            _dbg("EXCEPTION")
        ref = self._referenceMaster(font)
        if ref is not None:
            try:
                w.refPop.set(self._masterItems.index(ref.name))
            except Exception:
                pass

        # axis values default to the reference master's coordinates
        n_axes = len(font.axes)
        if len(self.axisValues) != n_axes:
            self.axisValues = (
                self._masterAxes(ref)[:n_axes] if ref is not None else [0.0] * n_axes
            )

        y = self._axesY
        for i, axis in enumerate(font.axes):
            values = [self._masterAxes(m)[i] for m in font.masters
                      if len(self._masterAxes(m)) > i]
            lo = min(values) if values else 0.0
            hi = max(values) if values else 100.0
            # Extrapolation: slider covers the master minimum up to
            # 3x the master maximum, so instances can extrapolate
            # past the top of the design space.
            hi = max(hi * 3.0, lo + 1.0)
            label = TextBox((12, y + 2, 100, 18), str(axis.name), sizeStyle="small")
            slider = Slider((116, y, 116, 20),
                            minValue=lo, maxValue=hi,
                            value=self.axisValues[i],
                            callback=self._sliderChanged)
            field = EditText((240, y, 68, 22), "%g" % self.axisValues[i],
                             callback=self._axisFieldChanged)
            setattr(w, "axisLabel_%d" % i, label)
            setattr(w, "axisSlider_%d" % i, slider)
            setattr(w, "axisField_%d" % i, field)
            self._axisRows.append((label, slider, field))
            y += 26
        y += 6

        # preview: NSImageView filling a vanilla Group (the Group does
        # vanilla's coordinate handling; the image view fills it)
        w.previewBox = Group((12, y, PREVIEW_W, PREVIEW_H))
        try:
            view = NSImageView.alloc().initWithFrame_(
                ((0, 0), (PREVIEW_W, PREVIEW_H)))
            view.setImageFrameStyle_(0)      # no frame
            view.setImageAlignment_(5)       # center
            w.previewBox._nsObject.addSubview_(view)
            self._previewView = view
        except Exception:
            _dbg("EXCEPTION")
        y += PREVIEW_H + 6

        w.readoutAdv = TextBox((12, y, 296, 16), "", sizeStyle="small")
        y += 18
        w.readoutInk = TextBox((12, y, 296, 16), "", sizeStyle="small")
        y += 18
        # What the SAVED layer will actually carry — the live Adv readout
        # above reports the interpolated instance's own spacing, which the
        # save overwrites, so without this line the panel shows a number
        # you never get.
        w.readoutPlan = TextBox((12, y, 296, 16), "", sizeStyle="small")
        y += 22
        w.spacingLabel = TextBox((12, y, 70, 20), "Spacing:")
        w.spacingPop = PopUpButton((82, y, 226, 22), SPACING_MODES,
                                   callback=self._spacingChanged)
        try:
            w.spacingPop.set(self._spacingMode)
        except Exception:
            _dbg("EXCEPTION")
        y += 26
        w.offsetLabel = TextBox((12, y, 70, 20), "Adv offset:")
        w.offsetField = EditText((82, y, 70, 22), "%g" % self._advOffset,
                                 callback=self._offsetChanged)
        w.offsetHint = TextBox((160, y + 4, 148, 16), "units, advance modes",
                               sizeStyle="small")
        y += 30
        w.nameLabel = TextBox((12, y, 70, 20), "New name:")
        default_name = self._masterName or (
            "%s matched" % ref.name if ref is not None else "Matched")
        w.nameField = EditText((82, y, 226, 22), default_name)
        y += 30
        # Spell out where the spacing comes from: the popup is scrolled out
        # of sight by the time you press Save, and picking up the wrong
        # master's sidebearings is invisible until you inspect the result.
        w.refEcho = TextBox((12, y, 296, 16),
                            "spacing from: %s" % (ref.name if ref is not None else "-"),
                            sizeStyle="small")
        y += 20
        w.saveButton = Button((12, y, 140, 26), "Save as Master",
                              callback=self._saveAsMaster)
        w.statusLine = TextBox((160, y + 5, 148, 16), "", sizeStyle="small")
        y += 36
        try:
            w.resize(320, y)
        except Exception:
            _dbg("EXCEPTION")  # resize failing leaves controls unreachable
        self._requestRegen()

    # ------------------------------------------------------------------
    # panel callbacks
    # ------------------------------------------------------------------

    @objc.python_method
    def _referenceChanged(self, sender):
        font = self._currentFont()
        if font is None:
            return
        sel = sender.get()
        # vanilla's PopUpButton.get() is the title in some builds and the
        # index in others — accept both instead of failing silently.
        if isinstance(sel, (int, float)):
            idx = int(sel)
        else:
            try:
                idx = self._masterItems.index(sel)
            except ValueError:
                idx = 0
        if 0 <= idx < len(font.masters):
            self.referenceMasterId = font.masters[idx].id
        self._updatePreview()

    @objc.python_method
    def _spacingChanged(self, sender):
        try:
            self._spacingMode = int(sender.get())
        except Exception:
            self._spacingMode = SPACING_REF_SB
        _dbg("spacing mode -> %d" % self._spacingMode)
        self._redraw()

    @objc.python_method
    def _offsetChanged(self, sender):
        try:
            self._advOffset = float((sender.get() or "").strip() or 0)
        except (TypeError, ValueError):
            self._advOffset = 0.0   # keep typing usable; bad text reads as 0
        self._redraw()

    @objc.python_method
    def _rowIndex(self, sender, column):
        for i, row in enumerate(self._axisRows):
            if row[column] is sender:
                return i
        return None

    @objc.python_method
    def _sliderChanged(self, sender):
        i = self._rowIndex(sender, 1)
        if i is None:
            return
        self.axisValues[i] = float(sender.get())
        try:
            self._axisRows[i][2].set("%g" % self.axisValues[i])
        except Exception:
            pass
        self._requestRegen()

    @objc.python_method
    def _axisFieldChanged(self, sender):
        i = self._rowIndex(sender, 2)
        if i is None:
            return
        try:
            self.axisValues[i] = float(sender.get())
        except (TypeError, ValueError):
            return
        try:
            self._axisRows[i][1].set(self.axisValues[i])
        except Exception:
            pass
        self._runRegen()  # discrete edit — interpolate immediately

    @objc.python_method
    def _setStatus(self, text):
        if self._panel is not None and hasattr(self._panel, "statusLine"):
            try:
                self._panel.statusLine.set(text)
            except Exception:
                pass

    @objc.python_method
    def _redraw(self):
        try:
            self.controller.redraw()
        except Exception:
            try:
                Glyphs.redraw()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # save as master
    # ------------------------------------------------------------------

    @objc.python_method
    def _saveAsMaster(self, sender):
        """Glyphs' 'Instance as Master', driven by the working instance:
        interpolate, append the master, copy each glyph's layer over."""
        font = self._currentFont()
        if font is None:
            self._setStatus("no font")
            return
        name = "Matched"
        try:
            name = self._panel.nameField.get().strip() or name
        except Exception:
            pass
        self._masterName = name  # keep it across the post-save rebuild
        existing = [m.name for m in font.masters]
        if name in existing:
            self._setStatus("name in use")
            _dbg("save: master name %r already exists" % name)
            return
        inst = self._workingInstance(font)
        if inst is None:
            self._setStatus("no instance")
            return
        ref = self._referenceMaster(font)
        # Cross-check against what the popup is actually showing. The id can
        # point at a master the user never chose — _referenceMaster falls back
        # to font.selectedFontMaster (whatever is active in the Edit view)
        # whenever no explicit choice has been made.
        try:
            shown = self._panel.refPop.getItem() if hasattr(self._panel, "refPop") else None
        except Exception:
            shown = None
        if shown and ref is not None and shown != ref.name:
            live = [m for m in font.masters if m.name == shown]
            _dbg("save: popup shows %r but reference resolved to %r — "
                 "using the popup" % (shown, ref.name))
            if live:
                ref = live[0]
                self.referenceMasterId = ref.id
        _dbg("save: reference master %r (%s); axisValues=%r; spacing mode %d"
             % (None if ref is None else ref.name,
                None if ref is None else ref.id,
                list(self.axisValues), self._spacingMode))
        self._applyAxisValues(inst)
        savedMasterId = None
        savedPlan = {}
        try:
            font.disableUpdateInterface()
        except Exception:
            pass
        try:
            interp = inst.interpolatedFont
            if interp is None or not len(interp.masters):
                self._setStatus("interpolation failed")
                _dbg("save: interpolatedFont returned no masters")
                return
            newMaster = self._detach(interp.masters[0])
            newMaster.name = name
            font.masters.append(newMaster)
            newMaster = font.masters[-1]
            savedMasterId = newMaster.id
            # The interpolated master does NOT reliably carry the
            # instance's axis coordinates — set them explicitly so the
            # new master sits where the sliders put it.
            try:
                newMaster.axes = list(self.axisValues)
                readback = [float(v) for v in newMaster.axes]
                if readback != list(self.axisValues):
                    _dbg("save: master axes drifted: wanted %r got %r"
                         % (list(self.axisValues), readback))
            except Exception:
                _dbg("EXCEPTION")
            copied = 0
            sb_mismatch = 0
            for g in font.glyphs:
                try:
                    ig = interp.glyphs[g.name]
                    if ig is None or not len(ig.layers):
                        continue
                    newLayer = self._detach(ig.layers[0])
                    # Re-key: the copy still identifies as the interpolated
                    # font's master, so Glyphs would file it under the wrong
                    # id and the Edit view would show an empty master.
                    try:
                        newLayer.layerId = newMaster.id
                        newLayer.associatedMasterId = newMaster.id
                    except Exception:
                        _dbg("EXCEPTION")
                    g.layers[newMaster.id] = newLayer
                    copied += 1
                    # The point of the tool: the new master's spacing is
                    # derived from the REFERENCE master, per the chosen
                    # mode — either its sidebearings verbatim, or its
                    # advance with the sidebearings recomputed to fit.
                    tgt = g.layers[newMaster.id]
                    refLayer = g.layers[ref.id] if ref is not None else None
                    if refLayer is None:
                        continue
                    inkRect = self._inkRect(tgt)
                    if inkRect is None:
                        # empty glyph (space etc.): no ink to place,
                        # just take the reference advance
                        tgt.width = self._emptyAdvance(refLayer)
                        continue
                    plan = self._targetSpacing(refLayer, inkRect[2] - inkRect[0])
                    if plan is None:
                        continue
                    wantLSB, wantRSB, _wantAdv = plan
                    # LSB first, then RSB: whether the LSB setter shifts
                    # outlines (RSB kept) or keeps outlines (RSB floats),
                    # the final pair is correct.
                    tgt.LSB = wantLSB
                    tgt.RSB = wantRSB
                    savedPlan[g.name] = (wantLSB, wantRSB)
                    if abs(float(tgt.LSB) - wantLSB) > 0.01 \
                            or abs(float(tgt.RSB) - wantRSB) > 0.01:
                        sb_mismatch += 1
                        if sb_mismatch == 1:
                            _dbg("save: sidebearing readback drift, "
                                 "first on %s (want %.1f/%.1f got %.1f/%.1f)"
                                 % (g.name, wantLSB, wantRSB,
                                    float(tgt.LSB), float(tgt.RSB)))
                except Exception:
                    _dbg("EXCEPTION")
            # Prove the layers actually landed on THIS master rather than
            # trusting the assignment — an empty master is the failure this
            # tool must never report as success.
            verified = 0
            for g in font.glyphs:
                try:
                    L = g.layers[newMaster.id]
                    if L is not None and str(getattr(L, "layerId", "")) == str(newMaster.id):
                        verified += 1
                except Exception:
                    pass
            status = "saved (%d glyphs)" % copied
            if verified != copied:
                status += " — ONLY %d landed" % verified
            if sb_mismatch:
                status += " — %d sb drift" % sb_mismatch
            self._setStatus(status)
            _dbg("save: master %r (%s) with %d glyph layers (%d verified), "
                 "%d sb mismatches"
                 % (name, newMaster.id, copied, verified, sb_mismatch))
        except Exception:
            _dbg("EXCEPTION")
            self._setStatus("error — see log")
        finally:
            try:
                font.enableUpdateInterface()
            except Exception:
                pass
        # Re-read once the interface is live again. The in-loop check runs
        # while updates are suppressed; Glyphs re-applies metrics keys when
        # they resume, and most of this font's glyphs are keyed off another
        # (=H, =O, =H*1.5), so a sidebearing that verified a moment ago can
        # still be rewritten underneath us.
        self._auditSavedSpacing(font, savedMasterId, savedPlan)
        self._syncPanelToFont(font)
        self._redraw()

    @objc.python_method
    def _auditSavedSpacing(self, font, masterId, plan):
        """Log every glyph whose sidebearings no longer match what was set."""
        if not masterId or not plan:
            return
        drifted = []
        for name, (wantLSB, wantRSB) in plan.items():
            try:
                g = font.glyphs[name]
                L = g.layers[masterId] if g is not None else None
                if L is None:
                    continue
                gotLSB, gotRSB = float(L.LSB), float(L.RSB)
                if abs(gotLSB - wantLSB) > 0.01 or abs(gotRSB - wantRSB) > 0.01:
                    drifted.append((name, wantLSB, wantRSB, gotLSB, gotRSB,
                                    getattr(g, "leftMetricsKey", None),
                                    getattr(g, "rightMetricsKey", None)))
            except Exception:
                continue
        if not drifted:
            _dbg("audit: all %d glyphs held their spacing after update" % len(plan))
            return
        _dbg("audit: %d of %d glyphs DRIFTED after enableUpdateInterface"
             % (len(drifted), len(plan)))
        for row in drifted[:20]:
            _dbg("   %-12s want %8.1f/%-8.1f got %8.1f/%-8.1f  keys=%s/%s" % row)
        try:
            self._setStatus("saved — %d drifted after update" % len(drifted))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # preview rendering
    # ------------------------------------------------------------------

    @objc.python_method
    def _pathRect(self, path):
        """(minx, miny, maxx, maxy) for an NSBezierPath, or None."""
        if path is None:
            return None
        try:
            b = path.controlPointBounds()
            if b.size.width == 0 and b.size.height == 0:
                return None
            return (b.origin.x, b.origin.y,
                    b.origin.x + b.size.width, b.origin.y + b.size.height)
        except Exception:
            return None

    @objc.python_method
    def _detach(self, obj):
        """A standalone copy of a master/layer from the interpolated font.

        ``interpolatedFont``'s masters and layers belong to THAT font. Handing
        them straight to the real font leaves it holding objects owned by a
        temporary: the next regen replaces ``_interpFont``, the interpolated
        font is released, and the saved master loses every layer — it appears
        in the master list with no glyphs at all. Copying first makes the real
        font the owner, so the master survives.
        """
        for attempt in (lambda: obj.copy(), lambda: _copy.copy(obj)):
            try:
                dup = attempt()
            except Exception:
                continue
            if dup is not None:
                return dup
        _dbg("detach: could not copy %r — falling back to the original" % obj)
        return obj

    @objc.python_method
    def _targetSpacing(self, refLayer, genInkW):
        """(lsb, rsb, advance) the saved layer should end up with.

        ``SPACING_REF_SB`` pastes the reference's sidebearings, so the
        advance only matches when the ink does — that is the original
        contract, and why the ink delta had to be driven to zero.

        Every other mode pins the advance to the reference's (plus
        ``_advOffset``) and derives the sidebearings from whatever ink the
        generated layer actually has. The spacing values then differ from
        the reference's by design: the slack left over after the ink is
        distributed, either in the reference's own LSB:RSB proportion,
        evenly, or entirely onto the right.
        """
        if refLayer is None:
            return None
        refLSB, refRSB = float(refLayer.LSB), float(refLayer.RSB)
        refAdv = float(refLayer.width)
        if self._spacingMode == SPACING_REF_SB:
            return (refLSB, refRSB, refLSB + genInkW + refRSB)
        targetAdv = refAdv + self._advOffset
        slack = targetAdv - genInkW
        if self._spacingMode == SPACING_ADV_PROPORTIONAL:
            total = refLSB + refRSB
            # A zero total (full-bleed glyph) has no ratio to preserve —
            # fall back to an even split rather than dividing by zero.
            lsb = slack * (refLSB / total) if abs(total) > 1e-6 else slack / 2.0
        elif self._spacingMode == SPACING_ADV_CENTRED:
            lsb = slack / 2.0
        else:
            lsb = refLSB
        return (lsb, slack - lsb, targetAdv)

    @objc.python_method
    def _emptyAdvance(self, refLayer):
        """Advance for a glyph with no ink (space etc.)."""
        adv = float(refLayer.width)
        return adv if self._spacingMode == SPACING_REF_SB else adv + self._advOffset

    @objc.python_method
    def _inkRect(self, layer):
        """(minx, miny, maxx, maxy) of a layer's drawn ink, or None for
        empty layers (e.g. space)."""
        if layer is None:
            return None
        try:
            b = layer.bounds
            if b.size.width == 0 and b.size.height == 0:
                return None
            return (float(b.origin.x), float(b.origin.y),
                    float(b.origin.x + b.size.width),
                    float(b.origin.y + b.size.height))
        except Exception:
            _dbg("EXCEPTION")
            return None

    @objc.python_method
    def _updatePreview(self):
        """Render reference vs. generated glyph into the panel's image
        view, plus advance-width markers; refresh the numeric readout."""
        if self._panel is None:
            return
        font = self._currentFont()
        glyph = self._currentGlyph()
        if font is None or glyph is None or self._previewView is None:
            return
        ref = self._referenceMaster(font)
        if ref is None:
            return
        try:
            refLayer = glyph.layers[ref.id]
        except Exception:
            refLayer = None
        genLayer = self._interpLayer(glyph.name)
        refW = float(refLayer.width) if refLayer is not None else None
        genW = self._widthCache.get(glyph.name)
        refInk = self._inkRect(refLayer)
        genInk = self._inkRect(genLayer)
        self._updateReadout(glyph.name, refW, genW, refInk, genInk, refLayer)

        W, H = PREVIEW_W, PREVIEW_H
        img = NSImage.alloc().initWithSize_((W, H))
        img.lockFocus()
        try:
            refPath = refLayer.bezierPath if refLayer is not None else None
            genPath = genLayer.bezierPath if genLayer is not None else None
            asc = float(ref.ascender)
            desc = float(ref.descender)

            from AppKit import NSAffineTransform

            # The generated glyph is drawn with its INK centered on the
            # reference's ink, not left-aligned at the origin — the user
            # matches outline extents (sidebearings are copied from the
            # reference at save time), so aligned outlines must read as
            # aligned in the overlay.
            genDx = 0.0
            if refInk is not None and genInk is not None:
                genDx = (refInk[0] + refInk[2]) / 2.0 \
                      - (genInk[0] + genInk[2]) / 2.0
            elif refW is not None and genW is not None:
                genDx = (refW - genW) / 2.0
            if genPath is not None and genDx:
                try:
                    sh = NSAffineTransform.transform()
                    sh.translateXBy_yBy_(genDx, 0)
                    genPath = sh.transformBezierPath_(genPath)
                except Exception:
                    _dbg("EXCEPTION")

            # union bounds: both outlines plus the full metric box
            # (width lines and asc/desc must fit even for empty glyphs)
            minx, miny, maxx, maxy = 0.0, desc, 0.0, asc
            for dx, wdt in ((0.0, refW), (genDx, genW)):
                if wdt is not None:
                    minx = min(minx, dx)
                    maxx = max(maxx, dx + wdt)
            for r in (self._pathRect(refPath), self._pathRect(genPath)):
                if r is None:
                    continue
                minx = min(minx, r[0])
                miny = min(miny, r[1])
                maxx = max(maxx, r[2])
                maxy = max(maxy, r[3])
            spanx = max(maxx - minx, 1.0)
            spany = max(maxy - miny, 1.0)
            scale = min(W / spanx, H / spany) * 0.9
            # center the union box in the view
            ox = (W - spanx * scale) / 2.0 - minx * scale
            oy = (H - spany * scale) / 2.0 - miny * scale

            t = NSAffineTransform.transform()
            t.translateXBy_yBy_(ox, oy)
            t.scaleBy_(scale)

            def xformed(path):
                if path is None:
                    return None
                try:
                    return t.transformBezierPath_(path)
                except Exception:
                    _dbg("EXCEPTION")
                    return None

            def vx(x):
                return x * scale + ox

            def vy(yv):
                return yv * scale + oy

            # metric lines: baseline + both edges of each advance box
            # (left edges matter now that the generated box is centered)
            line = NSBezierPath.bezierPath()
            line.setLineWidth_(0.5)
            _rgba((0.5, 0.5, 0.5), 0.35).set()
            line.moveToPoint_((vx(minx), vy(0)))
            line.lineToPoint_((vx(maxx), vy(0)))
            line.stroke()
            for dx, wdt, col in ((0.0, refW, REF_GRAY),
                                 (genDx, genW, GEN_BLUE)):
                if wdt is None:
                    continue
                for edge in (dx, dx + wdt):
                    marker = NSBezierPath.bezierPath()
                    marker.setLineWidth_(0.7)
                    _rgba(col, 0.55).set()
                    marker.moveToPoint_((vx(edge), vy(desc)))
                    marker.lineToPoint_((vx(edge), vy(asc)))
                    marker.stroke()

            rp = xformed(refPath)
            if rp is not None:
                _rgba(REF_GRAY, 0.30).set()
                rp.fill()
                _rgba(REF_GRAY, 0.75).set()
                rp.setLineWidth_(0.6)
                rp.stroke()
            gp = xformed(genPath)
            if gp is not None:
                _rgba(GEN_BLUE, 0.25).set()
                gp.fill()
                _rgba(GEN_BLUE, 0.85).set()
                gp.setLineWidth_(0.8)
                gp.stroke()
        except Exception:
            _dbg("EXCEPTION")
        finally:
            img.unlockFocus()
        try:
            self._previewView.setImage_(img)
        except Exception:
            _dbg("EXCEPTION")

    @objc.python_method
    def _updateReadout(self, glyphName, refW, genW, refInk, genInk,
                       refLayer=None):
        if self._panel is None or not hasattr(self._panel, "readoutAdv"):
            return
        if refW is None:
            adv = "%s — no layer in reference master" % glyphName
        elif genW is None:
            adv = "%s — Adv Ref %.0f · Gen …" % (glyphName, refW)
        else:
            adv = "%s — Adv Ref %.0f · Gen %.0f (Δ %+.0f)" % (
                glyphName, refW, genW, genW - refW)
        if refInk is None or genInk is None:
            ink = ""
        else:
            refInkW = refInk[2] - refInk[0]
            genInkW = genInk[2] - genInk[0]
            ink = "Ink Ref %.0f · Gen %.0f (Δ %+.0f)" % (
                refInkW, genInkW, genInkW - refInkW)
        # What Save as Master would actually produce. The Adv line above is
        # the interpolated instance's OWN spacing, which the save discards;
        # this is the number to trust.
        plan = None
        if refLayer is not None and genInk is not None:
            try:
                plan = self._targetSpacing(refLayer, genInk[2] - genInk[0])
            except Exception:
                _dbg("EXCEPTION")
        if plan is None:
            planTxt = ""
        else:
            lsb, rsb, advOut = plan
            planTxt = "Saved: LSB %.0f - RSB %.0f - Adv %.0f" % (lsb, rsb, advOut)
            if refW is not None:
                planTxt += " (%s %+.0f)" % ("Adv", advOut - refW)
        try:
            self._panel.readoutAdv.set(adv)
            self._panel.readoutInk.set(ink)
            if hasattr(self._panel, "readoutPlan"):
                self._panel.readoutPlan.set(planTxt)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # reporter entry point: bookkeeping only (no Edit-view drawing)
    # ------------------------------------------------------------------

    @objc.python_method
    def foreground(self, layer):
        """Glyphs 3 reporter draw entry (drawForegroundForLayer_* is the
        Glyphs 2 API). Nothing is drawn into the Edit view — the preview
        lives in the panel — but this is the reliable pulse for panel
        visibility, glyph tracking, and trailing regens.

        No `_active` gate: foreground() only fires while the View toggle
        is on anyway, and on builds that call deactivate() but never
        activate() such a gate would permanently brick the panel."""
        self._lastLayer = layer
        # The draw heartbeat IS the View-toggle signal (see CornerRadii).
        self._lastForegroundAt = time.time()
        if not self._loggedForeground:
            self._loggedForeground = True
            _ns0 = self._nswindow()
            _dbg("foreground: first call, panel=%s ns=%s visible=%s"
                 % (self._panel is not None,
                    _ns0 is not None,
                    "n/a" if _ns0 is None else _ns0.isVisible()))
        if self._panelClosedByUser:
            # the red-X close disposed the vanilla window — rebuild
            self._panelClosedByUser = False
            self._panel = None
            self._previewView = None
            self._build_panel()
        ns = self._nswindow()
        if ns is not None and not ns.isVisible():
            try:
                ns.makeKeyAndOrderFront_(None)
            except Exception:
                pass

        font = self._currentFont()
        # Rebuild on a master-count change too, not just a font change:
        # _masterItems maps popup index -> font.masters[index], so adding or
        # deleting a master while the panel is open silently shifts every
        # selection after it and the reference resolves to the wrong master.
        if font is not None and (font is not self._panelFont
                                 or len(font.masters) != len(self._masterItems)):
            self._panelFont = font
            self._syncPanelToFont(font)

        # trailing regen once a slider drag has settled
        if self._dirty \
                and time.time() - self._lastChangeAt > REGEN_IDLE \
                and time.time() - self._lastRegenAt >= REGEN_THROTTLE:
            self._runRegen()

        # re-render the preview when the glyph on screen changed
        try:
            glyph = layer.parent
            name = glyph.name if glyph is not None else None
        except Exception:
            name = None
        if name != self._previewGlyphName:
            self._previewGlyphName = name
            self._updatePreview()

    # Older Glyphs builds call the non-options variant.
    @objc.python_method
    def drawForegroundForLayer_(self, layer):
        self.foreground(layer)

    # ------------------------------------------------------------------
    # boilerplate
    # ------------------------------------------------------------------

    @objc.python_method
    def __file__(self):
        return __file__

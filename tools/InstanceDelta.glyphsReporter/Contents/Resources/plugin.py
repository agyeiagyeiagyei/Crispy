# -*- coding: utf-8 -*-
"""Instance Delta — Glyphs 3 Reporter plugin.

Draw one of the font's instances behind the glyph you are editing, and report
the difference between the two advance widths.

- Pick an INSTANCE in the floating panel. Its outlines come from Glyphs' own
  engine (``instance.interpolatedFont``), interpolated ONCE per selection and
  cached — ``background()`` runs for every glyph on screen at every redraw, so
  interpolating a whole font in there would make the Edit view unusable.
- Both outlines share the ORIGIN (x = 0), so the advance difference reads
  directly as the gap between the two advance markers on the right.
- The readout gives the active glyph's ``edit`` vs ``instance`` advance and
  the delta; the overlay itself is drawn for every glyph in the tab.

The instance list is the font's own ``GSInstance``s. Width Matcher's scratch
object is filtered out — it is a working instance that tool rewrites live, not
something to compare against.

Panel visibility follows the same contract as Width Matcher and CornerRadii:
this Glyphs build never calls ``activate()``, so the reporter's own draw
callback is the View-toggle signal — the panel is ordered front from there and
hidden by a heartbeat once the calls stop.
"""

from __future__ import division, print_function, unicode_literals

import time
import traceback

import objc
from AppKit import NSBezierPath, NSColor, NSTimer
from GlyphsApp import *
from GlyphsApp.plugins import *

try:
    from vanilla import Button, CheckBox, FloatingWindow, PopUpButton, TextBox
except ImportError:  # vanilla ships with Glyphs; guard for dev linting
    FloatingWindow = None


_DEBUG_LOG = "/tmp/instancedelta-debug.log"

# Width Matcher keeps a live scratch instance in the font; it is not a
# comparison target and listing it just invites picking it by accident.
EXCLUDED_INSTANCE_NAMES = ("Width Matcher Preview",)

INSTANCE_FILL = (0.85, 0.25, 0.55)   # the overlaid instance
EDIT_MARK = (0.55, 0.55, 0.55)       # the layer being edited
PANEL_W = 320

# Glyphs restores the View-menu toggle at launch and starts drawing straight
# away. That is not the user asking for the tool, so draw callbacks arriving
# within this many seconds of start() are treated as "restored", not "chosen".
LAUNCH_GRACE = 4.0
# How long without a draw callback before the reporter counts as switched off.
IDLE_OFF = 1.5


def _dbg(msg):
    try:
        with open(_DEBUG_LOG, "a") as f:
            f.write("%s\n" % msg)
    except Exception:
        pass


def _dbgexc(prefix=""):
    try:
        _dbg("%s%s" % (prefix, traceback.format_exc()))
    except Exception:
        pass


def _rgba(rgb, a):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], a)


class InstanceDelta(ReporterPlugin):

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({"en": "Instance Delta"})
        self.keyboardShortcut = None
        self.pickKey = None             # "master:<name>" or "instance:<name>"
        self._panel = None
        self._panelFont = None
        self._pickerItems = []          # popup titles, index-aligned with _entries
        self._entries = []              # [{kind, name, obj}] behind those titles
        self._sourceCounts = (-1, -1)   # (len(masters), len(instances)) at last sync
        self._interpFont = None         # cached interpolation, INSTANCES only
        self._interpMasterId = None
        self._interpFor = None          # which instance the cache belongs to
        self._lastForegroundAt = 0.0
        self._startedAt = 0.0
        # The tool is INERT until the user turns it on in this session: no
        # panel and no overlay. Nothing here is driven by the draw callback
        # merely firing, because Glyphs fires it for a toggle it restored.
        self._panelWanted = False
        self._wasIdle = True
        self._loggedDraw = False
        self._bgFired = False       # did background() ever fire in this build?
        self._showMarkers = True

    @objc.python_method
    def start(self):
        _dbg("start() called")
        self._lastForegroundAt = 0.0
        self._startedAt = time.time()
        # Deliberately NOT building the panel here. Building it at launch is
        # what put a window on screen before the user had asked for anything.
        self._startHeartbeat()

    # ------------------------------------------------------------------
    # panel plumbing
    # ------------------------------------------------------------------

    @objc.python_method
    def _startHeartbeat(self):
        try:
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.75, self, objc.selector(self._panelHeartbeat_), None, True
            )
        except Exception:
            _dbgexc("heartbeat: ")

    # NOT @objc.python_method — NSTimer needs a real ObjC selector, and the
    # trailing underscore supplies the single colon it expects.
    def _panelHeartbeat_(self, timer):
        try:
            idle = time.time() - self._lastForegroundAt > IDLE_OFF
            if idle and not self._wasIdle:
                # The reporter was just switched off. Drop the panel and force
                # one redraw so the last overlay we painted does not linger.
                self._wasIdle = True
                self._panelWanted = False
                _dbg("heartbeat: went idle -> panel hidden, overlay cleared")
                ns = self._nswindow()
                if ns is not None:
                    try:
                        ns.orderOut_(None)
                    except Exception:
                        pass
                self._redraw()
            elif not idle:
                self._wasIdle = False
        except Exception:
            pass

    @objc.python_method
    def _nswindow(self):
        if self._panel is None:
            return None
        try:
            return self._panel.getNSWindow()
        except Exception:
            return None

    @objc.python_method
    def _panelClosed(self, sender):
        # The red X means "I am done with this tool", not "reopen yourself on
        # the next redraw". Drop the window AND stop drawing the overlay;
        # re-selecting it in the View menu brings both back.
        _dbg("panel: closed by user")
        self._panelWanted = False
        self._panel = None
        self._redraw()

    @objc.python_method
    def _build_panel(self):
        w = FloatingWindow((PANEL_W, 120), "Instance Delta", closable=True)
        self._panel = w
        w.bind("close", self._panelClosed)
        _dbg("panel: building rows")
        try:
            self._syncPanelToFont(self._currentFont())
        except Exception:
            # Never let a row-build failure stop the window opening, or the
            # reporter has no UI at all and no way back.
            _dbgexc("panel: row build FAILED: ")
        w.open()
        _dbg("panel: opened")
        ns = self._nswindow()
        if ns is not None:
            try:
                # Keep the window out of macOS session restoration, or it
                # reappears at launch on its own — which is half of what we
                # are trying to stop.
                ns.setRestorable_(False)
                ns.disableSnapshotRestoration()
            except Exception:
                pass

    @objc.python_method
    def _syncPanelToFont(self, font):
        if self._panel is None:
            return
        w = self._panel
        for attr in ("instLabel", "instPop", "readout", "readoutAdv",
                     "markerCheck", "refreshButton", "statusLine"):
            if hasattr(w, attr):
                try:
                    getattr(w, attr).getNSView().removeFromSuperview()
                except Exception:
                    pass
                delattr(w, attr)   # vanilla refuses setattr over a live attribute
        if font is None:
            return

        # Masters first, then instances. A master needs no interpolation at
        # all — its layer is read straight off the glyph — so it is both the
        # cheaper comparison and the exact one, with no interpolation error.
        self._sourceCounts = (len(font.masters), len(font.instances))
        self._entries = [{"kind": "master", "name": str(m.name), "obj": m}
                         for m in font.masters]
        self._entries += [{"kind": "instance", "name": str(i.name), "obj": i}
                          for i in font.instances
                          if str(i.name) not in EXCLUDED_INSTANCE_NAMES]
        self._pickerItems = ["%s: %s" % (e["kind"].capitalize(), e["name"])
                             for e in self._entries]

        y = 12
        w.instLabel = TextBox((12, y, 62, 20), "Compare:")
        w.instPop = PopUpButton((78, y, PANEL_W - 90, 22),
                                self._pickerItems or ["(nothing to compare)"],
                                callback=self._pickChanged)
        cur = self._selectedEntry(font)
        if cur is not None:
            try:
                w.instPop.set(self._entries.index(cur))
            except Exception:
                pass
        y += 30
        w.readout = TextBox((12, y, PANEL_W - 24, 16), "", sizeStyle="small")
        y += 18
        w.readoutAdv = TextBox((12, y, PANEL_W - 24, 16), "", sizeStyle="small")
        y += 24
        w.markerCheck = CheckBox((12, y, 150, 20), "Advance markers",
                                 value=self._showMarkers,
                                 sizeStyle="small",
                                 callback=self._markersChanged)
        w.refreshButton = Button((PANEL_W - 100, y - 3, 88, 24), "Refresh",
                                 callback=self._refreshClicked)
        y += 28
        w.statusLine = TextBox((12, y, PANEL_W - 24, 16), "", sizeStyle="small")
        y += 24
        try:
            w.resize(PANEL_W, y)
        except Exception:
            _dbgexc("panel: resize failed: ")
        self._invalidate()

    # ------------------------------------------------------------------
    # callbacks
    # ------------------------------------------------------------------

    @objc.python_method
    def _pickChanged(self, sender):
        font = self._currentFont()
        if font is None:
            return
        sel = sender.get()
        # vanilla's PopUpButton.get() is the index in some builds and the
        # title in others — accept both instead of failing silently.
        if isinstance(sel, (int, float)):
            idx = int(sel)
        else:
            try:
                idx = self._pickerItems.index(sel)
            except ValueError:
                idx = 0
        if 0 <= idx < len(self._entries):
            e = self._entries[idx]
            self.pickKey = "%s:%s" % (e["kind"], e["name"])
            _dbg("compare -> %r" % self.pickKey)
        self._invalidate()

    @objc.python_method
    def _markersChanged(self, sender):
        try:
            self._showMarkers = bool(sender.get())
        except Exception:
            self._showMarkers = True
        self._redraw()

    @objc.python_method
    def _refreshClicked(self, sender):
        # Outlines change as you edit; the cache cannot see that, so this is
        # the explicit way to re-interpolate.
        self._invalidate()
        self._redraw()

    @objc.python_method
    def _invalidate(self):
        self._interpFont = None
        self._interpMasterId = None
        self._interpFor = None

    @objc.python_method
    def _redraw(self):
        try:
            self.controller.redraw()
        except Exception:
            try:
                Glyphs.redraw()
            except Exception:
                pass

    @objc.python_method
    def _setStatus(self, text):
        if self._panel is not None and hasattr(self._panel, "statusLine"):
            try:
                self._panel.statusLine.set(text)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # font / instance / interpolation
    # ------------------------------------------------------------------

    @objc.python_method
    def _currentFont(self):
        try:
            return Glyphs.font
        except Exception:
            return None

    @objc.python_method
    def _selectedEntry(self, font):
        """The chosen master or instance, resolved by key (not by index, which
        shifts whenever a master or instance is added or removed)."""
        if font is None or not self._entries:
            return None
        if self.pickKey is not None:
            for e in self._entries:
                if "%s:%s" % (e["kind"], e["name"]) == self.pickKey:
                    return e
        e = self._entries[0]
        self.pickKey = "%s:%s" % (e["kind"], e["name"])
        return e

    @objc.python_method
    def _interpolated(self, entry):
        """An instance's interpolated font, cached per instance.

        Only instances go through here. background()/foreground() run for every
        glyph on screen at every redraw, so interpolating there would make the
        Edit view unusable — the cache is rebuilt on selection change, font
        change, or an explicit Refresh.
        """
        key = "%s:%s" % (entry["kind"], entry["name"])
        if self._interpFont is not None and self._interpFor == key:
            return self._interpFont
        t0 = time.time()
        try:
            interp = entry["obj"].interpolatedFont
        except Exception:
            _dbgexc("interpolate: ")
            self._setStatus("interpolation failed — see log")
            return None
        if interp is None or not len(interp.masters):
            self._setStatus("interpolation returned nothing")
            return None
        self._interpFont = interp
        self._interpMasterId = interp.masters[0].id
        self._interpFor = key
        _dbg("interpolated %r in %.2fs" % (key, time.time() - t0))
        self._setStatus("%s — %d glyphs" % (entry["name"], len(interp.glyphs)))
        return interp

    @objc.python_method
    def _overlayLayer(self, font, glyphName):
        """The layer to draw behind/over the edited glyph.

        A MASTER is read straight off the glyph — exact, and free. An INSTANCE
        has to be interpolated first.
        """
        entry = self._selectedEntry(font)
        if entry is None:
            return None
        try:
            if entry["kind"] == "master":
                g = font.glyphs[glyphName]
                if g is None:
                    return None
                self._setStatus("%s (master)" % entry["name"])
                return g.layers[entry["obj"].id]
            interp = self._interpolated(entry)
            if interp is None:
                return None
            g = interp.glyphs[glyphName]
            if g is None:
                return None
            l = g.layers[self._interpMasterId]
            if l is None and len(g.layers):
                l = g.layers[0]
            return l
        except Exception:
            _dbgexc("overlayLayer: ")
            return None

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------

    @objc.python_method
    def _vline(self, x, y0, y1, rgb, alpha, width):
        try:
            p = NSBezierPath.bezierPath()
            p.moveToPoint_((x, y0))
            p.lineToPoint_((x, y1))
            p.setLineWidth_(width)
            _rgba(rgb, alpha).set()
            p.stroke()
        except Exception:
            pass

    @objc.python_method
    def _metricsSpan(self, layer):
        """A sensible vertical extent for the advance markers."""
        try:
            m = layer.master
            return (float(m.descender), float(m.ascender))
        except Exception:
            return (-300.0, 1600.0)

    @objc.python_method
    def _pulse(self, which, layer):
        """Panel lifecycle, run from whichever draw callback fires.

        This Glyphs build never calls activate(), so a draw callback is the
        only View-toggle signal there is. But the callback also fires for a
        toggle Glyphs merely RESTORED at launch, which is not the user asking
        for anything — so an off->on transition only counts once the launch
        grace has passed. Until the tool is wanted it stays completely inert:
        no window, no overlay.

        Returns the font to draw against, or None to draw nothing.
        """
        now = time.time()
        idle = now - self._lastForegroundAt
        self._lastForegroundAt = now
        if not self._loggedDraw:
            self._loggedDraw = True
            _dbg("%s: first call, %.1fs after start" % (which, now - self._startedAt))

        if idle > IDLE_OFF:                      # off -> on
            if now - self._startedAt > LAUNCH_GRACE:
                self._panelWanted = True
                _dbg("pulse: %s toggled on -> showing panel" % which)
            else:
                _dbg("pulse: %s active at launch -> staying inert" % which)
        self._wasIdle = False

        if not self._panelWanted:
            return None

        if self._panel is None and FloatingWindow is not None:
            self._build_panel()                  # built lazily, on demand
        ns = self._nswindow()
        if ns is not None and not ns.isVisible():
            try:
                ns.makeKeyAndOrderFront_(None)
            except Exception:
                pass

        font = self._currentFont()
        if font is None:
            return None
        # Rebuild when the master or instance count changes: _pickerItems maps
        # the popup index onto _entries, so adding or deleting a master OR an
        # instance while the panel is open would otherwise shift every
        # selection. Compare the RAW counts — _entries is filtered, so
        # comparing against its length would never match and would resync
        # (and re-interpolate) on every single draw.
        if (font is not self._panelFont
                or (len(font.masters), len(font.instances)) != self._sourceCounts):
            self._panelFont = font
            self._syncPanelToFont(font)
        return font

    @objc.python_method
    def _draw(self, layer):
        """The overlay itself: the chosen master/instance glyph, sharing the
        origin with the layer being edited, plus the two advance markers.

        Gated on _panelWanted so closing the panel stops the drawing too —
        an overlay with no window to explain or dismiss it is just litter.
        """
        if not self._panelWanted:
            return
        font = self._currentFont()
        if font is None:
            return
        try:
            glyph = layer.parent
            name = glyph.name if glyph is not None else None
        except Exception:
            name = None
        if name is None:
            return
        il = self._overlayLayer(font, name)
        if il is None:
            return

        try:
            path = None
            for attr in ("completeBezierPath", "bezierPath"):
                path = getattr(il, attr, None)
                if path is not None:
                    break
            if path is not None:
                _rgba(INSTANCE_FILL, 0.20).set()
                path.fill()
                _rgba(INSTANCE_FILL, 0.55).set()
                path.setLineWidth_(1.0)
                path.stroke()
        except Exception:
            _dbgexc("draw outline: ")

        try:
            editAdv = float(layer.width)
            instAdv = float(il.width)
        except Exception:
            return
        if self._showMarkers:
            y0, y1 = self._metricsSpan(layer)
            self._vline(0.0, y0, y1, EDIT_MARK, 0.45, 1.0)
            self._vline(editAdv, y0, y1, EDIT_MARK, 0.65, 1.0)
            self._vline(instAdv, y0, y1, INSTANCE_FILL, 0.80, 1.5)

        self._updateReadout(name, editAdv, instAdv)

    # --- draw callbacks -------------------------------------------------
    # Glyphs 3 documents both foreground() and background(), but this build
    # only dispatches foreground() — Width Matcher and CornerRadii both rely
    # on it, and a background()-only reporter is never called at all. So draw
    # BEHIND the glyph where that works, and fall back to drawing in front
    # where it does not, rather than silently rendering nothing.

    @objc.python_method
    def background(self, layer):
        self._bgFired = True
        if self._pulse("background", layer) is None:
            return
        self._draw(layer)

    @objc.python_method
    def foreground(self, layer):
        if self._pulse("foreground", layer) is None:
            return
        if not self._bgFired:
            self._draw(layer)

    # Older Glyphs builds call the non-options variants.
    @objc.python_method
    def drawBackgroundForLayer_(self, layer):
        self.background(layer)

    @objc.python_method
    def drawForegroundForLayer_(self, layer):
        self.foreground(layer)

    @objc.python_method
    def _updateReadout(self, glyphName, editAdv, instAdv):
        """Report for the ACTIVE glyph only — background() fires for every
        glyph in the tab, so writing on each call would make the panel
        flicker through the whole line."""
        font = self._currentFont()
        try:
            sel = font.selectedLayers
            active = sel[0].parent.name if sel else None
        except Exception:
            active = None
        if active is not None and active != glyphName:
            return
        if self._panel is None or not hasattr(self._panel, "readout"):
            return
        delta = instAdv - editAdv
        try:
            self._panel.readout.set(
                "%s — %s" % (glyphName, self.pickKey or "(nothing selected)"))
            self._panel.readoutAdv.set(
                "Adv edit %.0f - inst %.0f (delta %+.0f)" % (editAdv, instAdv, delta))
        except Exception:
            pass

    @objc.python_method
    def __file__(self):
        return __file__

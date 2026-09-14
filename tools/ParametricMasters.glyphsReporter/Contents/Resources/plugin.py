# -*- coding: utf-8 -*-
"""Parametric Masters — Glyphs 3 Reporter plugin.

Audits parametric-master consistency: masters that share the axis values
driving horizontal metrics should share horizontal metrics. Masters are
grouped by a pair of axes (default XTRA + XOPQ — the horizontal
transparent and opaque factors), and any glyph whose advance width, LSB,
or RSB differs between masters of the same group is flagged.

- "Group by" popup offers every pair of the font's axes, so other
  hypotheses (e.g. XTRA + YOPQ) can be checked too.
- Font-wide by default; "Current glyph only" narrows the audit to the
  Edit view's glyph. Live updates while you draw (UPDATEINTERFACE,
  throttled to one scan per second, trailing scan on redraw).
- Only groups of 2+ masters are audited. Consensus is the first member's
  metrics; deviations over 1 unit are flagged.

Draws nothing into the Edit view — the report lives in the floating panel.
"""

import time
import traceback

import objc
from AppKit import NSApp, NSTimer
from GlyphsApp import *
from GlyphsApp.plugins import *

try:
    from vanilla import (
        Button,
        CheckBox,
        FloatingWindow,
        List,
        PopUpButton,
        TextBox,
    )
except ImportError:  # vanilla ships with Glyphs; guard for dev linting
    FloatingWindow = None


TOLERANCE = 1.0        # units; deviations beyond this are flagged
SCAN_THROTTLE = 1.0    # min seconds between live scans
IDLE_OFF = 1.5         # seconds without foreground() => reporter toggled off

DEBUG = False  # flip to True for /tmp instrumentation while developing
_DEBUG_LOG = "/tmp/parametricmasters-debug.log"


def _dbg(msg):
    if not DEBUG:
        return
    try:
        with open(_DEBUG_LOG, "a") as f:
            f.write("%s\n" % msg)
    except Exception:
        pass


def _dbgexc(prefix=""):
    if not DEBUG:
        return
    try:
        _dbg("%s%s" % (prefix, traceback.format_exc()))
    except Exception:
        pass


# ----------------------------------------------------------------------
# audit logic (plain font/master/layer access, no UI)
# ----------------------------------------------------------------------

def _master_axes(master):
    """Axis coordinates of a master as a list of floats."""
    try:
        return [float(v) for v in master.axes]
    except Exception:
        pass
    try:
        return [float(v) for v in master.axesValues()]
    except Exception:
        return []


def group_masters(font, idx_a, idx_b):
    """{(valA, valB): [master, ...]} for the axis pair — 2+ members only."""
    groups = {}
    for m in font.masters:
        axes = _master_axes(m)
        if len(axes) <= max(idx_a, idx_b):
            continue
        key = (round(axes[idx_a], 2), round(axes[idx_b], 2))
        groups.setdefault(key, []).append(m)
    return {k: v for k, v in groups.items() if len(v) > 1}


def scan(font, groups, glyph_names):
    """One row per (glyph, group) whose members disagree on adv/LSB/RSB.

    Consensus is the first member's values; the row reports the largest
    absolute deviation among the other members.
    """
    rows = []
    for key, members in sorted(groups.items()):
        first_idx = list(font.masters).index(members[0])
        master_names = ", ".join(m.name for m in members)
        for name in glyph_names:
            g = font.glyphs[name]
            if g is None:
                continue
            vals = []
            for m in members:
                layer = g.layers[m.id]
                if layer is None:
                    continue
                try:
                    vals.append(
                        (float(layer.width), float(layer.LSB), float(layer.RSB))
                    )
                except Exception:
                    pass
            if len(vals) < 2:
                continue
            adv0, lsb0, rsb0 = vals[0]
            dadv = max(abs(v[0] - adv0) for v in vals[1:])
            dlsb = max(abs(v[1] - lsb0) for v in vals[1:])
            drsb = max(abs(v[2] - rsb0) for v in vals[1:])
            if max(dadv, dlsb, drsb) > TOLERANCE:
                rows.append({
                    "glyph": name,
                    "group": "%g · %g" % key,
                    "masters": master_names,
                    "dadv": "%.0f" % dadv,
                    "dlsb": "%.0f" % dlsb,
                    "drsb": "%.0f" % drsb,
                    "_masterIndex": first_idx,
                })
    return rows


class ParametricMasters(ReporterPlugin):

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({"en": "Parametric Masters"})
        self.keyboardShortcut = None
        self._panel = None
        self._panelFont = None
        self._lastLayer = None
        self._pairs = []                 # [(idxA, idxB, nameA, nameB)]
        self._pairItems = []             # popup titles, index-aligned
        self._pair = ("XTRA", "XOPQ")    # selected axis names
        self.currentGlyphOnly = False
        self.live = True
        self._dirty = False              # edits arrived since last scan
        self._lastScanAt = 0.0
        self._lastForegroundAt = 0.0
        self._currentGlyphName = None
        # View-toggle tracking (see _pollViewItem)
        self._viewItem = None
        self._userEnabled = False
        self._userClicked = False
        self._itemWasOn = False
        self._origItemTarget = None
        self._origItemAction = None
        self._lastUntoggleAt = 0.0

    @objc.python_method
    def start(self):
        self._lastForegroundAt = time.time()
        self._startHeartbeat()
        try:
            Glyphs.addCallback(self._updateInterface_, UPDATEINTERFACE)
        except Exception:
            _dbgexc("subscribe: ")

    # --- View-toggle tracking ------------------------------------------
    # Glyphs restores the View-menu toggle programmatically (at launch or
    # document open) and there is no reliable moment to catch it — so the
    # item's action is trampolined (_hookViewItem/_viewItemClicked_): a
    # real CLICK marks user intent; an on state with no click seen is the
    # restore and is switched back off (_toggleOffViaMenu, bypassing the
    # trampoline). Draw timing is never trusted either.

    @objc.python_method
    def _findViewItem(self):
        def find_item(menu, depth=0):
            for item in menu.itemArray():
                # Glyphs flips the title with the toggle: "Show X" when
                # off, "Hide X" when on — match both (and the bare name).
                if item.title() in ("Hide " + self.menuName,
                                    "Show " + self.menuName,
                                    self.menuName) \
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
            main.update()  # force dynamic (reporter) items to populate
            return find_item(main)
        except Exception:
            return None

    @objc.python_method
    def _pollViewItem(self):
        """Track the View-menu toggle, reading state() fresh (menu.update()
        forces validation first). The item's action is hooked with a
        trampoline (_viewItemClicked_), so a real click is distinguishable
        from Glyphs' session restore, which flips the toggle WITHOUT
        invoking the action: an on read with no click seen is the restore
        and is switched straight back off, whenever it lands."""
        item = self._viewItem or self._findViewItem()
        if item is None:
            if not getattr(self, "_notFoundLogged", False):
                self._notFoundLogged = True
                _dbg("poll: View item NOT FOUND")
            return
        self._viewItem = item
        self._hookViewItem(item)
        try:
            menu = item.menu()
            if menu is not None:
                menu.update()
        except Exception:
            pass
        on = bool(item.state())
        if on and not self._userClicked:
            self._toggleOffViaMenu()  # session restore, not a click
            return
        if not on:
            self._userEnabled = False
            if self._itemWasOn:
                self._toggledOff()
        else:
            self._userEnabled = True
        self._itemWasOn = on

    @objc.python_method
    def _hookViewItem(self, item):
        """Point the View item at the trampoline, keeping the original
        target/action for forwarding (and for programmatic toggles, which
        must NOT count as clicks)."""
        try:
            if item.target() is self:
                return  # already hooked
            self._origItemTarget = item.target()
            self._origItemAction = item.action()
            item.setTarget_(self)
            item.setAction_(objc.selector(self._viewItemClicked_))
            _dbg("hook: View item action trampolined")
        except Exception:
            _dbgexc("hook: ")

    # NOT @objc.python_method — the menu item needs a real ObjC selector.
    def _viewItemClicked_(self, sender):
        # A REAL click (the restore never invokes the action): the user
        # owns the toggle from here on. Forward to Glyphs' own handler.
        _dbg("click: View item clicked")
        self._userClicked = True
        try:
            NSApp.sendAction_to_from_(self._origItemAction,
                                      self._origItemTarget, sender)
        except Exception:
            _dbgexc("click: ")

    @objc.python_method
    def _toggledOff(self):
        """The reporter was switched off (seen by _pollViewItem)."""
        ns = self._nswindow()
        if ns is not None and ns.isVisible():
            ns.orderOut_(None)

    @objc.python_method
    def _toggleOffViaMenu(self):
        """Switch the reporter OFF programmatically, throttled to one send
        a second. Sends the item's ORIGINAL action (saved when the
        trampoline was installed): routing through the current action
        would trip _viewItemClicked_ and count our own untoggle as a user
        click."""
        now = time.time()
        if now - self._lastUntoggleAt < 1.0:
            return
        item = self._viewItem or self._findViewItem()
        if item is None:
            _dbg("untoggle: no View item")
            return
        try:
            menu = item.menu()
            if menu is not None:
                menu.update()
        except Exception:
            pass
        if not item.state():
            return
        hooked = item.target() is self
        action = self._origItemAction if hooked else item.action()
        target = self._origItemTarget if hooked else item.target()
        try:
            ok = NSApp.sendAction_to_from_(action, target, item)
            self._lastUntoggleAt = now
            _dbg("untoggle: sendAction -> %r, state now %r" % (ok, item.state()))
        except Exception:
            _dbgexc("untoggle: ")

    # --- heartbeat -----------------------------------------------------

    @objc.python_method
    def _startHeartbeat(self):
        try:
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.75, self, objc.selector(self._panelHeartbeat_), None, True
            )
        except Exception:
            _dbgexc("heartbeat: ")

    # NOT @objc.python_method — NSTimer needs this as a real ObjC selector.
    def _panelHeartbeat_(self, timer):
        try:
            self._pollViewItem()
            if time.time() - self._lastForegroundAt > IDLE_OFF:
                ns = self._nswindow()
                if ns is not None and ns.isVisible():
                    ns.orderOut_(None)
        except Exception:
            pass

    # NOT @objc.python_method — Glyphs.addCallback needs an ObjC selector.
    def _updateInterface_(self, sender):
        self._pollViewItem()
        if not self.live:
            return
        self._dirty = True
        self._maybeScan()

    # --- font / layer resolution ---------------------------------------

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

    # --- panel -----------------------------------------------------------

    @objc.python_method
    def _nswindow(self):
        if self._panel is None:
            return None
        try:
            return self._panel.getNSWindow()
        except Exception:
            return None

    @objc.python_method
    def _build_panel(self):
        w = FloatingWindow((620, 420), "Parametric Masters", closable=True,
                           minSize=(460, 260))
        self._panel = w
        # The red X means "turn the reporter off", not "hide the panel" —
        # foreground() would re-show it on the next draw.
        w.bind("close", self._panelClosed)
        y = 12
        w.pairLabel = TextBox((12, y, 70, 20), "Group by:")
        w.pairPop = PopUpButton((82, y, 200, 22), [""],
                                callback=self._pairChanged)
        w.liveBox = CheckBox((300, y, 60, 20), "Live", value=self.live,
                             callback=self._liveChanged)
        w.refreshButton = Button((-92, y - 2, 80, 24), "Refresh",
                                 callback=self._refreshClicked)
        y += 28
        w.scopeBox = CheckBox((12, y, 200, 20), "Current glyph only",
                              value=self.currentGlyphOnly,
                              callback=self._scopeChanged)
        y += 24
        w.summary = TextBox((12, y, -12, 16), "", sizeStyle="small")
        y += 22
        cols = [
            dict(title="Glyph", key="glyph", width=130, editable=False),
            dict(title="Group", key="group", width=110, editable=False),
            dict(title="Masters", key="masters", width=200, editable=False),
            dict(title="Δadv", key="dadv", width=50, editable=False),
            dict(title="ΔLSB", key="dlsb", width=50, editable=False),
            dict(title="ΔRSB", key="drsb", width=50, editable=False),
        ]
        w.list = List((10, y, -10, -10), [],
                      columnDescriptions=cols,
                      doubleClickCallback=self._openGlyph,
                      allowsMultipleSelection=False,
                      autohidesScrollers=False)
        font = self._currentFont()
        if font is not None:
            self._panelFont = font
            self._syncPairsToFont(font)
        w.open()
        ns = self._nswindow()
        if ns is not None:
            # Keep the window out of macOS session restoration so it can't
            # resurrect at launch independent of the View toggle.
            ns.setRestorable_(False)
            ns.disableSnapshotRestoration()

    @objc.python_method
    def _panelClosed(self, sender):
        # The red X toggles the reporter off (same as the View menu does)
        # and the dead vanilla window is dropped: the next wanted
        # foreground() rebuilds the panel from scratch.
        self._toggleOffViaMenu()
        self._panel = None

    @objc.python_method
    def _setStatus(self, text):
        if self._panel is not None and hasattr(self._panel, "summary"):
            try:
                self._panel.summary.set(text)
            except Exception:
                pass

    # --- panel callbacks -------------------------------------------------

    @objc.python_method
    def _syncPairsToFont(self, font):
        """Rebuild the Group-by popup: every pair of the font's axes."""
        if self._panel is None or not hasattr(self._panel, "pairPop"):
            return
        names = [str(a.name) for a in font.axes]
        self._pairs = []
        self._pairItems = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                self._pairs.append((i, j, names[i], names[j]))
                self._pairItems.append("%s + %s" % (names[i], names[j]))
        self._panel.pairPop.setItems(self._pairItems or ["(no axes)"])
        want = tuple(sorted(self._pair))
        for k, (_, _, na, nb) in enumerate(self._pairs):
            if tuple(sorted((na, nb))) == want:
                self._panel.pairPop.set(k)
                return
        if self._pairs:
            self._pair = (self._pairs[0][2], self._pairs[0][3])
            self._panel.pairPop.set(0)

    @objc.python_method
    def _pairChanged(self, sender):
        sel = sender.get()
        # vanilla's PopUpButton.get() is the index in some builds and the
        # title in others — accept both instead of failing silently.
        if isinstance(sel, (int, float)):
            idx = int(sel)
        else:
            try:
                idx = self._pairItems.index(sel)
            except ValueError:
                idx = -1
        if 0 <= idx < len(self._pairs):
            _, _, na, nb = self._pairs[idx]
            self._pair = (na, nb)
        self._scan()

    @objc.python_method
    def _scopeChanged(self, sender):
        self.currentGlyphOnly = bool(sender.get())
        self._scan()

    @objc.python_method
    def _liveChanged(self, sender):
        self.live = bool(sender.get())

    @objc.python_method
    def _refreshClicked(self, sender):
        self._dirty = True
        self._scan()

    @objc.python_method
    def _openGlyph(self, sender):
        sel = sender.getSelection()
        if not sel:
            return
        row = sender.get()[sel[0]]
        font = self._currentFont()
        if font is None:
            return
        try:
            font.masterIndex = row.get("_masterIndex", 0)
            font.newTab("/" + row["glyph"])
        except Exception:
            _dbgexc("open glyph: ")

    # --- scanning ----------------------------------------------------------

    @objc.python_method
    def _maybeScan(self):
        if not self._dirty:
            return
        if time.time() - self._lastScanAt < SCAN_THROTTLE:
            return  # trailing scan is picked up by foreground()
        self._scan()

    @objc.python_method
    def _scan(self):
        self._dirty = False
        self._lastScanAt = time.time()
        if self._panel is None:
            return
        font = self._currentFont()
        if font is None:
            self._setStatus("no font")
            return
        names = [str(a.name) for a in font.axes]
        try:
            idx_a, idx_b = names.index(self._pair[0]), names.index(self._pair[1])
        except ValueError:
            self._setStatus("axes %s not in this font" % (self._pair,))
            return
        groups = group_masters(font, idx_a, idx_b)
        if self.currentGlyphOnly and self._currentGlyphName:
            glyph_names = [self._currentGlyphName]
        else:
            glyph_names = [g.name for g in font.glyphs]
        try:
            rows = scan(font, groups, glyph_names)
        except Exception:
            _dbgexc("scan: ")
            self._setStatus("scan error — see log")
            return
        try:
            self._panel.list.set(rows)
        except Exception:
            pass
        scope = "current glyph" if self.currentGlyphOnly else "%d glyphs" % len(glyph_names)
        self._setStatus(
            "%s + %s — %d groups · %s · %d flagged"
            % (self._pair[0], self._pair[1], len(groups), scope, len(rows))
        )

    # --- reporter entry point (no Edit-view drawing) -----------------------

    @objc.python_method
    def foreground(self, layer):
        """Glyphs 3 reporter draw entry — the panel heartbeat and trailing
        live scan. Nothing is drawn into the Edit view."""
        self._lastForegroundAt = time.time()
        self._lastLayer = layer
        if not self._userEnabled:
            self._pollViewItem()
            if not self._userEnabled:
                return
        if self._panel is None and FloatingWindow is not None:
            self._build_panel()
        ns = self._nswindow()
        if ns is not None and not ns.isVisible():
            try:
                ns.makeKeyAndOrderFront_(None)
            except Exception:
                pass
        font = self._currentFont()
        if font is not None and font is not self._panelFont:
            self._panelFont = font
            self._syncPairsToFont(font)
            self._dirty = True
        try:
            glyph = layer.parent
            name = glyph.name if glyph is not None else None
        except Exception:
            name = None
        if name != self._currentGlyphName:
            self._currentGlyphName = name
            if self.currentGlyphOnly:
                self._dirty = True
        self._maybeScan()

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

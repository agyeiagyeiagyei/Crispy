# -*- coding: utf-8 -*-
"""Multi-Source Edit — Glyphs 3 Select Tool plugin.

Edit a point in one master and apply the same delta to the corresponding
point in any number of checked masters. Works with the standard Select
tool: drag a node, and the same movement is applied live to the same
(path, node) index in every synced master.

- Panel lists all masters with checkboxes.
- "Sync edits" toggle turns propagation on/off.
- Only point moves are synced; structural edits (add/delete) are not.

Undo: one step per target layer per drag, via beginChanges/endChanges.
"""

from __future__ import division, print_function, unicode_literals

import os
import time

import objc
from AppKit import NSImage
from GlyphsApp import Glyphs
from GlyphsApp.plugins import SelectTool

try:
    from vanilla import (
        CheckBox,
        FloatingWindow,
        TextBox,
    )
except ImportError:
    FloatingWindow = None


_DEBUG_LOG = "/tmp/multisourceedit-debug.log"


def _dbg(msg):
    try:
        import traceback as _tb
        with open(_DEBUG_LOG, "a") as f:
            f.write("%s\n" % msg)
            if msg == "EXCEPTION":
                f.write(_tb.format_exc())
    except Exception:
        pass


class MultiSourceEdit(SelectTool):

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Multi-Source Edit"})
        self.keyboardShortcut = None
        icon_path = os.path.join(os.path.dirname(self.__file__()), "toolbarIconTemplate.pdf")
        my_image = NSImage.alloc().initByReferencingFile_(icon_path)
        self._icon = None
        self.tool_bar_image = my_image

        # Sync state
        self.syncActive = False
        self.masterSelections = {}      # masterId -> bool (default True)
        self._panel = None
        self._masterRows = {}           # masterId -> CheckBox widget

        # Drag state
        self._dragStart = None          # drag start location (active layer coords)
        self._selectedNodeKeys = []     # [(pathIdx, nodeIdx), ...]
        self._activeInitial = {}        # nodeKey -> (x, y)
        self._targetInitial = {}        # layerId -> {nodeKey: (x, y)}
        self._targetLayers = {}         # layerId -> layer object
        self._targetsBegun = False      # whether beginChanges was called

    @objc.python_method
    def start(self):
        if FloatingWindow is not None:
            self._build_panel()

    @objc.python_method
    def activate(self):
        self._refreshMasters()
        self._show_panel()

    @objc.python_method
    def deactivate(self):
        self._cancelDrag()
        self._hide_panel()

    # ------------------------------------------------------------------
    # font / layer helpers (same pattern as CornerRadii)
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
        return None

    @objc.python_method
    def _activeMasterId(self, font):
        try:
            layer = self.editViewController().graphicView().activeLayer()
            if layer is not None:
                mids = set(m.id for m in font.masters)
                if layer.layerId in mids:
                    return layer.layerId
                if layer.associatedMasterId in mids:
                    return layer.associatedMasterId
        except Exception:
            pass
        try:
            m = font.selectedFontMaster
            if m is not None:
                return m.id
        except Exception:
            pass
        return None

    @objc.python_method
    def _targetMasterLayers(self, glyph, activeMasterId):
        """[(layerId, layer)] for checked masters, excluding the active one."""
        font = self._currentFont()
        if font is None:
            return []
        result = []
        for m in font.masters:
            if m.id == activeMasterId:
                continue
            if not self.masterSelections.get(m.id, True):
                continue
            try:
                layer = glyph.layers[m.id]
                if layer is not None:
                    result.append((m.id, layer))
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------
    # node selection helpers
    # ------------------------------------------------------------------

    @objc.python_method
    def _selectedNodeKeys(self, layer):
        """[(pathIndex, nodeIndex)] for nodes currently in layer.selection."""
        keys = []
        selection = set(layer.selection)
        for pathIdx, path in enumerate(layer.paths):
            for nodeIdx, node in enumerate(path.nodes):
                if node in selection:
                    keys.append((pathIdx, nodeIdx))
        return keys

    @objc.python_method
    def _nodeAt(self, layer, key):
        pathIdx, nodeIdx = key
        try:
            return layer.paths[pathIdx].nodes[nodeIdx]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # panel
    # ------------------------------------------------------------------

    @objc.python_method
    def _build_panel(self):
        w = FloatingWindow((280, 200), "Multi-Source Edit", closable=True)
        self._panel = w
        w.bind("close", self._panelClosed)
        y = 12
        w.syncBox = CheckBox(
            (12, y, 120, 20), "Sync edits",
            value=self.syncActive,
            callback=self._syncToggled,
        )
        y += 28
        w.mastersLabel = TextBox((12, y, 200, 20), "Masters:")
        y += 22
        self._mastersY = y
        self._refreshMasters()
        w.open()
        ns = self._nswindow()
        if ns is not None:
            ns.setRestorable_(False)
            ns.disableSnapshotRestoration()
            ns.orderOut_(None)

    @objc.python_method
    def _nswindow(self):
        if self._panel is None:
            return None
        return self._panel.getNSWindow()

    @objc.python_method
    def _show_panel(self):
        ns = self._nswindow()
        if ns is not None and not ns.isVisible():
            try:
                ns.makeKeyAndOrderFront_(None)
            except Exception:
                pass

    @objc.python_method
    def _hide_panel(self):
        ns = self._nswindow()
        if ns is not None and ns.isVisible():
            try:
                ns.orderOut_(None)
            except Exception:
                pass

    @objc.python_method
    def _panelClosed(self, sender):
        # Deactivate sync rather than closing the window
        self.syncActive = False
        if self._panel is not None:
            self._panel.syncBox.set(False)
        self._hide_panel()

    @objc.python_method
    def _syncToggled(self, sender):
        self.syncActive = bool(sender.get())
        _dbg("syncActive -> %s" % self.syncActive)

    @objc.python_method
    def _masterToggled(self, sender):
        for mid, cb in self._masterRows.items():
            if cb is sender:
                self.masterSelections[mid] = bool(sender.get())
                break

    @objc.python_method
    def _refreshMasters(self):
        if self._panel is None:
            return
        font = self._currentFont()
        w = self._panel
        for mid, cb in list(self._masterRows.items()):
            try:
                delattr(w, "master_%s" % mid.replace("-", "_"))
            except Exception:
                pass
        self._masterRows = {}
        if font is None:
            return
        masters = list(font.masters)
        cols = 2 if len(masters) > 8 else 1
        rows = (len(masters) + cols - 1) // cols
        col_w = 132
        for i, m in enumerate(masters):
            selected = self.masterSelections.get(m.id, True)
            self.masterSelections[m.id] = selected
            col, row = (i // rows, i % rows) if cols == 2 else (0, i)
            cb = CheckBox(
                (18 + col * col_w, self._mastersY + row * 22, col_w - 8, 20),
                m.name,
                value=selected,
                callback=self._masterToggled,
            )
            attr = "master_%s" % m.id.replace("-", "_")
            setattr(w, attr, cb)
            self._masterRows[m.id] = cb
        height = self._mastersY + rows * 22 + 12
        try:
            w.resize(280, height)
        except Exception:
            _dbg("EXCEPTION")

    # ------------------------------------------------------------------
    # drag tracking
    # ------------------------------------------------------------------

    def mouseDown_(self, theEvent):
        objc.super(MultiSourceEdit, self).mouseDown_(theEvent)
        self._cancelDrag()

        if not self.syncActive:
            return

        try:
            layer = self.editViewController().graphicView().activeLayer()
            if layer is None:
                return
            glyph = layer.parent
            font = self._currentFont()
            if glyph is None or font is None:
                return

            activeMid = self._activeMasterId(font)
            if activeMid is None:
                return

            self._dragStart = self.editViewController().graphicView().getActiveLocation_(theEvent)
            self._selectedNodeKeys = self._selectedNodeKeys(layer)

            # Record initial positions in active layer
            self._activeInitial = {}
            for key in self._selectedNodeKeys:
                node = self._nodeAt(layer, key)
                if node is not None:
                    self._activeInitial[key] = (node.position.x, node.position.y)

            # Record initial positions in target layers
            self._targetInitial = {}
            self._targetLayers = {}
            for mid, targetLayer in self._targetMasterLayers(glyph, activeMid):
                self._targetLayers[mid] = targetLayer
                self._targetInitial[mid] = {}
                for key in self._selectedNodeKeys:
                    node = self._nodeAt(targetLayer, key)
                    if node is not None:
                        self._targetInitial[mid][key] = (node.position.x, node.position.y)

            # Begin undo group for target layers
            if self._targetLayers:
                for targetLayer in self._targetLayers.values():
                    try:
                        targetLayer.beginChanges()
                    except Exception:
                        _dbg("EXCEPTION")
                self._targetsBegun = True

        except Exception:
            _dbg("EXCEPTION")

    def mouseDragged_(self, theEvent):
        objc.super(MultiSourceEdit, self).mouseDragged_(theEvent)

        if not self.syncActive or not self._targetsBegun:
            return

        try:
            layer = self.editViewController().graphicView().activeLayer()
            if layer is None or not self._selectedNodeKeys:
                return

            # Compute the actual delta applied to the active layer by the
            # standard tool (captures snapping/constraints if any).
            firstKey = self._selectedNodeKeys[0]
            node = self._nodeAt(layer, firstKey)
            if node is None or firstKey not in self._activeInitial:
                return
            dx = node.position.x - self._activeInitial[firstKey][0]
            dy = node.position.y - self._activeInitial[firstKey][1]

            # Apply same delta to all target layers
            for mid, targetLayer in self._targetLayers.items():
                initials = self._targetInitial.get(mid, {})
                for key in self._selectedNodeKeys:
                    if key not in initials:
                        continue
                    targetNode = self._nodeAt(targetLayer, key)
                    if targetNode is not None:
                        targetNode.position = (
                            initials[key][0] + dx,
                            initials[key][1] + dy,
                        )

            # Redraw so synced masters update live
            try:
                Glyphs.redraw()
            except Exception:
                pass

        except Exception:
            _dbg("EXCEPTION")

    def mouseUp_(self, theEvent):
        objc.super(MultiSourceEdit, self).mouseUp_(theEvent)
        self._endDrag()

    @objc.python_method
    def _endDrag(self):
        if self._targetsBegun:
            for targetLayer in self._targetLayers.values():
                try:
                    targetLayer.endChanges()
                except Exception:
                    _dbg("EXCEPTION")
            self._targetsBegun = False
        self._dragStart = None
        self._selectedNodeKeys = []
        self._activeInitial = {}
        self._targetInitial = {}
        self._targetLayers = {}

    @objc.python_method
    def _cancelDrag(self):
        """Abort any in-progress sync drag (tool switch, Escape, etc.)."""
        self._endDrag()

    # ------------------------------------------------------------------
    # boilerplate
    # ------------------------------------------------------------------

    @objc.python_method
    def __file__(self):
        return __file__

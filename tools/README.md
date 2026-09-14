# Crispy design tools

Glyphs 3 plugins written for Crispy's design and production workflow. The
repo is the source of truth; installed copies are duplicates.

## Install

Symlink (developing — repo edits go live on Glyphs restart):

```bash
ln -s "$PWD/tools/ParametricMasters.glyphsReporter" ~/Library/Application\ Support/Glyphs\ 3/Plugins/
# repeat per bundle, or: for b in tools/*.glyphsReporter tools/*.glyphsTool; do
#   ln -s "$PWD/$b" ~/Library/Application\ Support/Glyphs\ 3/Plugins/; done
```

Or copy (one-off install):

```bash
cp -R tools/*.glyphsReporter tools/*.glyphsTool ~/Library/Application\ Support/Glyphs\ 3/Plugins/
```

Restart Glyphs. The reporter plugins appear under **View → Show …**, the
tool plugin in the toolbar.

## Corner Radii (`CornerRadii.glyphsReporter`)

Audits and edits rounded corners. Enable via **View → Show Corner Radii**;
a floating panel opens alongside the Edit view.

Every rounded corner in the current glyph is detected and least-squares-fit
with a circle. The overlay draws:

- **gray circle** — the current fitted radius (amber when the round is
  poorly circular: fit residual > 8% of the radius)
- **blue label** — the radius at the current scale factor
- **blue outline + handles** — live preview of the corner as it would look
  after scaling
- **red lens** (optional) — where a scaled outer round would collide with
  a counter round

Panel controls:

- **Outer × / Inner ×** — independent scale factors for exterior-contour
  vs counter corners (fields, or −/+ in 0.05 steps). **Reset ×** restores
  1.00.
- **Show** toggles — Circles, Handles, Outlines; **Flag outer/inner
  overlaps**; **Baseline corners only** (restricts detection to corners
  whose virtual corner sits within ±10 units of y = 0).
- **Apply to** — scope: Current glyph / All glyphs / All glyphs, this
  master (the "→" hint shows which master was resolved) / Entire font,
  plus per-master checkboxes. Font-wide scopes also transform
  brace/bracket layers.
- **Apply** — rewrites node positions in place, keeping the same node
  slots, so masters stay interpolation-compatible.
- **Sharpen** — replaces each round with a single sharp corner node at the
  virtual corner (batched equivalent of Glyphs' "Sharpen Corners").

All edits are wrapped in one undo group per layer. The geometry core is
`Contents/Resources/cornerfit.py`, a pure-Python module with no Glyphs API
dependency (nodes are duck-typed), so it can also run under glyphsLib or
in scripts.

## Instance Delta (`InstanceDelta.glyphsReporter`)

Draws a comparison glyph — from a master or an interpolated instance —
behind the glyph being edited, and reports the advance-width difference.
Enable via **View → Instance Delta**.

- **Compare** popup lists `Master: …` then `Instance: …` entries. A master
  is read straight off the glyph (exact, free); an instance is
  interpolated once via `instance.interpolatedFont` and cached —
  re-interpolated on selection change, font change, or the **Refresh**
  button. The Width Matcher scratch instance is excluded from the list.
- Both outlines share x = 0, so the advance delta reads directly as the
  gap between the gray edit-advance marker and the colored
  instance-advance marker (**Advance markers** toggles them).
- The overlay draws for every glyph in the tab; the readout tracks the
  active glyph.
- A View toggle restored at launch does not open the panel (4 s grace);
  closing the panel with the red X stops panel and overlay until the view
  is re-selected.

## Multi-Source Edit (`MultiSourceEdit.glyphsTool`)

A Select-tool variant that propagates node drags across masters. Pick it
in the toolbar; its floating panel lists a **Sync edits** toggle plus one
checkbox per master (all checked by default).

With sync on, dragging a node applies the same delta live to the node at
the same (path, node) index in every checked master of that glyph. The
delta is read back from the first selected node in the active layer, so
snapping and constraints are captured; a multi-node drag syncs as a rigid
translation. Only point moves are synced — structural edits (adding or
deleting nodes) are not. Each drag closes as one undo step per target
layer. Closing the panel turns sync off; selecting the tool again
re-shows it.

`Contents/Resources/Icon.glyphs` is the design source for the toolbar
icon (`toolbarIconTemplate.pdf`); it is not used at runtime.

## Parametric Masters (`ParametricMasters.glyphsReporter`)

Audits parametric-master consistency in real time. Enable via **View →
Parametric Masters**; a floating panel opens alongside the Edit view.
Nothing is drawn into the Edit view.

The rule: masters that share the axis values driving horizontal metrics
should share horizontal metrics. Masters are grouped by a pair of axes —
**XTRA + XOPQ** by default (the horizontal transparent and opaque
factors) — and any glyph whose advance width, LSB, or RSB differs within
a group is flagged.

- **Group by** popup offers every pair of the font's axes, so other
  hypotheses (e.g. XTRA + YOPQ) can be checked too.
- Font-wide by default; **Current glyph only** narrows the audit to the
  Edit view's glyph.
- **Live** updates while you draw (throttled to one scan per second);
  **Refresh** forces a rescan.
- Only groups of 2+ masters are audited. Consensus is the first member's
  metrics; deviations over 1 unit are flagged. Double-click a row to open
  the glyph at the group's first master.

## Width Matcher (`WidthMatcher.glyphsReporter`)

Creates a new master whose advance widths match an existing reference
master's. Enable via **View → Width Matcher**. It draws nothing into the
Edit view; everything happens in the panel.

- **Reference** popup picks the master to match.
- **Axis sliders** (one per design axis, with numeric fields) drive a real
  GSInstance named *Width Matcher Preview* kept in `font.instances`, so
  Glyphs' own interpolation engine (brace layers included) produces the
  generated outlines. Slider range runs from the master minimum to 3× the
  master maximum, allowing extrapolation. The instance is visible in Font
  Info while the tool is in use.
- The **preview** draws the reference glyph (gray) and generated glyph
  (blue) ink-centered on each other, with markers at both advance boxes.
  Readouts: advance Ref vs Gen with Δ, ink width Ref vs Gen with Δ (the
  value you drive to zero by nudging sliders), and a "Saved: LSB/RSB/Adv"
  line predicting what Save will actually write.
- **Spacing** popup picks the saved master's spacing contract: reference
  sidebearings verbatim, or reference advance (plus **Adv offset**) with
  sidebearings redistributed proportionally / centred / keep-LSB. Empty
  glyphs take the reference advance.
- **Save as Master** interpolates the working instance, appends it as a
  new master, copies every glyph's layer across, and re-spaces each layer
  per the chosen mode. Afterwards it re-audits sidebearings (metrics keys
  can rewrite them when the interface updates resume) and reports drift
  in the status line.

## Development notes

- All five plugins follow the standard Glyphs 3 Python plugin template
  (bundle + stub loader, `NSPrincipalClass`, `PyMainFileNames`,
  vanilla `FloatingWindow` panels).
- This Glyphs build does not call `activate()`/`deactivate()` on View
  toggles, so panel visibility is driven by the reporter draw callbacks
  plus an `NSTimer` heartbeat instead — that is deliberate, not a quirk
  to "fix".
- Plugins are closed by default, opened via the View menu: Glyphs
  restores the View toggle programmatically (at launch or document
  open), and there is no reliable moment to catch it. So each reporter
  trampolines its View item's action (`_hookViewItem` /
  `_viewItemClicked_`): a real CLICK marks user intent, while an on
  state with no click seen is the session restore and is switched back
  off (`_toggleOffViaMenu`, bypassing the trampoline). Toggle state is
  polled from `Glyphs.addCallback(UPDATEINTERFACE)` with `state()`
  reads forced fresh via `menu.update()`; NSTimer callbacks never fire
  in this build (confirmed by instrumentation), and draw timing is never
  used — a pause in drawing is indistinguishable from a toggle (the bug
  in earlier iterations). A panel's red X toggles the reporter off and
  drops the dead vanilla window; the next wanted `foreground()` rebuilds
  the panel. (Multi-Source Edit is a toolbar tool without a View item,
  so it keeps a 2 s activate grace instead.)
- Each `plugin.py` has a module-level `DEBUG = False`. Flip it to `True`
  to append instrumentation to `/tmp/<plugin>-debug.log` while
  developing; it ships off.

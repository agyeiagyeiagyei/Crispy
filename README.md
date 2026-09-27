# Crispy

**Crispy** is a variable font, designed by Agyei Archer for Google Fonts and licensed under the [SIL Open Font License, 1.1](http://scripts.sil.org/OFL).

Crispy's variations are created based on Font Bureau and David Berlow's [variations proposal](https://variationsguide.typenetwork.com/), which outlined the descriptions of font features using more elemental factors than the more common paradigms like weight, width, x-height, etc. The parametric axes used in Crispy follow the [Type Network Parametric Axes proposal](https://github.com/Microsoft/OpenTypeDesignVariationAxisTags/blob/master/Proposals/TypeNetwork_ParametricAxes/Overview.md) submitted by Sam Berlow of Type Network.

Crispy is a typeface designed for applications where headline content needs to take primary importance. Its parametric design makes it applicable to a spectrum of eccentricity that makes it usable for headlines of all flav*ou*rs. Initially this focus was a good excuse to make it uppercase only, but a lowercase has since been added to increase range of future usability.

Development and design for this typeface project is sponsored by Google Fonts, and in the future it may be available in Google Fonts. Until then, this respository is the best place to download the latest usable files.


### Axes:

Crispy uses a dual-axis system: **traditional axes** (stylistic) and **parametric axes** (elemental). The source carries only the parametric axes; the traditional axes, and the avar2 table that maps them onto parametric combinations, are added at build time by [avar2-studio](https://github.com/agyeiagyeiagyei/avar2-studio) from the sidecar files in `sources/`.

**Traditional Axes (Stylistic):**
These are the familiar axes that describe the end-result appearance:
- **Weight** (wght): 1–1000
- **Width** (wdth): 5–220
- **Optical Size** (opsz): 14–144
- **Grade** (GRAD): −10 to +10 — darkens or lightens a style without changing its advance widths; declared in `sources/Crispy-grade.json`

**Parametric Axes (Elemental):**
These are the fundamental building blocks that control specific structural components, following the [Type Network Parametric Axes proposal](https://github.com/Microsoft/OpenTypeDesignVariationAxisTags/blob/master/Proposals/TypeNetwork_ParametricAxes/Overview.md). Values are in units on the em square (where 1000 units = 1em):
- **X-Opacity** (XOPQ): 1–1462 units - Controls horizontal opaque (positive) space
- **Y-Opacity** (YOPQ): 1–275 units - Controls vertical opaque (positive) space
- **X-Transparency** (XTRA): 47–1715 units - Controls horizontal transparent (negative) space
- **Spacing** (SPAC): −40 to 40 — tracking, added by the width-aware spacing transform declared in `sources/Crispy-transforms.json`

Two **secondary parametric axes** deform only chosen glyphs: **Lowercase width** (lcwd, 0–100) renders the lowercase at the heavy end as if at a lighter XOPQ, and **Horizontal correction** (ymod, 0–100) adjusts a handful of glyphs. They are declared in `sources/Crispy-control.json`, a working file that is not committed; `scripts/setup_lowercase_axis.py` and `scripts/setup_drawn_axis.py` regenerate it.

**Avar2 Mapping:**
The font uses an avar2 table to map traditional axis combinations to parametric axis values. This allows users to work with familiar axes (Weight, Width, Optical Size) while the font internally uses parametric axes (XOPQ, YOPQ, XTRA). Each row of `sources/Crispy-avar.csv` is one mapping: the `Def` row, for example, maps Weight=400, Width=100, Optical Size=48 to XTRA=663.1, XOPQ=202.5, YOPQ=121.8.

**Editing the avar2 mappings:**

Crispy's avar2 mappings, secondary axes, grade and transforms are authored with
[avar2-studio](https://github.com/agyeiagyeiagyei/avar2-studio). Install the
release wheel for the studio (the git install used by CI has no UI):

```bash
pipx install avar2-studio
avar2-studio sources/Crispy.glyphs
```

avar2-studio picks up the sibling `sources/Crispy-avar.csv` and the other
`Crispy-*` sidecars automatically and writes its working state into a
sibling `.avar2-studio/` directory (gitignored). Open `http://localhost:5001`
in a browser.

**Design tools:**

Six Glyphs 3 plugins were built for Crispy's design workflow — **Corner
Radii** (rounded-corner audit/edit), **Instance Delta** (master/instance
comparison overlay), **Multi-Source Edit** (node drags propagated across
masters), **Parametric Masters** (live parametric-master metrics audit),
**Slant Master** (italic masters: a source sheared into a new master, widths
matched to a reference), and **Width Matcher** (width-matched master creation). They now ship
with avar2-studio, under its **Window → avar2 Studio** menu in Glyphs:
`avar2-studio install-glyphs-plugins`, then restart Glyphs. Usage is in
[avar2-studio's glyphs README](https://github.com/agyeiagyeiagyei/avar2-studio/blob/main/src/avar2_studio/glyphs/README.md).

___
**For the purposes of this project, I describe *axes* as visual paradigms that we use to describe one or more features in a variable font.**

I describe *parametric axes* as elemental axes that we can use to describe one structural or aesthetic component of a typeface. 

I describe *stylistic axes* as axes that we can use to describe the end-result of more than one of these elemental factors, expressed to different individual degrees at the same time. 

By these descriptions, we can think of ***Weight*** as a stylistic axis that can be expressed as a combination of ***X-Opacity*** and ***Y-Opacity***. This parametric approach provides a more fundamental way to describe typeface attributes, offering greater flexibility and precision in typographic applications.

Anyway,

___

### Designer:
* Agyei Archer

### License:
Copyright (c) 2025, Agyei Archer (hello@agyei.design | [agyei.design]() )

Licensed under the [SIL Open Font License, 1.1](http://scripts.sil.org/OFL); you may not use this file except in compliance with the License.


### Building:

The fonts are built by avar2-studio, headless — the same pipeline the studio runs on load. CI (`.github/workflows/build.yaml`) does exactly this:

```bash
pip install -r requirements.txt
pip install "avar2-studio @ git+https://github.com/agyeiagyeiagyei/avar2-studio@github-pages"
avar2-studio build sources/Crispy.glyphs --out fonts/variable
```

This compiles the source with fontc, regenerates the secondary-axis shadow and the grade layers, builds the avar2 table from `sources/Crispy-avar.csv`, applies the spacing transform, and writes the variable font to `fonts/variable/`. CI then runs fontspector and diffenator2 proofs and publishes the results to GitHub Pages.


### Glyphs + :

### Design log:
* August 2025: build process completed: 8 masters, 6 axes
* December 2024: design optimised for avar2 revamped
* December 2023: design revamped entirely
* December 2021: math symbols completed, Design sources moved to Glyphs
* December 2020: lowercase parametric versions completed and merged
* March 2020: design direction completed and proportions resolved
* Juneish 2019: design initiated


### Acknowledgements

**David Jonathan Ross: Design Advisor** | david@djr.com | [http://djr.com/](http://djr.com/)

**Eben Sorkin: Design Advisor** | eben@eyebytes.com | [http://sorkintype.com/](http://sorkintype.com/)

**Tanya George: Design Production** | tanya@tanyatypes.com | [https://tanyatypes.wordpress.com/
](https://tanyatypes.wordpress.com/)

**Agyei Archer: Designer** | hello@agyei.design | [http://agyei.design]()

**David Berlow: Parametric Design Theorist & Pioneer**** [http://davidberlow.fontbureau.com/](http://davidberlow.fontbureau.com/)

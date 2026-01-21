# Crispy

**Crispy** is a variable font, designed by Agyei Archer for Google Fonts and licensed under the [SIL Open Font License, 1.1](http://scripts.sil.org/OFL).

Crispy's variations are created based on Font Bureau and David Berlow's [variations proposal](https://variationsguide.typenetwork.com/), which outlined the descriptions of font features using more elemental factors than the more common paradigms like weight, width, x-height, etc. The parametric axes used in Crispy follow the [Type Network Parametric Axes proposal](https://github.com/Microsoft/OpenTypeDesignVariationAxisTags/blob/master/Proposals/TypeNetwork_ParametricAxes/Overview.md) submitted by Sam Berlow of Type Network.

Crispy is a typeface designed for applications where headline content needs to take primary importance. Its parametric design makes it applicable to a spectrum of eccentricity that makes it usable for headlines of all flav*ou*rs. Initially this focus was a good excuse to make it uppercase only, but a lowercase has since been added to increase range of future usability.

Development and design for this typeface project is sponsored by Google Fonts, and in the future it may be available in Google Fonts. Until then, this respository is the best place to download the latest usable files.


### Axes:

Crispy uses a dual-axis system: **traditional axes** (stylistic) and **parametric axes** (elemental). The font includes both, with an avar2 table that maps traditional axis combinations to their parametric equivalents.

**Traditional Axes (Stylistic):**
These are the familiar axes that describe the end-result appearance:
- **Weight** (wght): 100-700
- **Width** (wdth): 52-300  
- **Optical Size** (opsz): 12-72
- **Contrast** (cntr): -10 to +10 (programmatically added)

**Parametric Axes (Elemental):**
These are the fundamental building blocks that control specific structural components, following the [Type Network Parametric Axes proposal](https://github.com/Microsoft/OpenTypeDesignVariationAxisTags/blob/master/Proposals/TypeNetwork_ParametricAxes/Overview.md). Values are in units on the em square (where 1000 units = 1em):
- **X-Opacity** (XOPQ): 2-1016 units - Controls horizontal opaque (positive) space
- **Y-Opacity** (YOPQ): 2-462 units - Controls vertical opaque (positive) space
- **X-Transparency** (XTRA): 94-3330 units - Controls horizontal transparent (negative) space
- **Spacing** (SPAC): -20 to 40 units (programmatically added) - Controls relative advance width

**Avar2 Mapping:**
The font uses an avar2 table to map traditional axis combinations to parametric axis values. This allows users to work with familiar axes (Weight, Width, Optical Size) while the font internally uses parametric axes (XOPQ, YOPQ, XTRA, SPAC). The avar2 table contains mappings for all combinations of traditional axes, automatically translating user input to the appropriate parametric values.

For example, when a user sets Weight=400, Width=100, Optical Size=72, the avar2 table maps this to XTRA=627.0, XOPQ=187.672, YOPQ=160.0, SPAC=25. This mapping is defined in `sources/avar2-mappings.csv` and built into the font during compilation.

**Preview Tool:**
A web-based preview tool is available (on the `glyphs-preview-tool` branch) for fine-tuning traditional axis outcomes. The tool allows you to:
- Preview all instances in real-time
- Adjust parametric axes (XOPQ, YOPQ, XTRA) with sliders
- See how traditional axis combinations map to parametric values via avar2
- Edit instance coordinates and update the Glyphs file
- Build fonts on-the-fly for instant preview

This tool is particularly useful for understanding how traditional axis combinations translate to parametric values and for fine-tuning the avar2 mappings.

**To launch the preview tool:**

```bash
# Using the launch script (recommended)
./scripts/launch-preview.sh

# Or specify a custom Glyphs file
./scripts/launch-preview.sh sources/Crispy.glyphs

# Manual launch (two terminals)
# Terminal 1: Backend server
python3 scripts/glyphs-preview-server.py --glyphs sources/Crispy.glyphs

# Terminal 2: Frontend
cd preview-app
npm start
```

The tool will be available at http://localhost:3000.

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

The build process uses `gftools builder` with `fontmake` for font compilation.

**To build the fonts:**

```bash
make build
```

This will:
1. Sync avar2 mappings from the Glyphs file
2. Update `config.yaml` with STAT and avar2 sections
3. Build variable fonts using `gftools builder`
4. Convert avar2 tables to avar1 for backward compatibility
5. Output fonts to the `fonts/` directory

**Prerequisites:**
- Python 3 with virtual environment (created automatically)
- `gftools` (installed via `requirements.txt`)

### Ideal build:

The masters associated with these files are handled on export by `gftools builder`, which uses `fontmake` for compilation. The build process is automated using `config.yaml` to specify variables like family name, instance names, STAT table, and avar2 mappings.

***The build process covers:***

1. Building parametric instances (stylistic sources)
2. Weight, Width, and Optical Size expressed as combinations of X-Opacity (XOPQ), Y-Opacity (YOPQ), X-Transparency (XTRA), and Spacing (SPAC) axes
3. Building stylistic sources (fvarInstances)
4. ttfautohint and other builtin fontmake checks (via gftools builder)
5. Building variable font with proper STAT and avar2 tables
6. Converting avar2 tables to avar1 for backward compatibility

**Additional targets available:**
- `make images`: Generate PNG specimen images using drawbot (requires separate run)
- `make proof`: Generate HTML proof documents (requires separate run)


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

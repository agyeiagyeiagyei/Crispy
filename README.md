# Crispy

**Crispy** is a variable font, designed by Agyei Archer for Google Fonts and licensed under the [SIL Open Font License, 1.1](http://scripts.sil.org/OFL).

Crispy's variations are created based on Font Bureau and David Berlow's [variations proposal](https://variationsguide.typenetwork.com/), which outlined the descriptions of font features using more elemental factors than the more common paradigms like weight, width, x-height, etc.

Crispy is a typeface designed for applications where headline content needs to take primary importance. Its parametric design makes it applicable to a spectrum of eccentricity that makes it usable for headlines of all flav*ou*rs. Initially this focus was a good excuse to make it uppercase only, but a lowercase has since been added to increase range of future usability.

Development and design for this typeface project is sponsored by Google Fonts, and in the future it may be available in Google Fonts. Until then, this respository is the best place to download the latest usable files.


### Planned Axes:

| Axis Name       | Axis Label | Axis Type     | Min Value    | Max Value |
| :-------------  | :--------- | :-----------  | -----------: | --------: |
|  X-Opacity      | XOPQ       | Parametric    | 2            | 1016      |
|  Y-Opacity      | YOPQ       | Parametric    | 2            | 462       |
|  X-Transparency | YTRA       | Parametric    | 94            | 3330      |
|  Relative X-Advance | RXAD       | Parametric    | 40            | 160      |
|  Weight         | wght       | Stylistic     | 100          | 900       |
|  Width          | wdth       | Stylistic     | 40            | 160       |
|  Optical Size   | opsz       | Stylistic     | 12           | 72        |

___
**For the purposes of this project, I describe *axes* as visual paradigms that we use to describe one or more features in a variable font.**

I describe *parametric axes* as elemental axes that we can use to describe one structural or aesthetic component of a typeface. 

I describe *stylistic axes* are axes that we can use to describe the end-result of more than one of these elemental factors, expressed to different individual degrees at the same time. 

By these descriptions, we can think of ***Weight*** as a stylistic axis that can be expressed as a combination of ***X-Opacity***, ***Y-Opacity***, ***Y-Transparency***, and ***X-Transparency***. We know then that, typically, a Latin typeface with conventional contrast will have a greater ratio of X-Opacity to Y-Opacity, at least visually, if not numerically.  Immediately, we can flag this idea of "conventional contrast" as potentially limiting, and a demonstrable indication of the long-term conceptual and semantic advantage of thinking of fonts parametrically, especially in global typographic applications where we would want to avoid positioning Latin-centric paradigms as default or industry standards. Right?

Anyway,

___

### Designer:
* Agyei Archer

### License:
Copyright (c) 2025, Agyei Archer (hello@agyei.design | [agyei.design]() )

Licensed under the [SIL Open Font License, 1.1](http://scripts.sil.org/OFL); you may not use this file except in compliance with the License.


### Ideal build:

The masters asociated with these file are only handled on export by a recently updated configuration of gftools builder, and the build process is currently automated using this congif file to specify variables like family name, instance names, etc.

[I think It would be good for Marc to help me outline the limitations that the builder has in terms of font features?]

***The ideal build will cover:***

1. Building parametric instances i.e. stylistic sources
2. Weight, Width, and Optical Size expressed as combinations of X-Opacity (XOPQ), Y-Opacity (YOPQ), X-Transparency (XTRA), and Relative Advance Width (RXAD) axes
3. Building stylistic sources
4. ttfautohint and other builtin fontmake checks
2. Building well-labeled versions of static .ttf and .woff files
3. Building variable font
4. *Automated static and animated proofs with drawbot*
5. *Automated, well-labelled git push* ⁴


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

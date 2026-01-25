SOURCES=$(shell python3 scripts/read-config.py --sources )
FAMILY=$(shell python3 scripts/read-config.py --family )
DRAWBOT_SCRIPTS=$(shell ls documentation/*.py)
DRAWBOT_OUTPUT=$(shell ls documentation/*.py | sed 's/\.py/.png/g')

help:
	@echo "###"
	@echo "# Build targets for $(FAMILY)"
	@echo "###"
	@echo
	@echo "  make build:       Builds the fonts and places them in the fonts/ directory"
	@echo "  make build-test:  Test build using preview-app/Crispy-avar.csv and config-preview.yaml (safe, doesn't modify sources)"
	@echo "  make test:        Tests the fonts with fontspector"
	@echo "  make proof:       Creates HTML proof documents in the proof/ directory"
	@echo "  make images:      Creates PNG specimen images in the documentation/ directory"
	@echo

build: build.stamp

venv: venv/touchfile

customize: venv
	. venv/bin/activate; python3 scripts/customize.py

# Step 0: Sync avar2-mappings.csv from Glyphs file (updates XTRA, XOPQ, YOPQ)
# Step 1: Update config.yaml with STAT and avar2 sections from CSV
# Steps 2-7: Build fonts (gftools builder generates build.ninja with 6 steps: buildVariable, fix, BuildSTAT, AddSpacingAxis, BuildAvar2, BuildFvarInstances)
# Step 8: Convert avar2 to avar1
build.stamp: venv sources/config.yaml sources/avar2-mappings.csv sources/Crispy.glyphs $(SOURCES)
	rm -rf fonts;
	. venv/bin/activate && \
	python3 scripts/sync-glyphs-to-avar2.py --glyphs sources/Crispy.glyphs --csv sources/avar2-mappings.csv --once && \
	python3 sources/update_config.py --csv sources/avar2-mappings.csv --config sources/config.yaml --no-backup --add-opsz && \
	(for config in sources/config*.yaml; do gftools builder --experimental-fontc $$(which fontc) $$config; done) && \
	gftools avar2-to-avar1 "fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf" -m scripts/mapping.yaml -o "fonts/variable/Crispy[SPAC,XOPQ,XTRA,YOPQ]-avar1.ttf" && \
	touch build.stamp

venv/touchfile: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	touch venv/touchfile

test: build.stamp
	which fontspector || (echo "fontspector not found. Please install it with 'cargo install fontspector'." && exit 1)
	TOCHECK=$$(find fonts/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); fi ; mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --html out/fontspector/fontspector-report.html --ghmarkdown out/fontspector/fontspector-report.md $$TOCHECK  || echo '::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'

proof: venv build.stamp
	TOCHECK=$$(find fonts/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); fi ; . venv/bin/activate; mkdir -p out/ out/proof; diffenator2 proof $$TOCHECK -o out/proof

images: venv $(DRAWBOT_OUTPUT)

%.png: %.py build.stamp
	. venv/bin/activate; python3 $< --output $@

# Test build using preview CSV and config-preview.yaml
# Outputs to preview-app/fonts-avar2/ directory
build-test: venv preview-app/Crispy-avar.csv preview-app/config-preview.yaml sources/Crispy.glyphs $(SOURCES)
	@echo "=== TEST BUILD: Using preview-app/Crispy-avar.csv and config-preview.yaml ==="
	@echo "This build validates CSV is synced with Glyphs, then updates config before building"
	@echo "Output will be in preview-app/fonts-avar2/ directory"
	@echo ""
	rm -rf test-build;
	. venv/bin/activate && \
	mkdir -p preview-app/fonts-avar2/variable test-build/sources && \
	python3 scripts/check-csv-sync.py --glyphs sources/Crispy.glyphs --csv preview-app/Crispy-avar.csv || (echo "ERROR: CSV is not synced with Glyphs file. Please sync first." && exit 1) && \
	python3 sources/update_config.py --csv preview-app/Crispy-avar.csv --config preview-app/config-preview.yaml --no-backup && \
	cp preview-app/config-preview.yaml test-build/sources/test-config.yaml && \
	sed -i '' 's|- ../sources/Crispy.glyphs|- Crispy.glyphs|' test-build/sources/test-config.yaml 2>/dev/null || sed -i 's|- ../sources/Crispy.glyphs|- Crispy.glyphs|' test-build/sources/test-config.yaml && \
	python3 -c "import yaml; f=open('test-build/sources/test-config.yaml','r'); d=yaml.safe_load(f); f.close(); d.pop('spacingAxis', None); old_key='Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf'; new_key='Crispy[XOPQ,XTRA,YOPQ].ttf'; fvar=d.get('fvarInstances',{}); avar2=d.get('avar2',{}); stat=d.get('stat',{}); fvar.update({new_key: fvar.pop(old_key)}) if old_key in fvar else None; avar2.update({new_key: avar2.pop(old_key)}) if old_key in avar2 else None; stat.update({new_key: stat.pop(old_key)}) if old_key in stat else None; f=open('test-build/sources/test-config.yaml','w'); yaml.dump(d, f, default_flow_style=False, sort_keys=False, allow_unicode=True); f.close()" && \
	ln -s ../../sources/Crispy.glyphs test-build/sources/Crispy.glyphs && \
	ln -sf ../preview-app/fonts-avar2 test-build/fonts && \
	cd test-build/sources && gftools builder --experimental-fontc $$(which fontc) test-config.yaml && \
	cd ../.. && \
	FONT_FILE="preview-app/fonts-avar2/variable/Crispy[XOPQ,XTRA,YOPQ].ttf" && \
	if [ ! -f "$$FONT_FILE" ]; then \
		echo "Error: Variable font not found at $$FONT_FILE"; \
		ls -la preview-app/fonts-avar2/variable/ 2>/dev/null || echo "preview-app/fonts-avar2/variable/ does not exist"; \
		rm -rf test-build; \
		exit 1; \
	fi && \
	gftools avar2-to-avar1 "$$FONT_FILE" -m scripts/mapping.yaml -o "preview-app/fonts-avar2/variable/Crispy[XOPQ,XTRA,YOPQ]-avar1.ttf" && \
	rm -rf test-build && \
	echo "" && \
	echo "=== TEST BUILD COMPLETE ===" && \
	echo "Test fonts are in preview-app/fonts-avar2/variable/" && \
	echo "Build was completely isolated - no interference with fonts/ or sources/" && \
	echo "CSV was validated to be synced with Glyphs before building"

clean:
	rm -rf venv fonts-test test-build test-config.yaml
	find . -name "*.pyc" -delete

update-project-template:
	npx update-template https://github.com/googlefonts/googlefonts-project-template/

update: venv
	venv/bin/pip install --upgrade pip-tools
	# See https://pip-tools.readthedocs.io/en/latest/#a-note-on-resolvers for
	# the `--resolver` flag below.
	venv/bin/pip-compile --upgrade --verbose --resolver=backtracking requirements.in
	venv/bin/pip-sync requirements.txt

	git commit -m "Update requirements" requirements.txt
	git push

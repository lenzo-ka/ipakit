# Regeneratable artefacts. Everything here is derived from the data and
# checked in, so a reader gets the figures without running anything and a
# reviewer sees a change to them in the diff.

PYTHON ?= python
FIGDIR := docs/figures
# One head is drawn. The others are not adult-male-shaped variants to be
# eyeballed -- tests/test_tract_figures.py checks every declared head, which
# is what says they are right; checking in three near-identical rest drawings
# would add weight without adding a check.
HEAD   ?= adult-male

# Symbol per figure. The stem is ASCII because a filename is not a place to
# put IPA; the symbol it draws is in the second column.
FIGURES := m:m n:n eng:ŋ t:t k:k theta:θ s:s esh:ʃ a:a i:i u:u silence:␣

.PHONY: figures figures-clean lint check

## figures: redraw the mid-sagittal tract figures in docs/
figures:
	@mkdir -p $(FIGDIR)
	@$(PYTHON) scripts/tract_svg.py draw --head $(HEAD) \
		-o $(FIGDIR)/tract-reference.svg
	@for pair in $(FIGURES); do \
		stem=$${pair%%:*}; sym=$${pair#*:}; \
		$(PYTHON) scripts/tract_svg.py draw --head $(HEAD) --phone "$$sym" \
			-o $(FIGDIR)/tract-$$stem.svg; \
	done

figures-clean:
	@rm -f $(FIGDIR)/tract-*.svg

## lint: the style gates; needs the `lint` extra (ruff / black / mypy)
lint:
	@$(PYTHON) -m ruff check .
	@$(PYTHON) -m black --check .
	@$(PYTHON) -m mypy

## check: the gates a release runs
# lint is a prerequisite rather than a recipe line so it fails in seconds,
# before the suite spends a minute earning the same verdict.
check: lint
	@$(PYTHON) -m pytest -q
	@PYTHONHASHSEED=0 $(PYTHON) scripts/invariants.py
	@$(PYTHON) scripts/confusion.py validate
	@$(PYTHON) scripts/xsampa_table.py validate

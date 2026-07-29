# Regeneratable artefacts. Everything here is derived from the data and
# checked in, so a reader gets the figures without running anything and a
# reviewer sees a change to them in the diff.

PYTHON ?= python
FIGDIR := docs/figures
HEAD   ?= adult-male

# Symbol per figure. The stem is ASCII because a filename is not a place to
# put IPA; the symbol it draws is in the second column.
FIGURES := m:m n:n eng:ŋ t:t k:k theta:θ s:s esh:ʃ a:a i:i u:u silence:␣

.PHONY: figures figures-clean check

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

## check: the gates a release runs
check:
	@$(PYTHON) -m pytest -q
	@PYTHONHASHSEED=0 $(PYTHON) scripts/invariants.py
	@$(PYTHON) scripts/confusion.py validate
	@$(PYTHON) scripts/xsampa_table.py validate

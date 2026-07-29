# Regeneratable artefacts. Everything here is derived from the data and
# checked in, so a reader gets the figures without running anything and a
# reviewer sees a change to them in the diff.

PYTHON ?= python
FIGDIR := docs/figures
HEAD   ?= adult-male
# Every declared head gets a reference figure. The phone figures use one head
# to keep the set readable, but the geometry is not adult-male-only and the
# tests do not treat it as though it were.
HEADS  ?= adult-male adult-female child

# Symbol per figure. The stem is ASCII because a filename is not a place to
# put IPA; the symbol it draws is in the second column.
FIGURES := m:m n:n eng:ŋ t:t k:k theta:θ s:s esh:ʃ a:a i:i u:u silence:␣

.PHONY: figures figures-clean check

## figures: redraw the mid-sagittal tract figures in docs/
figures:
	@mkdir -p $(FIGDIR)
	@for head in $(HEADS); do \
		$(PYTHON) scripts/tract_svg.py draw --head $$head \
			-o $(FIGDIR)/tract-$$head.svg; \
	done
	@cp $(FIGDIR)/tract-$(HEAD).svg $(FIGDIR)/tract-reference.svg
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

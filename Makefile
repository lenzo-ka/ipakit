# Regeneratable artifacts. Everything here is derived from the data and
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

.PHONY: figures figures-clean tutorial notebook lint check

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

## tutorial: regenerate docs/tutorial.md by running every example in it
# The prose is written in docs/tutorial.src.md; every value in the page is
# produced by executing the call beside it. PYTHONHASHSEED is pinned for the
# same reason it is pinned for invariants.py -- `check` compares bytes.
tutorial:
	@PYTHONHASHSEED=0 $(PYTHON) scripts/tutorial.py build markdown

## notebook: regenerate the tutorial notebook that ships in the package
# The same source and the same parse as `tutorial`, emitted as cells with no
# results in them. Nothing runs, so there is no seed to pin.
notebook:
	@$(PYTHON) scripts/tutorial.py build notebook

## lint: the style gates; needs the `lint` extra (ruff / black / mypy)
lint:
	@$(PYTHON) -m ruff check .
	@$(PYTHON) -m black --check .
	@$(PYTHON) -m mypy

## PYTEST_WORKERS: how many processes the suite runs in.
# 'auto' is one per core. Set it to 0 to run serially -- useful when a failure
# needs a readable traceback, or on a machine already under load, since xdist
# takes the cores it is given whatever else is running.
PYTEST_WORKERS ?= auto
PYTEST_N = $(if $(filter 0,$(PYTEST_WORKERS)),,-n $(PYTEST_WORKERS))

## check: the gates a release runs
# lint is a prerequisite rather than a recipe line so it fails in seconds,
# before the suite spends a minute earning the same verdict.
check: lint
	@$(PYTHON) -m pytest -q $(PYTEST_N)
	@PYTHONHASHSEED=0 $(PYTHON) scripts/invariants.py
	@$(PYTHON) scripts/confusion.py validate
	@$(PYTHON) scripts/xsampa_table.py validate
	@PYTHONHASHSEED=0 $(PYTHON) scripts/tutorial.py check all
	@PYTHONHASHSEED=0 $(PYTHON) scripts/docexamples.py

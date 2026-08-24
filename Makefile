# Regeneratable artifacts. Everything under docs/figures is derived from the
# data and checked in, so a reader gets the figures without running anything
# and a reviewer sees a change to them in the diff. frontal_figures.py also
# writes on-demand working artifacts under talking-heads/; those are excluded
# from pinning by design and are not part of this checked-in claim.

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

.PHONY: figures figures-clean tutorial tutorial-basics notebook house-style perceptual-validation state-of-work espeak-vocabularies espeak-vocabularies-check lint check gate-subject

ESPEAK_NG ?= $(HOME)/dev/other/espeak-ng

## espeak-vocabularies: regenerate every language-scoped eSpeak declaration
espeak-vocabularies:
	@if test ! -d "$(ESPEAK_NG)/.git"; then \
		echo "espeak-vocabularies: pinned checkout absent; nothing regenerated"; \
	else \
		$(PYTHON) scripts/espeak_vocabularies.py generate --source "$(ESPEAK_NG)"; \
	fi

espeak-vocabularies-check:
	@if test ! -d "$(ESPEAK_NG)/.git"; then \
		echo "espeak-vocabularies: pinned checkout absent; generated-data check skipped"; \
	else \
		$(PYTHON) scripts/espeak_vocabularies.py check --source "$(ESPEAK_NG)"; \
	fi

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
	@$(PYTHON) scripts/frontal_figures.py

figures-clean:
	@rm -f $(FIGDIR)/tract-*.svg

## tutorial: regenerate docs/tutorial.md by running every example in it
# The prose is written in docs/tutorial.src.md; every value in the page is
# produced by executing the call beside it. PYTHONHASHSEED is pinned for the
# same reason it is pinned for invariants.py -- `check` compares bytes.
tutorial:
	@PYTHONHASHSEED=0 $(PYTHON) scripts/tutorial.py build markdown

## tutorial-basics: regenerate the executable newcomer tutorial
tutorial-basics:
	@PYTHONHASHSEED=0 $(PYTHON) scripts/tutorial.py build basics

## notebook: regenerate the tutorial notebook that ships in the package
# The same source and the same parse as `tutorial`, emitted as cells with no
# results in them. Nothing runs, so there is no seed to pin.
notebook:
	@$(PYTHON) scripts/tutorial.py build notebook

## house-style: regenerate the declaration exhibits in the conventions page
house-style:
	@$(PYTHON) scripts/house_style.py generate --write

## perceptual-validation: regenerate the Miller-Nicely comparison exhibits
perceptual-validation:
	@PYTHONHASHSEED=0 $(PYTHON) scripts/perceptual_validation.py generate --write

## state-of-work: regenerate the index of design verdicts and superseded findings
state-of-work:
	@$(PYTHON) scripts/state_of_work.py generate --write

## lint: the style gates; needs the `lint` extra (ruff / black / mypy)
lint:
	@$(PYTHON) -m ruff check .
	@$(PYTHON) -m black --check .
	@$(PYTHON) -m mypy

## PYTEST_WORKERS: how many processes the suite runs in.
# A share of the cores rather than all of them, because this checkout is
# usually being worked by more than one agent and each of them runs this same
# suite. xdist's 'auto' is one worker per core, which is right for the only
# job on the box and wrong for any other number: two 'auto' suites on twelve
# cores is twenty-four runnable processes, and the box has been seen at a load
# average of 81. Niceness does not help there -- every competitor is equally
# nice, so they simply thrash each other. A quarter of the cores lets four
# suites run without oversubscribing, which is the number of lanes this
# program actually keeps in flight.
#
# Set PYTEST_WORKERS=auto for a deliberate solo run when you want the wall
# clock and know nothing else is running, or 0 to run serially -- useful when
# a failure needs a readable traceback.
CORES := $(shell getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)
PYTEST_WORKERS ?= $(shell expr $(CORES) / 4 \| 1)
# '-n 0' rather than an empty flag: the cap also lives in pyproject's addopts,
# so serial mode has to override it explicitly instead of falling through.
PYTEST_N = $(if $(filter 0,$(PYTEST_WORKERS)),-n 0,-n $(PYTEST_WORKERS))

## NICE: what the suite is run under.
# The default yields the CPU, because this checkout is often worked on by
# several agents at once and by whoever else is on the box; xdist takes every
# core it is given, so a suite that does not yield starves the others and they
# starve it back. Yielding costs the runner wall-clock only when something else
# wants the cores, and costs it nothing when nothing does. Set NICE= to run at
# normal priority.
NICE ?= nice -n 19

## check: the gates a release runs
# lint is a prerequisite rather than a recipe line so it fails in seconds,
# before the suite spends a minute earning the same verdict.
# Every step yields, not just the suite: the checks after it walk the corpus
# and re-render the tutorial, which is minutes of CPU that used to run at
# normal priority while the niced suite it followed had been polite.
gate-subject:
	@$(PYTHON) -m scripts.gate_subject

check: gate-subject lint
	@$(NICE) $(PYTHON) -m pytest -q $(PYTEST_N)
	@$(PYTHON) -m scripts.gate_subject
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/piece1_oracle.py check
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/piece1_oracle.py prove
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/containment_oracle.py
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/consolidation_parity.py check
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/invariants.py
	@$(NICE) $(PYTHON) scripts/confusion.py validate
	@$(NICE) $(PYTHON) scripts/xsampa_table.py validate
	@$(NICE) $(PYTHON) scripts/house_style.py check
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/perceptual_validation.py check
	@$(NICE) $(PYTHON) scripts/state_of_work.py check
	@$(MAKE) --no-print-directory espeak-vocabularies-check
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/tutorial.py check all
	@PYTHONHASHSEED=0 $(NICE) $(PYTHON) scripts/docexamples.py
	@$(NICE) $(PYTHON) scripts/docquotes.py
	@$(PYTHON) -m scripts.gate_subject

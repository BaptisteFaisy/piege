# Makefile — gestes courts du projet Piège.
# Aucun paquet tiers n'est requis pour `make ci` (stdlib + pytest).
PYTHON ?= python3
export PYTHONPATH := src

.PHONY: ci test gardes catalogue demo rapport demo-reel demo-libre site jury clean aide

aide:
	@echo "make ci        - gardes + catalogue + tests (ce que la CI exécute)"
	@echo "make test      - tests seuls (pytest si présent, sinon lanceur stdlib)"
	@echo "make gardes    - taille des fichiers/fonctions + cohérence du catalogue"
	@echo "make catalogue - liste les 60 techniques et la couverture par famille"
	@echo "make demo      - campagne de démonstration sur la cible Guichet RH (local)"
	@echo "make rapport   - rapport FR + EN de la dernière campagne locale"
	@echo "make jury      - dossier complet pour le jury (campagne, rapports, clôture, preuves)"
	@echo "make demo-reel - rejoue une campagne RÉELLE enregistrée (0 appel, 0 €)"
	@echo "make demo-libre - UNE vraie réponse de modèle, en direct, gratuite (0 €)"
	@echo "make site       - reconstruit l'état complet du site de démo (reproductible)"

ci: gardes test

test:
	@if $(PYTHON) -m pytest --version >/dev/null 2>&1; then \
		$(PYTHON) -m pytest -q; \
	else \
		$(PYTHON) scripts/lance_tests.py; \
	fi

gardes:
	@$(PYTHON) scripts/gardes/tailles.py
	@$(PYTHON) -m piege.catalogue.valideur catalogue

catalogue:
	@$(PYTHON) -m piege.catalogue.valideur catalogue --resume

demo:
	@$(PYTHON) -m piege.cli demo --graine 20261111

rapport:
	@$(PYTHON) -m piege.cli rapport --derniere --langues fr,en

demo-reel:
	@$(PYTHON) scripts/jury/demo-reel.py

demo-libre:
	@$(PYTHON) scripts/demo-libre.py

site:
	@$(PYTHON) scripts/jury/site.py

jury:
	@$(PYTHON) scripts/jury/dossier.py

clean:
	@find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	@rm -rf .pytest_cache preuves-locales dossier-jury demo-reel.md

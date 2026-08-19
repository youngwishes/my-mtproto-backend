.PHONY: test docs-check test-e2e

test:
	cd src && python manage.py test --settings=config.test_settings $(ARGS)

docs-check:
	python scripts/check_docs_boundaries.py
	python -m unittest scripts.tests.test_check_docs_boundaries

# e2e (бот → бэкенд → VDS). Требует локального backend-стека и тестового VDS API.
# Контейнеры НЕ поднимает — см. integration_tests/README.md.
# По умолчанию весь каталог; ARGS переопределяет цель, напр.:
#   make test-e2e ARGS="integration_tests/test_my_servers.py -v"
test-e2e:
	.venv-integration/bin/pytest $(if $(ARGS),$(ARGS),integration_tests)

test:
	cd src && python manage.py test --settings=config.test_settings $(ARGS)

# e2e (бот → бэкенд → VDS). Требует поднятого локального стека и живого VDS.
# Контейнеры НЕ поднимает — см. integration_tests/README.md.
# По умолчанию весь каталог; ARGS переопределяет цель, напр.:
#   make test-e2e ARGS="integration_tests/test_my_servers.py -v"
test-e2e:
	.venv-integration/bin/pytest $(if $(ARGS),$(ARGS),integration_tests)

test:
	cd src && python manage.py test --settings=config.test_settings $(ARGS)

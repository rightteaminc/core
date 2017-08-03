help:
	@echo "TODO: Write the install help"

clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

install:
	pip install -Ur requirements.txt
	@echo "Requirements installed."


unit:
	nosetests -sv -a is_unit --with-yanc --logging-level=ERROR

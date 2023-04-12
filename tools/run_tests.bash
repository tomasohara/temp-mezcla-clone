#!/bin/bash
#
# Run unitests and pytest files
# and generate coverage report
#
# Usage:
# $ ./tools/run_tests.bash
# $ ./tools/run_tests.bash --coverage
#

tools=$(dirname $(realpath -s $0))
base=$tools/..
mezcla=$base/mezcla
tests=$mezcla/tests

echo -e "Running tests on $tests\n"

pip uninstall mezcla &> /dev/null # Avoid conflicts with installed Mezcla

export PYTHONPATH="$mezcla/:$PYTHONPATH"

# Run with coverage enabled
if [ "$1" == "--coverage" ]; then
    export COVERAGE_RCFILE="$base/.coveragerc"
    export CHECK_COVERAGE='true'
    coverage erase
    coverage run -m pytest $tests
    coverage combine
    coverage html
else
    pytest $tests
fi

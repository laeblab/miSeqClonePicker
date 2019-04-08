#!/bin/bash

set -o nounset # Fail on unset variables
set -o errexit # Fail on uncaught non-zero returncodes
set -o pipefail # Fail is a command in a chain of pipes fails

#~/scratch/laebgroup/styrko/styrko/bin/mypy --ignore-missing-imports --follow-imports=silent --strict-optional --disallow-untyped-defs --disallow-untyped-calls --disallow-incomplete-defs -- $@
~/scratch/laebgroup/styrko/styrko/bin/mypy --strict-optional --disallow-untyped-defs --disallow-untyped-calls --disallow-incomplete-defs $@

#
# Test isothermal submodel
#

import pybamm
import tests
import unittest

from tests.unit.test_models.test_submodels.test_thermal.coupled_variables import (
    coupled_variables,
)


class TestCurrentCollector2D(unittest.TestCase):
    def test_public_functions(self):
        param = pybamm.standard_parameters_lithium_ion
        i_boundary_cc = pybamm.PrimaryBroadcast(pybamm.Scalar(1), ["current collector"])
        coupled_variables.update({"Current collector current density": i_boundary_cc})

        submodel = pybamm.thermal.isothermal.CurrentCollector2D(param)
        std_tests = tests.StandardSubModelTests(submodel, coupled_variables)
        std_tests.test_all()


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    pybamm.settings.debug_mode = True
    unittest.main()

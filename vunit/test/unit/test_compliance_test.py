# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2019, Lars Asplund lars.anders.asplund@gmail.com

"""
Test the compliance test.
"""

from unittest import TestCase
from shutil import rmtree
from os.path import exists, dirname, join, abspath
from itertools import product
from vunit.ostools import renew_path
from vunit import ComplianceTest
from vunit import VUnit


class TestComplianceTest(TestCase):
    """Tests the ComplianceTest class."""

    def setUp(self):
        self.tmp_dir = join(dirname(__file__), "vc_tmp")
        renew_path(self.tmp_dir)
        self.vc_contents = """
library ieee
use ieee.std_logic_1164.all;

entity vc is
  generic(vc_h : vc_handle_t);
  port(
    a, b : in std_logic;
    c : in std_logic := '0';
    d, e : inout std_logic;
    f, g : inout std_logic := '1';
    h, i : out std_logic := '0';
    j : out std_logic);

end entity;
"""
        self.vc_path = self.make_file(join(self.tmp_dir, "vc.vhd"), self.vc_contents)

        self.vci_contents = """
package vc_pkg is
  impure function new_vc(
    logger : logger_t := vc_logger;
    actor : actor_t := null_actor;
    checker : checker_t := null_checker;
    fail_on_unexpected_msg_type : boolean := true
  ) return vc_handle_t;
end package;
"""
        self.vci_path = self.make_file(join(self.tmp_dir, "vci.vhd"), self.vci_contents)

        self.ui = VUnit.from_argv([])

        self.vc_lib = self.ui.add_library("vc_lib")
        self.vc_lib.add_source_files(join(self.tmp_dir, "*.vhd"))

    def tearDown(self):
        if exists(self.tmp_dir):
            rmtree(self.tmp_dir)

    def make_file(self, file_name, contents):
        """
        Create a file in the temporary directory with contents
        Returns the absolute path to the file.
        """
        full_file_name = abspath(join(self.tmp_dir, file_name))
        with open(full_file_name, "w") as outfile:
            outfile.write(contents)
        return full_file_name

    def test_not_finding_vc(self):
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "other_vc", "vc_pkg"
        )

    def test_not_finding_vci(self):
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "vc", "other_vc_pkg"
        )

    def test_evaluating_vc_generics(self):
        vc1_contents = """
entity vc1 is
end entity;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vc1.vhd"), vc1_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc1", "vc_pkg")

        vc2_contents = """
entity vc2 is
  generic(a : bit; b : bit);
end entity;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vc2.vhd"), vc2_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc2", "vc_pkg")

        vc3_contents = """
entity vc3 is
  generic(a, b : bit);
end entity;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vc3.vhd"), vc3_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc3", "vc_pkg")

    def test_failing_with_no_constructor(self):
        vci_contents = """\
package other_vc_pkg is
  impure function create_vc return vc_handle_t;
end package;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "other_vci.vhd"), vci_contents)
        )
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "vc", "other_vc_pkg"
        )

    def test_failing_with_wrong_constructor_return_type(self):
        vci_contents = """\
package other_vc_pkg is
  impure function new_vc return vc_t;
end package;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "other_vci.vhd"), vci_contents)
        )
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "vc", "other_vc_pkg"
        )

    def test_failing_on_incorrect_constructor_parameters(self):
        parameters = dict(
            logger=("logger_t", "default_logger"),
            actor=("actor_t", "default_actor"),
            checker=("checker_t", "default_checker"),
            fail_on_unexpected_msg_type=("boolean", "true"),
        )
        reasons_for_failure = [
            "missing_parameter",
            "invalid_type",
            "missing_default_value",
        ]

        for iteration, (invalid_parameter, invalid_reason) in enumerate(
            product(parameters, reasons_for_failure)
        ):
            vci_contents = (
                """\
package other_vc_%d_pkg is
  impure function new_vc(
"""
                % iteration
            )
            for parameter_name, parameter_data in parameters.items():
                if parameter_name != invalid_parameter:
                    vci_contents += "    %s : %s := %s;\n" % (
                        parameter_name,
                        parameter_data[0],
                        parameter_data[1],
                    )
                elif invalid_reason == "invalid_type":
                    vci_contents += "    %s : invalid_type := %s;\n" % (
                        parameter_name,
                        parameter_data[1],
                    )
                elif invalid_reason == "missing_default_value":
                    vci_contents += "    %s : %s;\n" % (
                        parameter_name,
                        parameter_data[0],
                    )

            vci_contents = (
                vci_contents[:-2]
                + """
  ) return vc_handle_t;
end package;
"""
            )
            self.vc_lib.add_source_file(
                self.make_file(
                    join(self.tmp_dir, "other_vci_%d.vhd" % iteration), vci_contents
                )
            )
            self.assertRaises(
                RuntimeError,
                ComplianceTest,
                self.vc_lib,
                "vc",
                "other_vc_%d_pkg" % iteration,
            )

    def test_adding_vhdl_testbench(self):
        compliance_test = ComplianceTest(self.vc_lib, "vc", "vc_pkg")
        vc_test_lib = self.ui.add_library("vc_test_lib")
        compliance_test.add_vhdl_testbench(
            vc_test_lib, join(self.tmp_dir, "compliance_test")
        )

        self.assertTrue(
            exists(join(self.tmp_dir, "compliance_test", "tb_vc_compliance.vhd"))
        )
        self.assertRaises(
            RuntimeError,
            compliance_test.add_vhdl_testbench,
            vc_test_lib,
            join(self.tmp_dir, "compliance_test"),
        )

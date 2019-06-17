# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2019, Lars Asplund lars.anders.asplund@gmail.com

"""
Module for generating a compliance test for a VUnit verification component
"""

from os import mkdir
from os.path import exists, join
from string import Template
from vunit.vhdl_parser import VHDLDesignFile, VHDLFunctionSpecification


class ComplianceTest(object):
    """
    Represents the compliance test for a VUnit verification component
    """

    def __init__(self, vc_lib, vc_name, vci_name):
        self.vc_name = vc_name
        self.vci_name = vci_name
        self.vc_lib = vc_lib

        self._validate_vc()
        self._validate_vci()

    def _validate_vc(self):
        """Validates the existence and contents of the verification component."""
        try:
            vc_source_file = self.vc_lib.get_entity(self.vc_name).source_file
        except KeyError:
            raise RuntimeError("Failed to find VC %s" % self.vc_name)

        with open(vc_source_file.name) as fptr:
            self.vc_code = VHDLDesignFile.parse(fptr.read())
            for entity in self.vc_code.entities:
                if entity.identifier == self.vc_name:
                    self.vc_entity = entity
                    break
            else:
                raise RuntimeError(
                    "Failed to find VC %s in %s" % (self.vc_name, fptr.name)
                )

            if len(self.vc_entity.generics) != 1:
                raise RuntimeError("%s must have a single generic")

            self.vc_handle_t = self.vc_entity.generics[0].subtype_indication.type_mark

    def _validate_vci(self):
        """Validates the existence and contents of the verification component interface."""

        def create_error_messages(required_parameter_types):
            error_messages = [
                "Failed to find constructor function starting with new_",
                "Found constructor function starting with new_ but not with the correct return type %s"
                % (self.vc_handle_t),
            ]

            for parameter_name, parameter_type in required_parameter_types.items():
                error_messages.append(
                    "Found constructor function but %s parameter is missing"
                    % (parameter_name)
                )
                error_messages.append(
                    "Found constructor function but %s parameter is not of type %s"
                    % (parameter_name, parameter_type)
                )
                error_messages.append(
                    "Found constructor function but %s parameter is missing a default value"
                    % (parameter_name)
                )

            return error_messages

        try:
            vci_source_file = self.vc_lib.package(self.vci_name).source_file
        except KeyError:
            raise RuntimeError("Failed to find VCI %s" % self.vci_name)

        with open(vci_source_file.name) as fptr:
            code = fptr.read()

            required_parameter_types = dict(
                logger="logger_t",
                actor="actor_t",
                checker="checker_t",
                fail_on_unexpected_msg_type="boolean",
            )

            error_messages = create_error_messages(required_parameter_types)
            message_idx = 0
            for func in VHDLFunctionSpecification.find(code):
                if not func.identifier.startswith("new_"):
                    continue
                message_idx = max(message_idx, 1)

                if func.return_type_mark != self.vc_handle_t:
                    continue
                message_idx = max(message_idx, 2)

                parameters = {}
                for parameter in func.parameter_list:
                    for identifier in parameter.identifier_list:
                        parameters[identifier] = parameter

                step = 3
                for parameter_name, parameter_type in required_parameter_types.items():
                    if parameter_name not in parameters:
                        break
                    message_idx = max(message_idx, step)
                    step += 1

                    if (
                        parameters[parameter_name].subtype_indication.type_mark
                        != parameter_type
                    ):
                        break
                    message_idx = max(message_idx, step)
                    step += 1

                    if not parameters[parameter_name].init_value:
                        break
                    message_idx = max(message_idx, step)
                    step += 1

                if step == len(error_messages) + 1:
                    self.vc_constructor = func
                    break
            else:
                raise RuntimeError(error_messages[message_idx])

    def add_vhdl_testbench(self, vc_test_lib, test_dir):
        """Generates a VHDL compliance testbench in test_dir and adds it to vc_test_lib."""

        try:
            vc_test_lib.test_bench("tb_%s_compliance" % self.vc_entity.identifier)
            raise RuntimeError(
                "tb_%s_compliance already exists in %s"
                % (self.vc_entity.identifier, vc_test_lib.name)
            )
        except KeyError:
            pass

        if not exists(test_dir):
            mkdir(test_dir)

        tb_path = join(test_dir, "tb_%s_compliance.vhd" % self.vc_entity.identifier)
        with open(tb_path, "w") as fptr:
            fptr.write(self.create_vhdl_testbench())

        tb_file = vc_test_lib.add_source_file(tb_path)
        testbench = vc_test_lib.test_bench(
            "tb_%s_compliance" % self.vc_entity.identifier
        )
        test = testbench.test("Test that the actor can be customised")
        test.set_generic("use_custom_actor", True)

        test = testbench.test("Test unexpected message handling")
        for fail_on_unexpected_msg_type in [False, True]:
            test.add_config(
                name="fail_on_unexpected_msg_type=%s"
                % str(fail_on_unexpected_msg_type),
                generics=dict(
                    fail_on_unexpected_msg_type=fail_on_unexpected_msg_type,
                    use_custom_logger=True,
                    use_custom_actor=True,
                ),
            )

        return tb_file

    def create_vhdl_testbench(self):
        """Returns a VHDL compliance testbench."""

        entity_name = self.vc_entity.identifier

        library_names = set()
        context_items = "library %s;\n" % self.vc_lib.name
        context_items += "use %s.%s.all;\n" % (self.vc_lib.name, self.vci_name)
        for ref in self.vc_code.references:
            if ref.is_package_reference() or ref.is_context_reference():
                if ref.library_name != "work":
                    if ref.library_name not in library_names:
                        library_names.add(ref.library_name)
                        context_items = (
                            "library %s;\n" % ref.library_name + context_items
                        )

                library_name = (
                    ref.library_name if ref.library_name != "work" else self.vc_lib.name
                )

                if ref.is_context_reference():
                    context_items += "context %s.%s;\n" % (
                        library_name,
                        ref.design_unit_name,
                    )

                if ref.is_package_reference():
                    context_items += "use %s.%s.%s;\n" % (
                        library_name,
                        ref.design_unit_name,
                        ref.name_within,
                    )

        signal_declarations = ""
        port_mappings = ""
        for port in self.vc_entity.ports:
            if (port.mode == "in" or port.mode == "inout") and port.init_value is None:
                signal_declarations += "  signal %s : %s;\n" % (
                    ", ".join(port.identifier_list),
                    port.subtype_indication,
                )
                for identifier in port.identifier_list:
                    port_mappings += "      %s => %s,\n" % (identifier, identifier)
            else:
                for identifier in port.identifier_list:
                    port_mappings += "      %s => open,\n" % identifier

        vc_instantiation = """  vc_inst: entity %s.%s
    generic map(%s);
""" % (
            self.vc_lib.name,
            entity_name,
            self.vc_entity.generics[0].identifier_list[0],
        )

        if len(self.vc_entity.ports) > 0:
            vc_instantiation = (
                vc_instantiation[:-2]
                + """
    port map(
"""
            )

            vc_instantiation += port_mappings[:-2] + "\n    );\n"

        tb_template = Template(
            """${context_items}
entity tb_${entity_name}_compliance is
  generic(
    use_custom_logger : boolean := false;
    use_custom_actor : boolean := false;
    fail_on_unexpected_msg_type : boolean := true;
    runner_cfg : string);
end entity;

architecture tb of tb_${entity_name}_compliance is
  constant custom_actor : actor_t := new_actor("vc", inbox_size => 1);
  constant custom_logger : logger_t := get_logger("vc");

  impure function create_handle return ${vc_handle_t} is
    variable handle : ${vc_handle_t};
    variable logger : logger_t := null_logger;
    variable actor : actor_t := null_actor;
  begin
    if use_custom_logger then
      logger := custom_logger;
    end if;

    if use_custom_actor then
      actor := custom_actor;
    end if;

    return ${vc_constructor_name}(
      logger => logger,
      actor => actor,
      fail_on_unexpected_msg_type => fail_on_unexpected_msg_type);
  end;

  constant ${vc_handle_name} : ${vc_handle_t} := create_handle;
  constant unexpected_msg : msg_type_t := new_msg_type("unexpected msg");

${signal_declarations}
begin
  main : process
    variable t_start : time;
    variable msg : msg_t;
  begin
    test_runner_setup(runner, runner_cfg);

    while test_suite loop

      if run("Test that sync interface is supported") then
        t_start := now;
        wait_for_time(net, as_sync(${vc_handle_name}), 1 ns);
        wait_for_time(net, as_sync(${vc_handle_name}), 2 ns);
        wait_for_time(net, as_sync(${vc_handle_name}), 3 ns);
        check_equal(now - t_start, 0 ns);
        t_start := now;
        wait_until_idle(net, as_sync(${vc_handle_name}));
        check_equal(now - t_start, 6 ns);

      elsif run("Test that the actor can be customised") then
        t_start := now;
        wait_for_time(net, as_sync(${vc_handle_name}), 1 ns);
        wait_for_time(net, as_sync(${vc_handle_name}), 2 ns);
        check_equal(now - t_start, 0 ns);
        wait_for_time(net, as_sync(${vc_handle_name}), 3 ns);
        check_equal(now - t_start, 1 ns);
        wait_until_idle(net, as_sync(${vc_handle_name}));
        check_equal(now - t_start, 6 ns);

      elsif run("Test unexpected message handling") then
        mock(custom_logger);
        msg := new_msg(unexpected_msg);
        send(net, custom_actor, msg);
        wait for 1 ns;
        if fail_on_unexpected_msg_type then
          check_only_log(custom_logger, "Got unexpected message unexpected msg", failure);
        else
          check_no_log;
        end if;
        unmock(custom_logger);
      end if;

    end loop;

    test_runner_cleanup(runner);
  end process;

${vc_instantiation}
end architecture;
"""
        )

        return tb_template.substitute(
            context_items=context_items,
            entity_name=entity_name,
            vc_constructor_name=self.vc_constructor.identifier,
            signal_declarations=signal_declarations,
            vc_handle_name=self.vc_entity.generics[0].identifier_list[0],
            vc_handle_t=self.vc_handle_t,
            vc_instantiation=vc_instantiation,
        )

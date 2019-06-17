-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this file,
-- You can obtain one at http://mozilla.org/MPL/2.0/.
--
-- Copyright (c) 2014-2019, Lars Asplund lars.anders.asplund@gmail.com

library vunit_lib;
context vunit_lib.vunit_context;
context vunit_lib.com_context;
context vunit_lib.vc_context;

package vc_not_supporting_custom_logger_pkg is
  type vc_not_supporting_custom_logger_handle_t is record
    p_actor : actor_t;
    p_logger : logger_t;
    p_checker : checker_t;
    p_fail_on_unexpected_msg_type : boolean;
  end record;

  constant vc_not_supporting_custom_logger_logger : logger_t := get_logger("vc_not_supporting_custom_logger");
  constant vc_not_supporting_custom_logger_checker : checker_t := new_checker(vc_not_supporting_custom_logger_logger);

  impure function new_vc_not_supporting_custom_logger(
    logger : logger_t := vc_not_supporting_custom_logger_logger;
    actor : actor_t := null_actor;
    checker : checker_t := null_checker;
    fail_on_unexpected_msg_type : boolean := true
  ) return vc_not_supporting_custom_logger_handle_t;

  impure function as_sync(
    vc_h : vc_not_supporting_custom_logger_handle_t
  ) return sync_handle_t;

end package;

package body vc_not_supporting_custom_logger_pkg is
  impure function new_vc_not_supporting_custom_logger(
    logger : logger_t := vc_not_supporting_custom_logger_logger;
    actor : actor_t := null_actor;
    checker : checker_t := null_checker;
    fail_on_unexpected_msg_type : boolean := true
  ) return vc_not_supporting_custom_logger_handle_t is
    variable p_actor : actor_t;
    variable p_checker : checker_t;
  begin
    if actor = null_actor then
      p_actor := new_actor;
    else
      p_actor := actor;
    end if;

    if checker = null_checker then
      if logger = vc_not_supporting_custom_logger_logger then
        p_checker := vc_not_supporting_custom_logger_checker;
      else
        p_checker := new_checker(logger);
      end if;
    else
      p_checker := checker;
    end if;

    return (
      p_logger => vc_not_supporting_custom_logger_logger,
      p_actor => p_actor,
      p_checker => p_checker,
      p_fail_on_unexpected_msg_type => fail_on_unexpected_msg_type
    );
  end;

  impure function as_sync(
    vc_h : vc_not_supporting_custom_logger_handle_t
  ) return sync_handle_t is
  begin
    return vc_h.p_actor;
  end;

end package body;


import re

from virttest import error_context


@error_context.context_aware
def run(test, params, env):
    """
    Install cygwin env for windwos guest:

    1) Install cygwin in guest
    2) Verify cygwin install

    :param test: QEMU test object
    :param params: Dictionary with the test parameters
    :param env: Dictionary with test environment.
    """
    cygwin_install_cmd = params.get("cygwin_install_cmd")
    cygwin_prompt = params.get("cygwin_prompt", r"\$\s+$")
    cygwin_start = params.get("cygwin_start")
    cygwin_verify_cmd = params.get("cygwin_verify_cmd", "ls")
    cygwin_install_timeout = float(params.get("cygwin_install_timeout", "2400"))
    timeout = float(params.get("login_timeout", 240))
    cdrom_check_cmd = params.get("cdrom_check")
    cdrom_filter = params.get("cdrom_filter")

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    error_context.context("Install cygwin in guest")
    session = vm.wait_for_login(timeout=timeout)
    output = session.cmd_output(cdrom_check_cmd, timeout)
    cdrom = re.findall(cdrom_filter, output)
    if cdrom:
        cygwin_install_cmd = re.sub("WINUTILS", cdrom[0], cygwin_install_cmd)
    else:
        test.error("Can not find tools iso in guest")

    session.cmd(cygwin_install_cmd, timeout=cygwin_install_timeout)

    error_context.context("Verify cygwin install")
    old_prompt = session.prompt
    session.set_prompt(cygwin_prompt)
    session.cmd_output(cygwin_start)
    session.cmd_output(cygwin_verify_cmd)

    session.set_prompt(old_prompt)
    session.cmd_output("exit")
    session.close()

import os

from avocado.utils import process
from virttest import error_context
from virttest import env_process


@error_context.context_aware
def run(test, params, env):
    """
    Qemu sev basic test on Milan and above host:
    1. Check host sev capability
    2. Generate dhcert and session files
    3. Boot sev VM with dhcert
    4. Verify sev enabled

    :param test: QEMU test object
    :param params: Dictionary with the test parameters
    :param env: Dictionary with test environment.
    """
    error_context.context("Start sev test", test.log.info)
    timeout = float(params.get("login_timeout", 240))

    try:
        output = process.system_output(params["sev_enable_check"], shell=True)
        error_context.context("Host sev capabilities: %s" % output,
                              test.log.info)
    except Exception as e:
        test.cancel("Host sev capability check fail: %s" % e)
    sev_tool_pkg = params.get("sev_tool_pkg")
    s, o = process.getstatusoutput("rpm -qa | grep %s" % sev_tool_pkg,
                                   shell=True)
    if s != 0:
        try:
            process.run("yum -y install %s" % sev_tool_pkg, shell=True)
        except Exception as e:
            test.cancel("Fail to install package %s: %s" % (sev_tool_pkg, e))

    vm_name = params["main_vm"]
    try:
        process.system_output("sevctl export --full vm.chain", shell=True)
        process.system_output("sevctl session --name " + vm_name +
                              " vm.chain " + params["vm_sev_policy"],
                              shell=True)
        params["vm_sev_dh_cert_file"] = os.path.abspath("%s_godh.b64"
                                                        % vm_name)
        params["vm_sev_session_file"] = os.path.abspath("%s_session.b64"
                                                        % vm_name)
    except Exception as e:
        test.fail("Insert guest dhcert and session blob failed, %s" % e)

    env_process.preprocess_vm(test, params, env, vm_name)
    vm = env.get_vm(vm_name)
    vm.create()
    vm.verify_alive()
    session = vm.wait_for_login(timeout=timeout)
    vm.monitor.query_sev_launch_measure()
    try:
        session.cmd_output(params["sev_enable_check"], timeout=240)
    except Exception as e:
        test.cancel("Guest sev verify fail: %s" % e)
    session.close()
    vm.destroy()

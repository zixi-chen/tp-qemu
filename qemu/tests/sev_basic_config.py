from avocado.utils import process
from virttest import error_context
from virttest.utils_misc import verify_dmesg


@error_context.context_aware
def run(test, params, env):
    """
    Qemu sev basic test on Milan and above host:
    1. Check host sev capability
    2. Boot sev VM
    3. Verify sev enabled in guest
    4. Check sev qmp cmd

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

    vms = params.objects("vms")
    for vm_name in vms:
        vm = env.get_vm(vm_name)
        vm.verify_alive()
        session = vm.wait_for_login(timeout=timeout)
        verify_dmesg()
        vm_policy = int(params["vm_sev_policy_%s" % vm_name])
        if vm_policy <= 3:
            params["sev_keyword"] = "sev"
        try:
            session.cmd_output(params["sev_enable_check"], timeout=240)
        except Exception as e:
            test.cancel("Guest sev verify fail: %s" % e)
        sev_guest_info = vm.monitor.query_sev()
        if sev_guest_info["policy"] != vm_policy:
            test.fail("QMP sev policy doesn't match.")
        else:
            error_context.context("QMP sev policy matches", test.log.info)
        session.close()

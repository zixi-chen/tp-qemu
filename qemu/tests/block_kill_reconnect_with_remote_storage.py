import logging
import re
import time
import os

from virttest import error_context

from avocado.utils import process


@error_context.context_aware
def run(test, params, env):
    """
    Test kill/reconnect of block devices.

    1) Boot up guest with a data disk.
    2) Do I/O on data disk
    3) Kill nbd export image process.
    4) Apply a firewall on nbd data disk's port
    5) Check guest system disk function
    6) Drop the firewall
    7) Export the nbd data disk image
    8) Do I/O on data disk

    :param test:   QEMU test object.
    :param params: Dictionary with the test parameters.
    :param env:    Dictionary with test environment.
    """

    def get_disk_storage_name(system_disk_cmd, data_disk_cmd):
        """
        get data disk name
        return: data disk name e.g. /dev/sdb
        """
        error_context.context(
            "Identify data disk.", logging.info)
        session = vm.wait_for_login(timeout=timeout)
        system_disk_name = session.cmd(system_disk_cmd,
                                       timeout=disk_op_timeout).strip()
        find_disk_cmd = data_disk_cmd % system_disk_name
        data_disk_name = session.cmd(find_disk_cmd,
                                     timeout=disk_op_timeout).strip()
        logging.info('The data disk is %s' % data_disk_name)
        session.close()
        return system_disk_name, data_disk_name

    def run_io_test(test_disk):
        """ Run io test on given disks. """
        error_context.context(
            "Run io test on %s." % test_disk, logging.info)
        session = vm.wait_for_login(timeout=timeout)
        test_cmd = disk_op_cmd % (test_disk, test_disk)
        session.cmd(test_cmd, timeout=disk_op_timeout)
        session.close()

    def save_data_img_process(nbd_port_data):
        """
        Save data disk image export process cmd.
        :param nbd_port_data: port number
        return: export data disk cmd
        """
        save_pid_cmd = save_export_data_img_cmd % nbd_port_data
        result = process.run(save_pid_cmd, ignore_status=True, shell=True)
        if result.exit_status != 0:
            test.error('command error: %s' % result.stderr.decode())
        logging.info(result.stdout_text)
        result_cmd = re.split(r'\d{2}:\d{2}:\d{2} ',
                              result.stdout_text)[1].strip()
        return result_cmd

    def kill_data_disk(nbd_port_data):
        error_context.context(
            "Kill nbd data disks %s." % nbd_port_data, logging.info)
        kill_pid_cmd = find_data_disk_pid_cmd % nbd_port_data
        result = process.run(kill_pid_cmd, ignore_status=True, shell=True)
        if result.exit_status != 0:
            test.error('command error: %s' % result.stderr.decode())

    def run_iptables(cmd):
        result = process.run(cmd, ignore_status=True, shell=True)
        if result.exit_status != 0:
            logging.error('command error: %s' % result.stderr.decode())

    def break_net_with_iptables():
        run_iptables(params['net_break_cmd'])
        net_down = True

    def resume_net_with_iptables():
        run_iptables(params['net_resume_cmd'])
        net_down = False

    def reconnect_loop_io(test_disk):
        error_context.context(
            "Run IO test when in reconnecting loop", logging.info)
        for iteration in range(repeat_times):
            error_context.context("Wait %s seconds" % reconnect_time_wait,
                                  logging.info)
            time.sleep(reconnect_time_wait)
            run_io_test(test_disk)

    def export_data_img():
        logging.info("Resume to export nbd data disks.")
        logging.info("Run command: %s" % resume_export_img_cmd)
        result = os.system(resume_export_img_cmd)
        if result != 0:
            test.error('command error: %s' % result.stderr.decode())
        logging.info("Wait %s seconds" % reconnect_time_wait)
        time.sleep(reconnect_time_wait)

    def check_data_disk_resume(test_disk):
        error_context.context(
            "check data disk resumed", logging.info)
        for iteration in range(repeat_times):
            logging.info("Wait %s seconds" % reconnect_time_wait)
            time.sleep(reconnect_time_wait)
            run_io_test(test_disk)

    def clean_images(net_status):
        """
        recover nbd image access
        """
        if net_status:
            resume_net_with_iptables()

    disk_op_cmd = params.get("disk_op_cmd")
    disk_op_timeout = int(params.get("disk_op_timeout", 360))
    timeout = int(params.get("login_timeout", 360))
    save_export_data_img_cmd = params.get("save_export_data_img_cmd")
    find_data_disk_pid_cmd = params.get("find_data_disk_pid_cmd")
    find_data_disk_cmd = params.get("find_data_disk_cmd")
    find_system_disk_cmd = params.get("find_system_disk_cmd")
    nbd_port_data1 = params.get("nbd_port_data1")
    repeat_times = int(params.get("repeat_times"))
    reconnect_time_wait = int(params.get("reconnect_time_wait"))
    error_context.context(find_system_disk_cmd, logging.info)

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    disk_storage_name = get_disk_storage_name(find_system_disk_cmd,
                                              find_data_disk_cmd)
    system_disk = disk_storage_name[0]
    data_disk = disk_storage_name[1]
    if disk_op_cmd:
        run_io_test(data_disk)
    resume_export_img_cmd = save_data_img_process(nbd_port_data1)
    net_down = False
    kill_data_disk(nbd_port_data1)
    break_net_with_iptables()
    try:
        reconnect_loop_io(system_disk)
        export_data_img()
        resume_net_with_iptables()
        check_data_disk_resume(data_disk)
    except Exception:
        clean_images(net_down)
        raise

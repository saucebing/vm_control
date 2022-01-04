#!/usr/bin/python3
import os, sys, time, subprocess, tempfile, re
import client, timeit
from bidict import bidict
from collections import Counter
import pickle
import random
import paramiko

out_temp = [None] * 1024
fileno = [None] * 1024

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def exec_cmd(cmd, index = 0, wait = True, vm_id = 0):
    global out_temp, fileno
    print('[VM%d]: CMD: ' % vm_id, cmd)
    #out_temp = tempfile.SpooledTemporaryFile(bufsize=1000 * 1000)
    out_temp[index] = tempfile.SpooledTemporaryFile()
    fileno[index] = out_temp[index].fileno()
    p1 = subprocess.Popen(cmd, stdout = fileno[index], stderr = fileno[index], shell=True)
    if wait:
        p1.wait()
    out_temp[index].seek(0)
    return p1

def parallel_cmd(cmd, num, wait = True):
    global out_temp, fileno
    p = []
    for i in range(0, num):
        out_temp[i] = tempfile.SpooledTemporaryFile()
        fileno[i] = out_temp[i].fileno()
        real_cmd = '%s %d' % (cmd, i)
        print('CMD: ', real_cmd)
        p.append(subprocess.Popen(real_cmd, stdout = fileno[i], stderr = fileno[i], shell=True))
    for i in range(0, num):
        if wait:
            p[i].wait()
        out_temp[i].seek(0)
    return p

def find_str(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[0]

def split_str(string):
    return filter(lambda x:x, string.split())

def b2s(s):
    return str(s, encoding = 'utf-8')

def get_res(index = 0):
    global out_temp, fileno
    return b2s(out_temp[index].read())

class VM:
    vm_name = ''
    vm_id = 0
    num_cores = 0
    ip = ''
    state = ''
    client = None
    port = 0

    def __init__(self, vm_id, vm_name):
        self.vm_id = vm_id
        self.vm_name = vm_name
        self.client = client.CLIENT()
        state = self.get_state()
        self.print(self.state)

    def print(self, *argc, **kwargs):
        print('[VM%d]:' % self.vm_id, *argc, **kwargs)

    def get_ip(self):
        cmd1 = '{"execute":"guest-network-get-interfaces"}'
        cmd = "virsh qemu-agent-command %s '%s'" % (self.vm_name, cmd1)
        exec_cmd(cmd, vm_id = self.vm_id)
        content = get_res()
        self.ip = find_str('(192\.168\.122\.[0-9]+)', content)
        self.print(self.ip)

    def get_state(self):     #running, shut off
        cmd = 'virsh dominfo --domain %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)
        content = get_res()
        self.state = find_str('State: (.*)', content).strip()
        self.num_cores = int(find_str('CPU\(s\): (.*)', content).strip())

    def set_port(self, port):
        self.port = port
        self.client.set_port(self.port)

    def connect(self):
        if self.state == 'running':
            self.get_ip()
        self.print('ip:', self.ip)
        self.client.set_ip(self.ip)
        self.client.connect()
        self.client.send('begin:0')

    def send(self, msg):
        self.client.send(msg)

    def client_close(self):
        self.client.client_close()

    def recv(self):
        return self.client.recv()

    def shutdown(self):
        if self.state == 'running':
            cmd = 'virsh shutdown %s' % self.vm_name
            exec_cmd(cmd, vm_id = self.vm_id)

    def start(self):
        if self.state == 'shut off':
            cmd = 'virsh start %s' % self.vm_name
            exec_cmd(cmd, vm_id = self.vm_id)

    def suspend(self):
        cmd = 'virsh suspend %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)

    def resume(self):
        cmd = 'virsh resume %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)

    def bind_core(self, vcpu, pcpu): #pcpu可以是0-143
        cmd = 'virsh vcpupin %s %s %s' % (self.vm_name, vcpu, pcpu)
        exec_cmd(cmd, vm_id = self.vm_id)

    def setvcpus_sta(self, n_vcpu): #set up when shutting down
        cmd = 'virsh setvcpus %s --maximum %d --config' % (self.vm_name, n_vcpu)
        exec_cmd(cmd, vm_id = self.vm_id)

    def setvcpus_dyn(self, n_vcpu):
        cmd = 'virsh setvcpus %s %d' % (self.vm_name, n_vcpu)
        exec_cmd(cmd, vm_id = self.vm_id)

    def setmem_sta(self, mem):
        cmd = 'virsh setmaxmem %s %dG --config' % (self.vm_name, mem)
        exec_cmd(cmd, vm_id = self.vm_id)

    def setmem_dyn(self, mem):
        cmd = 'virsh setmem %s %dG' % (self.vm_name, mem)
        exec_cmd(cmd, vm_id = self.vm_id)

class VMM:
    maps_vm_core = bidict()
    visited = []
    vms = []
    num_vms = 0
    record = []
    records = []
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.barnes', 'splash2x.lu_cb', 'splash2x.radiosity', 'splash2x.water_spatial', 'parsec.fluidanimate', 'parsec.freqmine', 'parsec.ferret']
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.barnes', 'splash2x.lu_cb', 'splash2x.radiosity', 'splash2x.water_spatial', 'parsec.fluidanimate', 'parsec.freqmine', 'parsec.ferret', 'parsec.blackscholes']
    #benchs = ['splash2x.ocean_ncp']
    #benchs = ['splash2x.raytrace', 'parsec.blackscholes', 'splash2x.water_spatial']
    benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.water_spatial']

    bench_id = 0
    run_index = 0
    N_MAX = 144

    def __init__(self):
        VMM.N_MAX = 144
        VMM.visited = [False] * VMM.N_MAX

    def new_vm(self, vm_id, vm_name):
        vm = VM(vm_id, vm_name)
        self.vms.append(vm)
        self.num_vms = len(self.vms)

    def set_mem(self, vm_id, mem):
        vm = self.vms[vm_id]
        vm.setmem_dyn(mem)

    def set_cores(self, vm_id, num_cores, begin_core = 0):
        cores = range(0, num_cores)
        for i in cores:
            for j in range(begin_core, VMM.N_MAX):
              if j % 2 == 0 and not VMM.visited[int(j / 2)]:
                  self.maps_vm_core[(vm_id, i)] = int(j / 2)
                  VMM.visited[int(j / 2)] = True
                  break
              elif j % 2 == 1 and not VMM.visited[int(j / 2) + 72]:
                  self.maps_vm_core[(vm_id, i)] = int(j / 2) + 72
                  VMM.visited[int(j / 2) + 72] = True
                  break
        print('maps_vm_core:', self.maps_vm_core)
        vm = self.vms[vm_id]
        vm.setvcpus_dyn(num_cores)
        vm.num_cores = num_cores
        for i in range(0, num_cores):
            vm.bind_core(i, self.maps_vm_core[(vm.vm_id, i)])

    def get_ipc(self):
        exec_cmd('pqos -t 1')
        res = get_res()
        #print(res)
        res = res.split('\n')
        ind = 0
        while not 'CORE' in res[ind]:
            ind += 1
        while not 'CORE' in res[ind]:
            ind += 1
        ipc = {}
        for (ind, line) in enumerate(res[ind + 1: ind + 37] + res[ind + 73: ind + 109]):
            aline = line.split()
            ipc[int(aline[0])] = float(aline[1])
        return ipc

    def get_freq(self):
        exec_cmd('turbostat -q -i 1 -n 1')
        res = get_res()
        #print(res)
        res = res.split('\n')
        ind = 0
        while not 'Package' in res[ind]:
            ind += 1
        freq_rea = {}
        freq_bsy = {}
        for (ind, line) in enumerate(res[ind + 2: ind + 74]):
            aline = line.split()
            freq_rea[int(aline[2])] = float(aline[3])
            freq_bsy[int(aline[2])] = float(aline[5])
        return [freq_rea, freq_bsy]

    def get_avg(self, freqs, num):
        freq_sum = {}
        for i in range(0, int(self.N_MAX / 4)):
            freq_sum[i] = 0
            freq_sum[i + 72] = 0
        for freq in freqs:
            for i in range(0, int(self.N_MAX / 4)):
                freq_sum[i] += freq[i];
                freq_sum[i + 72] += freq[i + 72];
        for i in range(0, int(self.N_MAX / 4)):
            freq_sum[i] /= num
            freq_sum[i + 72] /= num
        return freq_sum

    def get_ipcs():
        ipcs = []
        for i in range(0, num):
            ipc = self.get_ipc()
            ipcs.append(ipc)
        avg_ipc = self.get_avg(ipcs, num)
        return avg_ipc

    def get_freqs(self, num):
        freqs_rea = []
        freqs_bsy = []
        for i in range(0, num):
            freq = self.get_freq()
            freqs_rea.append(freq[0])
            freqs_bsy.append(freq[1])
        avg_freq_rea = self.get_avg(freqs_rea, num)
        avg_freq_bsy = self.get_avg(freqs_bsy, num)
        return [avg_freq_rea, avg_freq_bsy]

    def get_freqs_ipcs(self, num):
        freqs_rea = []
        freqs_bsy = []
        ipcs = []
        for i in range(0, num):
            freq = self.get_freq()
            ipc = self.get_ipc()
            freqs_rea.append(freq[0])
            freqs_bsy.append(freq[1])
            ipcs.append(ipc)
        avg_freq_rea = self.get_avg(freqs_rea, num)
        avg_freq_bsy = self.get_avg(freqs_bsy, num)
        avg_ipc = self.get_avg(ipcs, num)
        return [avg_freq_rea, avg_freq_bsy, avg_ipc]

    def vm_ipc(self, vm_id, ipc):
        vm = self.vms[vm_id]
        num_cores = vm.num_cores
        ipc_total = 0
        for id_core in range(0, num_cores):
            ipc_total += ipc[self.maps_vm_core[(vm_id, id_core)]]
        ipc_avg = ipc_total / num_cores
        return ipc_avg

    def vm_freq(self, vm_id, freq):
        vm = self.vms[vm_id]
        num_cores = vm.num_cores
        freq_total = 0
        for id_core in range(0, num_cores):
            freq_total += freq[self.maps_vm_core[(vm_id, id_core)]]
        freq_avg = freq_total / num_cores
        return freq_avg

    def vm_ipc2(self, vm_id, num):
        ipc = self.get_ipcs(num)
        print('ipc:', ipc)
        ipc_vm = self.vm_ipc(vm_id, ipc)
        self.vms[vm_id].print('ipc_vm: ', ipc_vm)
        return ipc_vm

    def vm_freq2(self, vm_id, num):
        freq = self.get_freqs(num)
        self.vms[vm_id].print('freq:', freq)
        freq_rea_vm = self.vm_freq(vm_id, freq[0])
        freq_bsy_vm = self.vm_freq(vm_id, freq[1])
        self.vms[vm_id].print('freq_vm: ', freq_rea_vm, freq_bsy_vm)
        return [freq_rea_vm, freq_bsy_vm]

    def vm_freq_ipc2(self, vm_id, num_sample, res):
        print('vm_id = ', vm_id)
        self.vms[vm_id].print('freq_rea, frea_bsy and ipc:', res)
        freq_rea_vm = self.vm_freq(vm_id, res[0])
        freq_bsy_vm = self.vm_freq(vm_id, res[1])
        ipc_vm = self.vm_ipc(vm_id, res[2])
        self.vms[vm_id].print('freq_rea_vm, freq_bsy_vm and ipc_vm is: ', freq_rea_vm, freq_bsy_vm, ipc_vm)
        return [freq_rea_vm, freq_bsy_vm, ipc_vm]

    def preprocess(self, params):
        time.sleep(1)
        for [vm_id, bench_id, num_cores] in params:
            self.bench_id = bench_id
            vm = self.vms[vm_id]
            self.set_cores(vm_id, num_cores)
            vm.client.send('tasks:%d %s' % (vm.num_cores, self.benchs[self.bench_id]))
        time.sleep(1)
        self.record = [[]] * len(params)
        num_sample = 6
        res = self.get_freqs_ipcs(num_sample)
        for [vm_id, bench_id, num_cores] in params:
            self.record[vm_id] = []
            vm = self.vms[vm_id]
            self.record[vm_id].append(vm.vm_id)
            self.record[vm_id].append(bench_id)
            self.record[vm_id].append(self.benchs[bench_id])
            self.record[vm_id].append(vm.num_cores)
            res_vm = self.vm_freq_ipc2(vm_id, num_sample, res)
            self.record[vm_id].append(res_vm[0])
            self.record[vm_id].append(res_vm[1])
            self.record[vm_id].append(res_vm[2])

    def postprocess(self, params):
        data_dir = 'records'
        for [vm_id, bench_id, data] in params:
            vm = self.vms[vm_id]
            data = float(data)
            vm.print('avg_perf: %f' % data)
            self.record[vm_id].append(data)
            #print('self.record[%d]:' % vm_id, self.record[vm_id])
        res = []
        for j in range(0, self.num_vms):
            res.append(self.record[j])
        for [vm_id, bench_id, data] in params:
            self.records[vm_id].append(res)
            #print('self.records[%d]:' % vm_id, self.records[vm_id])
            vm.print('bench_id: %d, benchmark: %s, num_cores: %d\nrecords: ' % (bench_id, self.benchs[bench_id], vm.num_cores), self.records[vm_id])
            f = open('%s/%03d_%03d_%03d_%s.log' % (data_dir, vm_id, self.run_index, bench_id, self.benchs[bench_id]), 'wb')
            #pickle.dump(self.record[vm_id], f)
            pickle.dump(self.records[vm_id], f)
            f.close()
        VMM.visited = [False] * VMM.N_MAX
        self.maps_vm_core = bidict()

    def read_records(self, vm_id, run_index):
        #data_dir = 'records_20211111_two_vms_perf_thread'
        #data_dir = 'records_20211110_one_vm_perf_thread'
        data_dir = 'records'
        vm = self.vms[vm_id]
        files = os.listdir(data_dir)
        print('files=',files)
        pat2 = '(%03d_%03d_.*_.*\..*\.log)' % (vm_id, run_index)
        pat = re.compile(pat2)
        file_name = ''
        for f in files:
            if pat.findall(f):
                file_name = f
                print(f)
                break
        #f = open('%s/%03d_%03d_%s.log' % (data_dir, vm_id, bench_id, self.benchs[bench_id]), 'rb')
        f = open('%s/%s' % (data_dir, file_name), 'rb')
        records = pickle.load(f)
        f.close()
        #vm.print('bench_id: %d, benchmark: %s, num_cores: %d\nrecords: ' % (bench_id, self.benchs[bench_id], vm.num_cores), records)
        vm.print('bench_id: %d, benchmark: %s, num_cores: %d\nrecords: ' % (bench_id, self.benchs[bench_id], vm.num_cores))
        vm.print(records)
        #for record in records:
        #    vm.print(record)
        vm.print('')
        return records

    def force_cmd(self, vm_id):
        vm = self.vms[vm_id]
        vm.get_ip()
        port = random.randint(12345, 16000)
        vm.set_port(port)
        cmd = 'ssh root@%s "pkill test_server"' % (vm.ip)
        p = exec_cmd(cmd, vm_id = vm_id)
        cmd = 'ssh root@%s "cd /root/control_exp && ./test_server.py run %d"' % (vm.ip, vm.port)
        p = exec_cmd(cmd, 1, False, vm_id = vm_id)
        time.sleep(1)
        vm.print(get_res(vm_id))

def decode(data):
    pat = re.compile('(.*):(.*)')
    res = pat.findall(data)
    return res[0]

class SST:
    def __init__(self):
        pass

    def tf(self, num):
        cmd = 'intel-speed-select --cpu 0-%d turbo-freq enable -a' % num
        exec_cmd(cmd)

    def bf(self, num):
        cmd = 'intel-speed-select base-freq enable -a' % num
        exec_cmd(cmd)

    def test(self):
        prog = 'intel-speed-select'
        high_cores = 8
        total_cores = 36
        for ind in range(0, high_cores):
            cmd = '%s core-power --cpu %d assoc --clot 0' % (prog, ind)
            exec_cmd(cmd)

        for ind in range(high_cores, total_cores):
            cmd = '%s core-power --cpu %d assoc --clot 3' % (prog, ind)
            exec_cmd(cmd)

if __name__ == "__main__":
    param = sys.argv[1]
    #new vmm
    vmm = VMM()

    #new VMs
    num_vms = 2
    for vm_id in range(0, num_vms):
        vm_name = 'centos8_test%d' % vm_id
        vmm.new_vm(vm_id, vm_name)
    if param == 'core':
        for vm_id in range(0, num_vms):
            num_cores = 72
            vmm.set_cores(vm_id, num_cores)
            vmm.set_mem(vm_id, 64)
    elif param == 'start' or param == 'shutdown':
        for vm_id in range(0, num_vms):
            vm = vmm.vms[vm_id]
            if param == 'start':
                vm.start()
            elif param == 'shutdown':
                vm.shutdown()
    elif param == 'ip':
        for vm_id in range(0, num_vms):
            vm = vmm.vms[vm_id]
            vm.get_ip()
    elif param == 'test':
        vm_id = 0
        vmm.set_cores(vm_id, 72)
        vmm.set_mem(vm_id, 16)
        res = vmm.get_freqs_ipcs(num)
        vmm.vm_freq_ipc2(vm_id, 6, res)
    elif param == 'read':
        for bench_id in range(0, len(vmm.benchs)):
            for vm_id in range(0, num_vms):
                vmm.read_records(vm_id, bench_id)
    elif param == 'draw':
        records_total = []
        for bench_id in range(0, len(vmm.benchs)):
            records_total.append(vmm.read_records(vm_id, bench_id))
    elif param == 'run':
        debug = True
        vmm.records = [[]] * num_vms
        for vm_id in range(0, num_vms):
            vmm.records[vm_id] = []
            if not debug:
                vmm.force_cmd(vm_id)
            #vmm.vms[vm_id].set_port(12345)
            vmm.vms[vm_id].connect()

        bench_id = 0
        cmd = [None] * num_vms
        data = [None] * num_vms
        while True:
            for vm_id in range(0, num_vms):
                (cmd[vm_id], data[vm_id]) = decode(vmm.vms[vm_id].recv())
            if cmd[0] == 'begin':   #Only vm 0 is the master node
                params = []
                num_cores = 4
                params.append([0, bench_id, num_cores])
                params.append([1, (bench_id + 1) % 3, 72 - num_cores])
                vmm.preprocess(params[0:num_vms])
            elif cmd[0] == 'res':
                params = []
                params.append([0, bench_id, data[0]])
                params.append([1, (bench_id + 1) % 3, data[1]]) #you need to add this
                vmm.postprocess(params[0:num_vms])

                if num_cores == 68:
                    if bench_id == len(vmm.benchs) - 1:
                        for vm_id in range(0, num_vms):
                            vmm.vms[vm_id].send('end:0')
                    else:
                        num_cores = 4
                        bench_id += 1
                        vmm.records = [[]] * num_vms
                        for vm_id in range(0, num_vms):
                            vmm.records[vm_id] = []
                        vmm.run_index += 1
                        params = []
                        params.append([0, bench_id, num_cores])
                        params.append([1, (bench_id + 1) % 3, 72 - num_cores])
                        vmm.preprocess(params[0:num_vms])
                else:
                    num_cores += 4
                    params = []
                    params.append([0, bench_id, num_cores])
                    params.append([1, (bench_id + 1) % 3, 72 - num_cores])
                    vmm.preprocess(params[0:num_vms])
            elif cmd[0] == 'end':
                break
        for vm_id in range(0, num_vms):
            vmm.vms[vm_id].client_close()
    elif param == 'run2':
        debug = True
        vmm.records = [[]] * num_vms
        for vm_id in range(0, num_vms):
            vmm.records[vm_id] = []
            if not debug:
                vmm.force_cmd(vm_id)
            #vmm.vms[vm_id].set_port(12345)
            vmm.vms[vm_id].connect()

        bench_id = 0
        cmd = [None] * num_vms
        data = [None] * num_vms
        while True:
            for vm_id in range(0, num_vms):
                (cmd[vm_id], data[vm_id]) = decode(vmm.vms[vm_id].recv())
            if cmd[0] == 'begin':   #Only vm 0 is the master node
                params = []
                num_cores = 16
                params.append([0, 1, num_cores])
                params.append([1, 1, 72 - num_cores])
                vmm.preprocess(params[0:num_vms])
            elif cmd[0] == 'res':
                params = []
                params.append([0, 1, data[0]])
                params.append([1, 1, data[1]]) #you need to add this
                vmm.postprocess(params[0:num_vms])

                if num_cores == 68:
                    if bench_id == len(vmm.benchs) - 1:
                        for vm_id in range(0, num_vms):
                            vmm.vms[vm_id].send('end:0')
                    else:
                        vmm.records = [[]] * num_vms
                        for vm_id in range(0, num_vms):
                            vmm.records[vm_id] = []
                        vmm.run_index += 1
                        params = []
                        params.append([0, 1, num_cores])
                        params.append([1, 1, 72 - num_cores])
                        vmm.preprocess(params[0:num_vms])
                else:
                    num_cores += 4
                    params = []
                    params.append([0, 1, num_cores])
                    params.append([1, 1, 72 - num_cores])
                    vmm.preprocess(params[0:num_vms])
            elif cmd[0] == 'end':
                break
        for vm_id in range(0, num_vms):
            vmm.vms[vm_id].client_close()
    elif param == 'sst':
        sst = SST()
        #sst.test()
        sst.tf(8)
    elif param == 'ssh':
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname='192.168.122.153', port=22, username='root', password='123')
        stdin, stdout, stderr = ssh.exec_command('cd /root/control_exp; ./test_server.py run 12349')
        print(stdout.read())
        print(stderr.read())
        #sys.stdout = stdout
        #ssh.close()

    else:
        print("param error")

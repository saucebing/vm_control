#!/usr/bin/python3
import os, sys, time, subprocess, tempfile, re
import client, timeit
from bidict import bidict
from collections import Counter
import pickle
import random
import paramiko

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from scipy.interpolate import splev, splrep

out_temp = [None] * 1024
fileno = [None] * 1024

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def exec_cmd(cmd, index = 0, wait = True, vm_id = 0):
    global out_temp, fileno
    print('[VM%d]: CMD: ' % vm_id, cmd)
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
    return list(filter(lambda x:x, string.split()))

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

    llc_ways_beg = 0
    llc_ways_end = 11
    memb = 100

    def __init__(self, vm_id, vm_name):
        self.vm_id = vm_id
        self.vm_name = vm_name
        self.client = client.CLIENT()
        state = self.get_state()

        self.llc_ways_beg = 0
        self.llc_ways_end = 11
        self.memb = 100
        #self.print(self.state)

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
        self.get_state()
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
        vm.get_state()
        if self.state == 'running':
            cmd = 'virsh shutdown %s' % self.vm_name
            exec_cmd(cmd, vm_id = self.vm_id)

    def start(self):
        vm.get_state()
        if self.state == 'shut off':
            cmd = 'virsh start %s' % self.vm_name
            exec_cmd(cmd, vm_id = self.vm_id)

    def suspend(self):
        cmd = 'virsh suspend %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)

    def resume(self):
        cmd = 'virsh resume %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)

    def get_pid(self):
        cmd = 'ps aux | grep kvm'
        exec_cmd(cmd, vm_id = self.vm_id)
        lines = get_res().split('\n')
        pid = 0
        for line in lines:
            if self.vm_name in line:
                pid = int(split_str(line)[1])
                break
        return pid

    def get_spid(self):
        pid = self.get_pid()
        spids = []
        for i in range(0, self.num_cores):
            spids.append([])
        cmd = 'ps -T -p %d' % pid
        exec_cmd(cmd, vm_id = self.vm_id)
        lines = get_res().split('\n')
        for line in lines:
            if 'CPU' in line and 'KVM' in line:
                line2 = split_str(line)
                vcpu_id = int(find_str('([0-9]+)/KVM', line2[5]))
                spids[vcpu_id] = int(line2[1])
        return spids

    def bind_core(self, vcpu, pcpu): #pcpu可以是0-143
        cmd = 'virsh vcpupin %s %s %s' % (self.vm_name, vcpu, pcpu)
        exec_cmd(cmd, vm_id = self.vm_id)

    def bind_mem(self): #pcpu可以是0-143
        pid = self.get_pid()
        cmd = 'migratepages %d all 0' % pid
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
    benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'NPB.CG', 'NPB.FT', 'NPB.SP', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions', 'NPB.EP', 'parsec.canneal', 'parsec.freqmine']
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions']
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions']
    #benchs = ['parsec.canneal', 'parsec.freqmine']
    #benchs = ['NPB.CG', 'NPB.FT', 'NPB.SP', 'NPB.EP']
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'NPB.CG', 'NPB.FT', 'NPB.SP', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions', 'NPB.EP']
    #benchs = ['splash2x.raytrace']
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.barnes', 'splash2x.lu_cb', 'splash2x.radiosity', 'splash2x.water_spatial', 'parsec.fluidanimate', 'parsec.freqmine', 'parsec.ferret', 'parsec.blackscholes']
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.water_spatial']

    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.water_spatial', 'parsec.blackscholes']
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.water_spatial', 'parsec.blackscholes']

    bench_id = 0
    run_index = 0
    N_CORE = 0 #number of logical cores
    H_CORE = 0 #number of logical cores in one socket
    Q_CORE = 0 #number of logical cores in one socket
    N_RDT = 0 #number of RDT metrics
    N_FREQ = 0 #number of frequency metrics
    params = []
    mode = ''

    def __init__(self):
        VMM.N_CORE = 80
        VMM.H_CORE = int(VMM.N_CORE / 2)
        VMM.Q_CORE = int(VMM.N_CORE / 4)
        VMM.N_RDT = 5
        VMM.N_FREQ = 2
        VMM.visited = [False] * VMM.N_CORE

    def new_vm(self, vm_id, vm_name):
        vm = VM(vm_id, vm_name)
        self.vms.append(vm)
        self.num_vms = len(self.vms)
        self.params.append([])

    def set_mem(self, vm_id, mem):
        vm = self.vms[vm_id]
        vm.setmem_dyn(mem)

    def set_cores(self, vm_id, num_cores, begin_core = 0, same_core = 0):
        num_pcores = int(num_cores / 2)
        local_core_id = 0
        for global_core_id in (list(range(begin_core, VMM.Q_CORE)) + list(range(0, begin_core))):
            if not VMM.visited[global_core_id]:
                if begin_core == 0 and vm_id != 0:
                    global_core_id -= int(same_core / 2)
                self.maps_vm_core[(vm_id, local_core_id)] = global_core_id
                local_core_id += 1
                VMM.visited[global_core_id] = True
                self.maps_vm_core[(vm_id, local_core_id)] = global_core_id + VMM.H_CORE
                local_core_id += 1
                VMM.visited[global_core_id + VMM.H_CORE] = True
        print('maps_vm_core:', self.maps_vm_core)
        vm = self.vms[vm_id]
        vm.setvcpus_dyn(num_cores)
        vm.num_cores = num_cores
        for i in range(0, num_cores):
            vm.bind_core(i, self.maps_vm_core[(vm.vm_id, i)])
        vm.bind_mem()

    def get_rdt(self):
        exec_cmd('pqos-msr -t 1')
        res = get_res()
        #print(res)
        res = res.split('\n')
        ind = 0
        while not 'CORE' in res[ind]:
            ind += 1
        ind += 1
        while not 'CORE' in res[ind]:
            ind += 1
        rdts = []
        for i in range(0, VMM.N_RDT):
            rdts.append({})
        for (ind, line) in enumerate(res[ind + 1: ind + VMM.Q_CORE + 1] + res[ind + VMM.H_CORE + 1: ind + VMM.H_CORE + VMM.Q_CORE + 1]):
            aline = line.split()
            rdts[0][int(aline[0])] = float(aline[1]) #ipc
            rdts[1][int(aline[0])] = float(aline[2][:-1]) #miss
            rdts[2][int(aline[0])] = float(aline[3]) #LLC (KB)
            rdts[3][int(aline[0])] = float(aline[4]) #MBL (MB/s)
            rdts[4][int(aline[0])] = float(aline[5]) #MBR (MB/s)
        return rdts

    def get_freq(self):
        exec_cmd('turbostat -q -i 1 -n 1')
        res = get_res()
        #print(res)
        res = res.split('\n')
        ind = 0
        while not 'Package' in res[ind]:
            ind += 1
        freqs = []
        for i in range(0, VMM.N_FREQ):
            freqs.append({})
        for (ind, line) in enumerate(res[ind + 2: ind + 2 + VMM.H_CORE]):
            aline = line.split()
            freqs[0][int(aline[2])] = float(aline[3]) #avg_freq
            freqs[1][int(aline[2])] = float(aline[5]) #bzy_freq
        return freqs

    def get_avg(self, mets, num):
        met_sum = {}
        for i in range(0, VMM.Q_CORE):
            met_sum[i] = 0
            met_sum[i + VMM.H_CORE] = 0
        for met in mets:
            for i in range(0, VMM.Q_CORE):
                met_sum[i] += met[i];
                met_sum[i + VMM.H_CORE] += met[i + VMM.H_CORE];
        for i in range(0, int(self.N_CORE / 4)):
            met_sum[i] /= num
            met_sum[i + VMM.H_CORE] /= num
        return met_sum

    def get_metrics(self, num):
        mets = []
        avg_mets = []
        N_METRICS = VMM.N_FREQ + VMM.N_RDT
        for i in range(0, N_METRICS):
            mets.append([])
        for i in range(0, num):
            freq = self.get_freq()
            rdt = self.get_rdt()
            mets[0].append(freq[0])
            mets[1].append(freq[1])
            mets[2].append(rdt[0])
            mets[3].append(rdt[1])
            mets[4].append(rdt[2])
            mets[5].append(rdt[3])
            mets[6].append(rdt[4])
        for met in mets:
            avg_mets.append(self.get_avg(met, num))
        return avg_mets

    def vm_met(self, vm_id, met):
        vm = self.vms[vm_id]
        num_cores = vm.num_cores
        met_total = 0
        for id_core in range(0, num_cores):
            met_total += met[self.maps_vm_core[(vm_id, id_core)]]
        met_avg = met_total / num_cores
        return met_avg

    def vm_metrics(self, vm_id, num_sample, res):
        print('vm_id = ', vm_id)
        self.vms[vm_id].print('freq_rea, frea_bsy and ipc:', res)
        met_vm = []
        for r in res:
            met_vm.append(self.vm_met(vm_id, r))
        self.vms[vm_id].print('freq_rea_vm, freq_bsy_vm and ipc_vm is: ', met_vm[0], met_vm[1], met_vm[2])
        return met_vm

    def param_bench_id(self, vm_id):
        if vm_id == 0:
            return self.run_index
        elif vm_id == 1:
            if self.mode == 'num_cores':
                return (self.run_index + 1) % 3
            elif self.mode == 'begin_core':
                return self.run_index

    def param_num_cores(self, vm_id, num_cores):
        if vm_id == 0:
            return num_cores
        elif vm_id == 1:
            return VMM.H_CORE - num_cores

    def param_begin_core(self, vm_id, begin_core):
        if self.mode == 'num_cores':
            return begin_core
        elif self.mode == 'begin_core':
            if vm_id == 0:
                return begin_core
            elif vm_id == 1:
                return 0
        elif self.mode == 'llc':
            return begin_core
        elif self.mode == 'memb':
            return begin_core

    def end_event(self, num_cores, begin_core):
        if self.mode == 'num_cores':
            return (self.num_vms == 1 and num_cores == VMM.H_CORE) or (self.num_vms == 2 and num_cores == VMM.H_CORE - 4)
        elif self.mode == 'begin_core':
            return begin_core == num_cores
        elif self.mode == 'llc':
            return vmm.vms[0].llc_ways_end == 11
        elif self.mode == 'memb':
            return vmm.vms[0].memb == 100

    def end_all(self):
        return self.run_index == len(self.benchs) - 1

    def set_params(self, num_cores, begin_core, data):
        for vm_id in range(0, self.num_vms):
            self.params[vm_id] = [vm_id, self.param_bench_id(vm_id), self.param_num_cores(vm_id, num_cores), self.param_begin_core(vm_id, begin_core), data[vm_id]]

    def init_mode(self, mode):
        self.mode = mode #num_cores, begin_core

    def preprocess(self):
        time.sleep(0.5)
        for [vm_id, bench_id, num_cores, begin_core, data] in self.params:
            self.bench_id = bench_id
            vm = self.vms[vm_id]
            self.set_cores(vm_id, num_cores, begin_core)

            rdt = RDT()
            if self.mode == 'llc' or self.mode == 'memb':
                rdt.set_llc(self, 0, vm.llc_ways_beg, vm.llc_ways_end)
                rdt.set_mb(self, 0, vm.memb)

            vm.client.send('tasks:%d %s' % (vm.num_cores, self.benchs[self.bench_id]))
        time.sleep(2)
        self.record = [[]] * len(self.params)
        num_sample = 5
        res = self.get_metrics(num_sample)
        for [vm_id, bench_id, num_cores, begin_core, data] in self.params:
            self.record[vm_id] = []
            vm = self.vms[vm_id]
            self.record[vm_id].append(vm.vm_id)
            self.record[vm_id].append(bench_id)
            self.record[vm_id].append(self.benchs[bench_id])
            self.record[vm_id].append(begin_core)
            self.record[vm_id].append(vm.num_cores)
            self.record[vm_id].append(vm.llc_ways_beg)
            self.record[vm_id].append(vm.llc_ways_end)
            self.record[vm_id].append(vm.memb)
            res_vm = self.vm_metrics(vm_id, num_sample, res)
            for r_vm in res_vm:
                self.record[vm_id].append(r_vm)
        #vm_id, bench_id, bench_name, begin_core, num_cores, llc_ways_beg, llc_ways_end, memb, freq_avg, freq_bzy, ipc, miss, LLC, MBL, MBR, time

    def postprocess(self):
        data_dir = 'records'
        for [vm_id, bench_id, num_cores, begin_core, data] in self.params:
            vm = self.vms[vm_id]
            data = float(data)
            vm.print('avg_perf: %f' % data)
            self.record[vm_id].append(data)
            #print('self.record[%d]:' % vm_id, self.record[vm_id])
        res = []
        for j in range(0, self.num_vms):
            res.append(self.record[j])
        for [vm_id, bench_id, num_cores, begin_core, data] in self.params:
            self.records[vm_id].append(res)
            #print('self.records[%d]:' % vm_id, self.records[vm_id])
            vm.print('bench_id: %d, benchmark: %s, num_cores: %d\nrecords: ' % (bench_id, self.benchs[bench_id], vm.num_cores), self.records[vm_id])
            f = open('%s/%03d_%03d_%03d_%s.log' % (data_dir, vm_id, self.run_index, bench_id, self.benchs[bench_id]), 'wb')
            #pickle.dump(self.record[vm_id], f)
            pickle.dump(self.records[vm_id], f)
            f.close()
        VMM.visited = [False] * VMM.N_CORE
        self.maps_vm_core = bidict()

    def read_records(self, data_dir, vm_id, run_index, is_print = True):
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
        f = open('%s/%s' % (data_dir, file_name), 'rb')
        #f2 = open('%s/%s' % ('records_llc_2', file_name), 'wb')
        records = pickle.load(f)
        #for record1 in records:
        #    for record2 in record1:
        #        record2.insert(7, 100)
        #        print(record2)
        #pickle.dump(records, f2)
        f.close()
        #f2.close()
        if is_print:
            vm.print('bench_id: %d, benchmark: %s, num_cores: %d\nrecords: ' % (bench_id, self.benchs[bench_id], vm.num_cores))
            vm.print(records)
            vm.print('')
        return records

    def pre_draw(self, data_dir, benchs):
        records_total = []
        for bench_id in range(0, len(benchs)):
            records_total.append(self.read_records(data_dir, 0, bench_id, False))
        #different benchmarks, different experiments, different vms
        num_benchs = len(records_total)
        num_exps = len(records_total[0])
        num_vms = len(records_total[0][0])
        #print(num_benchs, num_exps, num_vms)
        vms_exps_benchs = []
        for record in records_total:
            vms_exps = []
            for (ind, exp) in enumerate(record):
                vms_exp = []
                for tmp_exp in exp:
                    vm_exp = Exp(vmm, tmp_exp)
                    vms_exp.append(vm_exp)
                vms_exps.append(vms_exp)
            vms_exps_benchs.append(vms_exps)
        return [num_benchs, num_exps, num_vms, vms_exps_benchs]

    def pre_draw_2(self, num_figs):
        figs = []
        axs = []

        for f_id in range(0, num_figs):
            fig, ax = plt.subplots()
            figs.append(fig)
            axs.append(ax)
        return [figs, axs]

    def post_draw(self, num_figs, figs, axs):
        figdir = 'figs'
        for f_id in range(0, num_figs):
            title = '%s-%s' % (ylabels[f_id], xlabels[f_id])
            axs[f_id].set_title(title)
            if xaxis[f_id]:
                axs[f_id].set_xticks(xaxis[f_id])
            axs[f_id].set_xlabel(xlabels[f_id])
            axs[f_id].set_ylabel(ylabels[f_id])
            #axs[f_id].grid('on')
            #plt.legend(loc='lower left')
            #axs[f_id].legend(loc='best')
            #axs[f_id].legend(loc=2, bbox_to_anchor=(1.05,1.0), borderaxespad = 0.) 
            axs[f_id].legend(loc=2, bbox_to_anchor=(1.0, 1.0))
            #size = figs[f_id].get_size_inches()
            #print(size)
            width = 6.4
            height = 4.8
            figs[f_id].set_figwidth(width  * 1.3)
            figs[f_id].tight_layout()
            file_name = "%s/%s.eps" % (figdir, title)
            #file_name = file_name.replace(' ', '_')
            figs[f_id].savefig(file_name, bbox_inches='tight')

    def force_cmd(self, vm_id):
        vm = self.vms[vm_id]
        vm.get_ip()
        #port = random.randint(12345, 16000)
        port = 12345
        vm.set_port(port)
        cmd = "ssh root@%s 'pkill test_server'" % (vm.ip)
        p = exec_cmd(cmd, vm_id = vm_id)
        cmd = "ssh -t %s 'cd /root/vm_control/control_exp && ./test_server.py run %d' > %s.log" % (vm.ip, port, vm.vm_name)
        p = exec_cmd(cmd, 1, False, vm_id = vm_id)
        #vm.print(get_res(vm_id))

def decode(data):
    pat = re.compile('(.*):(.*)')
    res = pat.findall(data)
    return res[0]

class SST:
    def __init__(self):
        pass

    def tf(self, num):
        cmd = 'intel-speed-select --cpu 0-%d turbo-freq enable -a' % (num - 1)
        exec_cmd(cmd)

    def tf_close(self):
        cmd = 'intel-speed-select turbo-freq disable -a'
        exec_cmd(cmd)

    def bf(self, num):
        cmd = 'intel-speed-select base-freq enable -a' 
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

class RDT:
    def __init__(self):
        pass

    def llc2bit(self, beg, end):
        llc_ways = 0x0
        for way_id in range(beg, end):
            llc_ways |= (1 << way_id)
        return llc_ways

    def set_llc(self, vmm, vm_id, way_beg, way_end):
        core_list = []
        for core_id in range(0, vmm.vms[vm_id].num_cores):
            core_list.append(str(vmm.maps_vm_core[(vm_id, core_id)]))
        core_list = ",".join(core_list)
        llc_ways = self.llc2bit(way_beg, way_end)
        cmd1 = 'pqos-msr -e "llc:%d=0x%x"' % (vm_id + 1, llc_ways)
        cmd2 = 'pqos-msr -a "cos:%d=%s"' % (vm_id + 1, core_list)
        exec_cmd(cmd1)
        exec_cmd(cmd2)

    def set_mb(self, vmm, vm_id, mba_perc):
        core_list = []
        for core_id in range(0, vmm.vms[vm_id].num_cores):
            core_list.append(str(vmm.maps_vm_core[(vm_id, core_id)]))
        core_list = ",".join(core_list)
        cmd1 = 'pqos-msr -e "mba:%d=%d"' % (vm_id + 1, mba_perc)
        cmd2 = 'pqos-msr -a "cos:%d=%s"' % (vm_id + 1, core_list)
        exec_cmd(cmd1)
        exec_cmd(cmd2)

    def reset(self):
        cmd = 'pqos-msr -R'
        exec_cmd(cmd)

    def show(self):
        cmd = 'pqos-msr -s'
        exec_cmd(cmd)
        print(get_res())

class Exp:
    vm_id = 0
    bench_id = 0
    bench_name = ''
    begin_core = 0
    num_cores = 0

    llc_ways_beg = 0
    llc_ways_end = 0
    memb = 0

    avg_freq = 0
    bzy_freq = 0
    ipc = 0
    miss = 0
    LLc = 0
    MBL = 0
    MBR = 0

    runtime = 0
    vmm = None
    data = []

    def __init__(self, vmm, data):
        self.vm_id = data[0]
        self.bench_id = data[1]
        self.bench_name = data[2]
        self.begin_core = data[3]
        self.num_cores = data[4]

        self.llc_ways_beg = data[5]
        self.llc_ways_end = data[6]
        self.memb = data[7]

        self.avg_freq = data[8]
        self.bzy_freq = data[9]
        self.ipc = data[10]
        self.miss = data[11]
        self.LLc = data[12]
        self.MBL = data[13]
        self.MBR = data[14]
        self.runtime = data[15]

        self.vmm = vmm
        self.data = data

    def print(self):
        self.vmm.vms[self.vm_id].print('vm_id = %02d, bench_id = %02d, bench_name = %20s, begin_core = %02d, num_cores = %02d, avg_freq = %.2f, bzy_freq = %.2f, ipc = %.2f, runtime = %.2f' % (self.vm_id, self.bench_id, self.bench_name, self.begin_core, self.num_cores, self.avg_freq, self.bzy_freq, self.ipc, self.runtime))

if __name__ == "__main__":
    param = sys.argv[1]
    #new vmm
    vmm = VMM()

    #new VMs
    num_vms = 1
    for vm_id in range(0, num_vms):
        vm_name = 'centos8_test%d' % vm_id
        vmm.new_vm(vm_id, vm_name)
    if param == 'init':
        for vm_id in range(0, num_vms):
            vm = vmm.vms[vm_id]
            vm.setvcpus_sta(VMM.H_CORE)
            vm.setmem_sta(64)
            vm.shutdown()
            time.sleep(10)
            vm.start()
            time.sleep(10)
            vm.setvcpus_dyn(1)
            vm.setmem_dyn(16)
    elif param == 'core':
        for vm_id in range(0, num_vms):
            num_cores = 4
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
        vmm.set_cores(vm_id, VMM.H_CORE)
        vmm.set_mem(vm_id, 16)
        res = vmm.get_metrics(num)
        vmm.vm_metrics(vm_id, 6, res)
    elif param == 'read':
        #data_dir = 'records_20211123_one_vm_perf_thread'
        data_dir = 'records'
        for bench_id in range(0, len(vmm.benchs)):
            for vm_id in range(0, num_vms):
                vmm.read_records(data_dir, vm_id, bench_id + 11)
    elif param == 'draw':
        #data_dir = 'records_20211123_one_vm_perf_thread'
        data_dir = 'records_llc'
        [num_benchs, num_exps, num_vms, vms_exps_benchs] = vmm.pre_draw(data_dir, vmm.benchs)
        num_figs = 2
        xlabels = ['LLC ways', 'LLC ways']
        ylabels = ['IPC', 'Run Time(s)']
        xaxis = [range(0, 12, 1), range(0, 12, 1), None]
        [figs, axs] = vmm.pre_draw_2(num_figs)

        for id_bench in range(0, num_benchs):
            num_cores = []
            bzy_freq = []
            runtime = []
            llc_ways = []
            ipc = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    num_cores.append(ele.num_cores)
                    bzy_freq.append(ele.bzy_freq)
                    ipc.append(ele.ipc)
                    llc_ways.append(ele.llc_ways_end)
                    runtime.append(ele.runtime)
                    ele.print()
            #axs[0].plot(num_cores, bzy_freq, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[1].plot(num_cores, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[2].plot(bzy_freq, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[0].plot(llc_ways, ipc, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[1].plot(llc_ways, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            vmm.post_draw(num_figs, figs, axs)

        data_dir = 'records_memb'
        [num_benchs, num_exps, num_vms, vms_exps_benchs] = vmm.pre_draw(data_dir, vmm.benchs)
        num_figs = 2
        xlabels = ['Memory Bandwidth(%)', 'Memory Bandwidth(%)']
        ylabels = ['IPC', 'Run Time(s)']
        xaxis = [range(0, 110, 10), range(0, 110, 10), None]
        [figs, axs] = vmm.pre_draw_2(num_figs)

        for id_bench in range(0, num_benchs):
            num_cores = []
            bzy_freq = []
            runtime = []
            memb = []
            ipc = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    num_cores.append(ele.num_cores)
                    bzy_freq.append(ele.bzy_freq)
                    ipc.append(ele.ipc)
                    memb.append(ele.memb)
                    runtime.append(ele.runtime)
                    ele.print()
            #axs[0].plot(num_cores, bzy_freq, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[1].plot(num_cores, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[2].plot(bzy_freq, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[0].plot(memb, ipc, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[1].plot(memb, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            vmm.post_draw(num_figs, figs, axs)

        #plt.show()

    elif param == 'run':
        debug = True
        vmm.records = [[]] * num_vms
        for vm_id in range(0, num_vms):
            vmm.records[vm_id] = []
            if not debug:
                vmm.force_cmd(vm_id)
            else:
                vmm.vms[vm_id].set_port(12345)
            vmm.vms[vm_id].connect()

        cmd = [None] * num_vms
        data = [None] * num_vms
        num_cores = 0 
        begin_core = 0
        #vmm.init_mode('begin_core')
        #vmm.init_mode('num_cores')
        vmm.init_mode('llc')
        #vmm.init_mode('memb')
        while True:
            for vm_id in range(0, num_vms):
                (cmd[vm_id], data[vm_id]) = decode(vmm.vms[vm_id].recv())
            if cmd[0] == 'begin':   #Only vm 0 is the master node
                if vmm.mode == 'num_cores':
                    num_cores = 4
                elif vmm.mode == 'begin_core':
                    num_cores = 64
                elif vmm.mode == 'llc':
                    num_cores = 4
                    vmm.vms[0].llc_ways_end = 0
                    vmm.vms[0].llc_ways_end = 1
                    vmm.vms[0].memb = 100
                elif vmm.mode == 'memb':
                    num_cores = 4
                    vmm.vms[0].llc_ways_end = 0
                    vmm.vms[0].llc_ways_end = 11
                    vmm.vms[0].memb = 10

                #sst = SST()
                #if vmm.mode == 'num_cores':
                #    sst.tf_close()
                #elif vmm.mode == 'begin_core':
                #    sst.tf(int(num_cores / 2)) #num is the number of physical cores
                #time.sleep(1)

                vmm.set_params(num_cores, begin_core, data)
                vmm.preprocess()
            elif cmd[0] == 'res':
                vmm.set_params(num_cores, begin_core, data)
                vmm.postprocess()

                if vmm.end_event(num_cores, begin_core):
                    if vmm.end_all():
                        for vm_id in range(0, num_vms):
                            vmm.vms[vm_id].send('end:0')
                    else:
                        vmm.records = []
                        for vm_id in range(0, num_vms):
                            vmm.records.append([])
                        if vmm.mode == 'num_cores':
                            num_cores = 4
                        elif vmm.mode == 'begin_core':
                            begin_core = 0
                        elif vmm.mode == 'llc':
                            vmm.vms[0].llc_ways_end = 1
                        elif vmm.mode == 'memb':
                            vmm.vms[0].memb = 10
                        vmm.run_index += 1
                        vmm.set_params(num_cores, begin_core, data)
                        vmm.preprocess()
                else:
                    if vmm.mode == 'num_cores':
                        num_cores += 4
                    elif vmm.mode == 'begin_core':
                        begin_core += 4
                    elif vmm.mode == 'llc':
                        vmm.vms[0].llc_ways_end += 1
                    elif vmm.mode == 'memb':
                        vmm.vms[0].memb += 10
                    vmm.set_params(num_cores, begin_core, data)
                    vmm.preprocess()
            elif cmd[0] == 'end':
                break
        for vm_id in range(0, num_vms):
            vmm.vms[vm_id].client_close()
    elif param == 'sst':
        sst = SST()
        #sst.test()
        sst.tf(4) #num is the number of physical cores
    elif param == 'rdt':
        rdt = RDT()
        num_cores = 8
        vmm.set_cores(0, num_cores)
        rdt.set_llc(vmm, 0, 1, 3)
        rdt.set_mb(vmm, 0, 30)
        #rdt.show()
    elif param == 'clean':
        rdt = RDT()
        rdt.reset()
    elif param == 'spid':
        #print(vmm.vms[0].get_spid())
        num_cores = 8
        vmm.set_cores(0, num_cores)
    elif param == 'ssh':
        vmm.force_cmd(0)
        #vm_id = 0
        #vm = vmm.vms[vm_id]
        #vm.get_ip()
        #p = exec_cmd("ssh -t %s 'cd /root/vm_control/control_exp && ./test_server.py run 12345' > %s.log" % (vm.ip, vm.vm_name), 1, True)
        #ssh = paramiko.SSHClient()
        #ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #ssh.connect(hostname='192.168.122.169', port=22, username='root', password='123')
        #stdin, stdout, stderr = ssh.exec_command('cd /root/vm_control/control_exp && ./test_server.py run 12345')
        #print(stdout.read())
        #print(stderr.read())
    else:
        print("param error")

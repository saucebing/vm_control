#!/usr/bin/python3
import os, sys, time, subprocess, tempfile, re
import server

out_temp = [None] * 1024
fileno = [None] * 1024

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def exec_cmd(cmd, index = 0, wait = True):
    global out_temp, fileno
    print('CMD: ', cmd)
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
    return pat.findall(string)[0].strip()

def find_str2(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[-1]

def split_str(string):
    return filter(lambda x:x, string.split())

def b2s(s):
    return str(s, encoding = 'utf-8')

def get_res(ind = 0):
    return b2s(out_temp[ind].read())

def run_parsec(task, scale, times, limited_time = 0):
    ws = '/root/parsec-3.0'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    cmd = 'time ./run.sh %s %s %s' % (task, scale, times)
    t_total = 0
    nums = 1
    for i in range(0, nums):
        p = exec_cmd(cmd, wati = False)
        if limited_time != 0:
            time.sleep(limited_time)
            p.terminate()
        else:
            p.wait()
        res = get_res()
        #print(res)
        if limited_time == 0:
            (m, s) = find_str2('real(.*)m(.*)s', res)
        else:
            (m, s) = ('0', str(limited_time))
        m = m.strip()
        s = s.strip()
        t = float(m) * 60 + float(s)
        t_total += t
    t_avg = t_total / nums
    os.chdir(cur_path)
    return t_avg

def run_parsec_parallel(task, scale, times, n_proc, limited_time = 0):
    ws = '/root/parsec-3.0'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    t_total = 0
    nums = 1
    for i in range(0, nums): # nums times same tasks
        cmd = 'time ./run.sh %s %s %s' % (task, scale, times)
        p = parallel_cmd(cmd, n_proc, wait = False)
        if limited_time != 0:
            time.sleep(limited_time)
            for p1 in p:
                p1.terminate()
        else:
            for p1 in p:
                p1.wait()
        for j in range(0, n_proc):
            res = get_res(j)
            #print(res)
            if limited_time == 0:
                (m, s) = find_str2('real(.*)m(.*)s', res)
            else:
                (m, s) = ('0', str(limited_time))
            print('Thread %d: %sm %ss' % (j, m, s))
            m = m.strip()
            s = s.strip()
            t = float(m) * 60 + float(s)
            t_total += t
        t_total /= n_proc
    t_avg = t_total / nums
    os.chdir(cur_path)
    return t_avg

def run_NPB_parallel(task_name, n_thread, n_proc, limited_time = 0):
    cmd = 'mpirun --version'
    exec_cmd(cmd)
    allow_root = ''
    if not 'mpich' in get_res():
        allow_root = '--allow-run-as-root'
    ws = '/root/NPB3.4.2/NPB3.4-MPI'
    cur_path = os.getcwd()
    os.chdir('%s' % ws)
    t_total = 0
    nums = 1
    for i in range(0, nums): # nums times same tasks
        if n_thread == 4:
            cmd = 'time mpirun %s -np %d bin/%s.B.x' % (allow_root, n_thread, task_name)
        elif n_thread == 16:
            cmd = 'time mpirun %s -np %d bin/%s.C.x' % (allow_root, n_thread, task_name)
        p = parallel_cmd(cmd, n_proc, wait = False)
        if limited_time != 0:
            time.sleep(limited_time)
            for p1 in p:
                p1.terminate()
        else:
            for p1 in p:
                p1.wait()
        for j in range(0, n_proc):
            res = get_res(j)
            #print(res)
            if limited_time == 0:
                (m, s) = find_str2('real(.*)m(.*)s', res)
            else:
                (m, s) = ('0', str(limited_time))
            print('Thread %d: %sm %ss' % (j, m, s))
            m = m.strip()
            s = s.strip()
            t = float(m) * 60 + float(s)
            t_total += t
        t_total /= n_proc
    t_avg = t_total / nums
    os.chdir(cur_path)
    return t_avg

def decode(data):
    pat = re.compile('(.*):(.*)')
    res = pat.findall(data)
    return res[0]

param = sys.argv[1]
#parsec_scale = 'simlarge'
#parsec_times = 10
parsec_scale = 'native'
parsec_times = 1
limited_time = 0
if param == 'test':
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions']
    benchs = ['parsec.blackscholes', 'parsec.canneal', 'parsec.fluidanimate', 'parsec.freqmine', 'parsec.streamcluster', 'parsec.vips']
    #run_parsec_parallel('4 parsec.ferret', parsec_scale, parsec_times, 18)
    #run_NPB_parallel('sp', 4, 1)
    limited_time = 15
    os.system("make run")
    run_parsec_parallel('4 parsec.swaptions', parsec_scale, parsec_times, 1, limited_time)
    #for bench_id in range(6, len(benchs)):
    #    run_parsec_parallel('4 %s' % benchs[bench_id], parsec_scale, parsec_times, 1)
elif param == 'run':
    debug = True
    port = int(sys.argv[2])
    serv = server.SERVER()
    if not debug:
        serv.set_port(port)
    serv.build()
    while True:
        data = 0
        try:
            while True:
                (cmd, data) = decode(serv.recv())
                if cmd == 'begin':
                    serv.send('begin:0')
                elif cmd == 'end':
                    serv.send('end:0')
                    break #modify file
                elif cmd == 'all_end':
                    break
                elif cmd == 'tasks' or cmd == 'limited_time':
                    if cmd == 'limited_time':
                        limited_time = 15
                    (n_cores, task_name) = find_str2('([0-9]+)(.*)', data)
                    n_cores = n_cores.strip()
                    task_name = task_name.strip()
                    if 'splash2x' in task_name or 'parsec' in task_name:
                        #if 'ocean_ncp' in task_name:    #special deal
                        #    num_threads = 4
                        #    tasks_per_thread = int(int(n_cores) / num_threads)
                        #    task = '%d %s' % (tasks_per_thread, task_name)
                        #else:
                        #    task = '4 %s' % task_name
                        #    num_threads = int(int(n_cores) / 4)
                        task = ''
                        num_threads = 0
                        if int(n_cores) == 4:
                            task = '4 %s' % task_name
                            num_threads = int(int(n_cores) / 4)
                        elif int(n_cores) == 16:
                            task = '16 %s' % task_name
                            num_threads = int(int(n_cores) / 16)
                        #avg_perf = run_parsec(task, parsec_scale)
                        os.system('rm -rf /root/parsec-3.0/result/*')
                        os.system("make run")
                        avg_perf = run_parsec_parallel(task, parsec_scale, parsec_times, num_threads, limited_time)
                        print(avg_perf, 's')
                        serv.send('res:%f' % avg_perf)
                    elif 'NPB' in task_name:
                        task_name = task_name[4:].lower()
                        num_threads = int(n_cores)
                        avg_perf = run_NPB_parallel(task_name, num_threads, 1, limited_time)
                        print(avg_perf, 's')
                        serv.send('res:%f' % avg_perf)
            if cmd == 'all_end':
                serv.client_close()
                serv.server_close()
                break
        except KeyboardInterrupt:
            serv.client_close()
            serv.server_close()
            break
else:
    print('param error')

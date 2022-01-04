#!/usr/bin/python
import os, sys, time, subprocess, tempfile, re
import client
import timeit
out_temp = None
fileno = None

def exec_cmd(cmd):
    global out_temp, fileno
    out_temp = tempfile.SpooledTemporaryFile(bufsize=1000 * 1000 * 100)
    fileno = out_temp.fileno()
    p1 = subprocess.Popen(cmd, stdout = fileno, stderr = fileno, shell=True)
    return p1

def find_str(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[0]

def split_str(string):
    return filter(lambda x:x, string.split())

#f = open('a.log', 'a')
#for i in range(0, 10):
#    print i
#    os.system('pkill sail')
#    p1 = exec_cmd('sail -c 1')
#    p1.wait()
#    out_temp.seek(0)
#    f.write(out_temp.read())
#    out_temp.flush()
#    out_temp.close()
#f.close()

fname = 'monitor_output_origin_cpu2006_namd_guest_%sthreads.log'
print 'Test Client, connecting'
client.connect()
print 'Connected'
ratios = [i / 100.0 for i in range(100,0,-5)]
for ratio in ratios:
    client.send(str(ratio))
    f = open(fname % int(ratio * 96), 'w')
    cmd = client.recv()
    if cmd == 'begin':
        client.send('stage 1')
        time.sleep(2)
        beg = time.time()
        while True:
            os.system('pkill sail')
            p1 = subprocess.Popen('sail -c 1', stdout = f, shell=True)
            p1.wait()
            end = time.time()
            if end - beg > 300:
                break
        client.send('stage 2')
        time.sleep(20)
client.send('end')
client.client_close()

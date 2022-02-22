#!/usr/bin/python3
import os, sys, re, numpy, matplotlib, random
import copy
from control_vm import *

class PSO:
    dim = 4 #dim
    p_num = 8 #the number of particals
    step = 0
    iters = 10
    inf = 999999
    pi = 3.1415
    v_max = 1
    v_min = -1
    pos_max = 11
    pos_min = 0
    subdim = 2
    f_test = [] #the value of local minima
    pos = []
    spd = []
    p_best = [] #the position of local minima
    g_best = [] #the position of global minima
    vmm = None
    eprint_bool = True
    eprint_f = None
    
    def eprint(self, *args, **kwargs):
        self.eprint_f = open('pso.log', 'a+')
        print(*args, file=self.eprint_f, **kwargs)
        self.eprint_f.close()

    def fun_test(self, x):
        ipcs = self.vmm.test_benchmark(x)
        self.eprint('ipcs:', ipcs[0], ipcs[1], ipcs[2], ipcs[3])
        return ipcs[0] + ipcs[1]

    def fun_test_2(self, x):
        res = 0
        stat = [0] * 11
        for i in range(0, self.dim):
            for j in range(x[i][0], x[i][1]): 
                stat[j] += 1
        #for j in range(0, self.subdim):
        #    res += y[j]
        for j in range(0, 11):
            #res += 1.0 / (stat[j] + 1)
            res += stat[j]
        return res

    def fun_test_3(self, x):
        res = 0
        for i in range(0, self.dim):
            for j in range(0, self.subdim):
                res += x[i][j]
        return res

    def print_subdata(self, x):
        for j in range(0, self.dim):
            self.eprint("[%d %d], " % (x[j][0], x[j][1]), end = '')
        self.eprint("")

    def print_data(self, x):
        for i in range(0, self.p_num):
            self.eprint("%d: " % i, end = '')
            for j in range(0, self.dim):
                self.eprint("[%d %d], " % (x[i][j][0], x[i][j][1]), end = '')
            self.eprint("")
        self.eprint("")

    def sum_data(self, x):
        res = [0] * 11
        for i in range(0, self.dim):
            for j in range(x[i][0], x[i][1]):
                res[j] += 1
#self.eprint('sum_data: ', res)
        return res

    def cover_all(self, x):
        res = self.sum_data(x)
        for i in res:
            if i == 0:
                return False
        return True

    def find_data(self, x, t1, t2):
        res = []
        for i in range(0, self.dim):
            for j in range(x[i][0], x[i][1]):
                if j == t1 and i != t2:
                    res.append(i)
                    break
        if res:
            ind = random.randint(0, len(res) - 1)
            return res[ind]
        else:
            return -1

    def init(self):
        #new vmm
        self.vmm = VMM()
        self.vmm.pre_test_benchmark()

        for i in range(0, self.p_num):
            self.f_test.append(self.inf)
            self.p_best.append([])
        for i in range(0, self.p_num):
            rand0 = []
            rand1 = []
            for j in range(0, self.dim):
                rand00 = []
                rand11 = []
                rand00.append(int((11 + self.dim - 1) / self.dim) * j)
                rand00.append(min(int((11 + self.dim - 1 ) / self.dim) * (j + 1), 11))
                #t = random.randint(0, 9)
                #rand00.append(t)
                #rand00.append(random.randint(t + 1, 11))  
                rand11.append(random.random() * (self.v_max - self.v_min) + self.v_min)     
                rand11.append(random.random() * (self.v_max - self.v_min) + self.v_min)     
                rand0.append(rand00)
                rand1.append(rand11)
            self.pos.append(rand0)
            self.spd.append(rand1)
        #self.eprint("self.spd", self.spd)
        #self.eprint("self.pos", self.pos)
        for i in range(0, self.p_num):
            temp = self.fun_test(self.pos[i])
            self.f_test[i] = temp
            self.p_best[i] = copy.deepcopy(self.pos[i])
        maxPos = self.f_test.index(max(self.f_test))
        self.g_best = copy.deepcopy(self.p_best[maxPos])
        #self.eprint("self.p_best", self.p_best)
        #self.eprint("self.f_test", self.f_test)
        #self.eprint("minPos:", minPos)
        #self.eprint("self.g_best", self.g_best)
        for j in range(0, self.dim):
            if not j == self.dim - 1:
                self.eprint(self.g_best[j], ", ", end='')
            else:
                self.eprint(self.g_best[j], " - ", self.f_test[maxPos])
        self.eprint("=============================================")

    def run(self):
        omega_init = 0.5
        omega_end = 1e-3
        alpha = 1
        beta = 1
        #alpha = 1
        #beta = 1
        for step in range(1, self.iters):
            self.step = step
            self.eprint("step = %d" % self.step)
            #self.print_data(self.pos)
            #omega = (omega_init - omega_end) * (self.iters - step) / self.iters + omega_end;
            #omega = omega_init
            omega = 1
            #self.eprint("omega", omega)
            for i in range(0, self.p_num):
                rand0 = random.random()
                rand1 = random.random()

#                j = random.randint(0, self.dim - 1)
#                k = random.randint(0, self.subdim - 1)
#                l = random.randint(0, 1)
##self.eprint('j = %d, k = %d, l = %d' % (j, k, l))
#                if l == 0: #up
#                    if k == 0: #beg
#                        if self.pos[i][j][0] + 1 < self.pos[i][j][1]:
#                            if self.sum_data(self.pos[i])[self.pos[i][j][0]] > 1:
#                                self.pos[i][j][0] += 1
#                            else:
#                                ind = self.find_data(self.pos[i], self.pos[i][j][0] - 1, j)
#                                if not ind == -1:
#                                    self.pos[i][ind][1] += 1 #must be end
#                                    self.pos[i][j][0] += 1
#                    elif k == 1: #end
#                        if self.pos[i][j][1] + 1 <= 11:
#                            self.pos[i][j][1] += 1
#                elif l == 1: #down
#                    if k == 0: #beg
#                        if self.pos[i][j][0] - 1 > -1:
#                            self.pos[i][j][0] -= 1
#                    elif k == 1: #end
#                        if self.pos[i][j][1] - 1 >= self.pos[i][j][0]:
#                            if self.sum_data(self.pos[i])[self.pos[i][j][1] - 1] > 1:
#                                self.pos[i][j][1] -= 1
#                            else:
#                                ind = self.find_data(self.pos[i], self.pos[i][j][1], j)
#                                if not ind == -1:
#                                    self.pos[i][ind][0] -= 1 #must be beg
#                                    self.pos[i][j][1] -= 1

#self.print_subdata(self.pos[i])

                for j in range(0, self.dim):
                    for k in range(0, self.subdim):
#self.spd[i][j][k] = omega * self.spd[i][j][k] + alpha * rand0 * (self.p_best[i][j][k] - self.pos[i][j][k]) + beta * rand1 * (self.g_best[j][k] - self.pos[i][j][k])
#self.pos[i][j][k] = round(self.pos[i][j][k] + self.spd[i][j][k]);
                        old_spd = self.spd[i][j][k]
                        old_pos = self.pos[i][j][k]
                        new_spd = omega * self.spd[i][j][k] + alpha * rand0 * (self.p_best[i][j][k] - self.pos[i][j][k]) + beta * rand1 * (self.g_best[j][k] - self.pos[i][j][k])
                        new_pos = round(self.pos[i][j][k] + self.spd[i][j][k]);
                        if k == 0 and new_pos < self.pos[i][j][1] and new_pos >= 0:
                            self.spd[i][j][k] = new_spd
                            self.pos[i][j][k] = new_pos
                            if not self.cover_all(self.pos[i]):
                                self.spd[i][j][k] = old_spd
                                self.pos[i][j][k] = old_pos
                        elif k == 1 and new_pos > self.pos[i][j][0] and new_pos <= 11:
                            self.spd[i][j][k] = new_spd
                            self.pos[i][j][k] = new_pos
                            if not self.cover_all(self.pos[i]):
                                self.spd[i][j][k] = old_spd
                                self.pos[i][j][k] = old_pos

                        if self.spd[i][j][k] < self.v_min:
                            self.spd[i][j][k] = self.v_min
                        if self.spd[i][j][k] > self.v_max:
                            self.spd[i][j][k] = self.v_max
                        if self.pos[i][j][k] < self.pos_min:
                            self.pos[i][j][k] = self.pos_min
                        if self.pos[i][j][k] > self.pos_max:
                            self.pos[i][j][k] = self.pos_max
            #self.eprint("self.spd", self.spd)
            #self.eprint("self.pos", self.pos)
            for i in range(0, self.p_num):
                temp = self.fun_test(self.pos[i])
                self.eprint('%d: ' % i, self.pos[i], '-', temp)
                if temp > self.f_test[i]:
                    self.f_test[i] = temp
                    self.p_best[i] = copy.deepcopy(self.pos[i])
            maxPos = self.f_test.index(max(self.f_test))
            self.g_best = copy.deepcopy(self.p_best[maxPos])
            #self.eprint("self.p_best", self.p_best)
            #self.eprint("self.f_test", self.f_test)
            #self.eprint("minPos:", minPos)
            #self.eprint("self.g_best", self.g_best)
            #self.eprint(step, ": ")
            self.eprint("step: %03d" % self.step, end="   ")
            for j in range(0, self.dim):
                if not j == self.dim - 1:
                    self.eprint(self.g_best[j], ", ", end='')
                else:
                    self.eprint(self.g_best[j], " - ", self.f_test[maxPos])
            self.eprint("=============================================")

        self.vmm.aft_test_benchmark()

if __name__ == '__main__':
    pso = PSO()
    pso.init()
    pso.run()
    PSO()

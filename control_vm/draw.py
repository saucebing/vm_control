#!/Users/chenbingwei/anaconda3/bin/python
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import splev, splrep
import os, sys, time, subprocess, tempfile, re

out_temp = None
fileno = None

def exec_cmd(cmd):
	global out_temp, fileno
	out_temp = tempfile.SpooledTemporaryFile(bufsize=1000 * 1000)
	fileno = out_temp.fileno()
	p1 = subprocess.Popen(cmd, stdout = fileno, stderr = fileno, shell=True)
	return p1

def find_str(pattern, string):
	pat = re.compile(pattern)
	return pat.findall(string)[0]

def split_str(string):
	return filter(lambda x:x, string.split())

fname = sys.argv[1]
fig, ax = plt.subplots()
ax.plot()

#fig, ax = plt.subplots()
#ax.plot(data_exp, data_sum_ratio,'b-')
#ax.plot(data_exp, data_sum_ratio,'b*')
#ax.plot(star3_ind, star3_sum_ratio,'y*', label='(%d, %f)' % (star3_ind, star3_sum_ratio))
#ax.plot(star2_ind, star2_sum_ratio,'g*', label='(%d, %f)' % (star2_ind, star2_sum_ratio))
#ax.plot(star_ind, star_sum_ratio,'r*', label='(%d, %f)' % (star_ind, star_sum_ratio))
#ax.set_xlabel('Exponent')
#ax.set_ylabel('Cumulative Frequency')
#ax.set_title('Cumulative Frequency for Variable %s in %dth Iteration' % (var, dir_num))
#plt.legend(loc='lower right')
#min_data_exp = min(data_exp)
#max_data_exp = max(data_exp)
##print(min_data_exp, max_data_exp)
#    xticks2 = [int(i) for i in np.linspace(min_data_exp, max_data_exp, 10)]
##print(xticks2)
#    ax.set_xticks(xticks2)
#    ax.invert_xaxis()
##ax.annotate('(%d, %f)' % (star_ind, star_sum_ratio), xy=(star_ind - 1, star_sum_ratio - 0.04))
##ax.annotate('(%d, %f)' % (star2_ind, star2_sum_ratio), xy=(star2_ind - 1, star2_sum_ratio - 0.04))
##ax.annotate('(%d, %f)' % (star3_ind, star3_sum_ratio), xy=(star3_ind - 1, star3_sum_ratio - 0.04))
#    fig.savefig('%s/cf_%s.eps' % (root2, var), dpi=600, format='eps')
#    plt.close()
#
##  fig, ax = plt.subplots()
#    fig, ax = plt.subplots()
#    ax.bar(x=data_exp, height=data_ratio)
#    ax.set_xlabel('Exponent')
#    ax.set_ylabel('Frequency')
#    ax.set_title('Frequency for Variable %s in %dth Iteration' % (var, dir_num))
#    ax.set_xticks(xticks2)
#    fig.savefig('%s/fre_normal_%s.eps' % (root2, var), dpi=600, format='eps')
#    ax.set_ylabel('Frequency(log)')
#    ax.set_title('Frequency(log) for Variable %s in %dth Iteration' % (var, dir_num))
#    ax.set_yscale('log')
#    fig.savefig('%s/fre_log_%s.eps' % (root2, var), dpi=600, format='eps')
#    plt.close()
#
##plt.show()

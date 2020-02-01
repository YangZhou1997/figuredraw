#!/usr/bin/python3

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import rcParams
from collections import defaultdict
import glob
import re
from termcolor import colored
from util_serilize import *
from util_patterns import *
rcParams.update(params_line)

dx = 0/72.; dy = -15/72. 
offset = matplotlib.transforms.ScaledTranslation(dx, dy, plt.gcf().dpi_scale_trans)


nfinvoke = ['acl-fw', 'dpi', 'nat-tcp-v4', 'maglev', 'lpm', 'monitoring']
nfinvoke_legend = ["FW", "DPI", "NAT", "LB", "LPM", "Mon."]
cpus = ['detailed']
modes = ['none', 'tp']
l2_size = ['256kB', '512kB', '1MB', '2MB', '4MB']
datadir = 'gem5data/tp_10mins'

def bit_num(x):
    cnt = 0
    for i in range(32):
        if ((x >> i) & 1) == 1:
            cnt += 1
    return cnt        

singleprog = nfinvoke
multiprog = []
for i in range(1, 1 << 6):
    prog_set = []
    bitn = bit_num(i)
    if bitn not in [2, 4]:
        continue
    for j in range(6):
        if (i >> j) & 1 == 1:
            prog_set.append(nfinvoke[j])
    multiprog.append(prog_set)
# print(multiprog, len(multiprog))

def prog_set_to_cmd(prog_set):
    ret = ''
    num_prog = len(prog_set)
    if num_prog != 0:
        for i in range(num_prog - 1):
            ret += prog_set[i] + '.'
        ret += prog_set[-1]
    return ret
multiprog = list(map(lambda x: prog_set_to_cmd(x), multiprog))

# "throughput"/"l2missrate" -> "detailed" -> "monitoring" -> "standalone"/"nat-tcp-v4.lpm" -> "l2 cache size" -> "tp"/"none" -> value
rawdata = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float))))))

def extract_stdout(f_name):
    found = re.search('stdout_(.+?)\.out', f_name).group(1)
    return found

ticks_base = 1000000000000 # one second
def extract_lasting_times_contents(contents):
    if contents == '':
        print(colored('Error: stdout content null', 'red'))
        return 1
        
    r = re.search('Switched\ CPUS\ \@\ tick\ (.+?)\n', contents)
    if r: 
        start_ticks = int(r.group(1))
        start_pos = r.start()
    else:
        start_ticks = 0
        start_pos = 0
        print(colored('start_ticks not found', 'red'))

    r = re.search('reached\ the\ max\ instruction\ count\ \@\ (.+?)\n', contents)
    if r:
        end_ticks = int(r.group(1))
        end_pos = r.start()
    else:
        r = re.search('Exiting\ \@\ tick\ (.+?)\ ', contents)
        if r: 
            end_ticks = int(r.group(1))
            end_pos = r.start()
        else:
            end_ticks = 5 * ticks_base
            end_pos = len(contents)
            print(colored('end_ticks not found', 'red'))

    return (end_ticks - start_ticks) * 1.0 / ticks_base, contents[start_pos: end_pos]

def extract_packet_num(contents, nf):
    lines = contents.split('\n')
    start_num = 0
    end_num = 0
    for line in lines:
        if f'{nf} packets processed:' in line:
            start_num = int(line.split()[3])
            break
    for line in lines[::-1]:
        if f'{nf} packets processed:' in line:
            end_num = int(line.split()[3])
            break
    if start_num == 0:
        print(colored('start_num not found', 'red'))
    if end_num == 0:
        print(colored('end_num not found', 'red'))
    return end_num - start_num        

def load_data_throughput():
    f_list = glob.glob(f'./{datadir}/results/*.out')
    for f_name in f_list:
        # if 'TimingSimpleCPU' not in f_name:
        #     continue

        print(f_name)

        splits = extract_stdout(f_name).split('_')
        cpu = splits[0]
        nfs_str = splits[1]
        cachesize = splits[2]
        mode = splits[3]

        contents = open(f_name).read()
        index = contents.find('Switched CPUS @ tick ')
        contents = contents[index:]

        nfs = nfs_str.split('.')
        
        lasting_time, sim_contents = extract_lasting_times_contents(contents)
        for nf in nfs:
            packet_num = extract_packet_num(sim_contents, nf)
            th_value = packet_num / lasting_time / (1000000)
            
            corun_nfs_list = nfs.copy()
            corun_nfs_list.remove(nf)
            corun_nfs = prog_set_to_cmd(corun_nfs_list)
            if corun_nfs == '':
                corun_nfs = 'standalone'
            
            rawdata['throughput'][cpu][nf][corun_nfs][cachesize][mode] = th_value

            print('throughput', cpu, nf, corun_nfs, cachesize, mode, th_value)
        print('')


def extract_m5out(f_name):
    found = re.search('m5out\/(.+?)\/', f_name).group(1)
    return found

def extract_miss_rate(contents, nf, cpu_id, num_nfs, mode):
    if contents == '':
        print(colored('Error: m5out content null', 'red'))
        return 1

    lines = contents.split('\n')

    if num_nfs == 1:
        for line in lines:
            if 'system.l2.overall_miss_rate::total' in line:
                miss_rate = float(line.split()[1])
                return miss_rate
        print(colored('Error: m5out no l2.overall_miss_rate', 'red'))            
        return 1
    else: # num_nfs = 2 or 4:
        if mode == 'tp':
            for line in lines:
                if f'system.l2{cpu_id}.overall_miss_rate::total' in line:
                    miss_rate = float(line.split()[1])
                    return miss_rate
            print(colored(f'Error: m5out no l2{cpu_id}.overall_miss_rate', 'red'))            
        else: # none
            overall_accesses = 0
            overall_hits = 0
            overall_misses = 0
            for line in lines:
                if f'system.l2.overall_accesses::switch_cpus{cpu_id}.data' in line:
                    overall_accesses += int(line.split()[1])
                if f'system.l2.overall_accesses::switch_cpus{cpu_id}.inst' in line:
                    overall_accesses += int(line.split()[1])

                if f'system.l2.overall_hits::switch_cpus{cpu_id}.data' in line:
                    overall_hits += int(line.split()[1])
                if f'system.l2.overall_hits::switch_cpus{cpu_id}.inst' in line:
                    overall_hits += int(line.split()[1])

                if f'system.l2.overall_misses::switch_cpus{cpu_id}.data' in line:
                    overall_misses += int(line.split()[1])
                if f'system.l2.overall_misses::switch_cpus{cpu_id}.inst' in line:
                    overall_misses += int(line.split()[1])
            
            if overall_accesses == 0:
                print(colored('Error: m5out overall_accesses is zero', 'red'))
                return 1
            if overall_misses != 0:
                return overall_misses * 1.0 / overall_accesses
            if overall_hits != 0:
                return 1- overall_hits * 1.0 / overall_accesses
            
            print(colored('Error: m5out no overall_hits and overall_misses', 'red'))
            return 1

# system.l2.demand_hits::.switch_cpus0.data
def get_cpuids_from_name(nfs_str):
    nf_cpu_ids = defaultdict(lambda : [])
    nfs = nfs_str.split('.')
    idx = 0
    for nf in nfs:
        nf_cpu_ids[nf] = f'{idx}'
        idx += 1
    return nf_cpu_ids    

def load_data_l2cachemiss():
    f_list = glob.glob(f'./{datadir}/m5out/*')
    for f_name in f_list:
        # if 'TimingSimpleCPU_dpi-queue_' not in f_name:
        #     continue

        print(f_name)
        dir_name = extract_m5out(f_name + '/')
        
        splits = dir_name.split('_')
        cpu = splits[0]
        nfs_str = splits[1]
        cachesize = splits[2]
        mode = splits[3]

        f_name = f'{f_name}/{dir_name}_stats.txt'
        # print(f_name)
        contents = open(f_name).read()

        nf_cpu_ids = get_cpuids_from_name(nfs_str)
        nfs = nfs_str.split('.')
        num_nfs = len(nfs)

        for nf in nfs:
            corun_nfs_list = nfs.copy()
            corun_nfs_list.remove(nf)
            corun_nfs = prog_set_to_cmd(corun_nfs_list)
            if corun_nfs == '':
                corun_nfs = 'standalone'

            cpu_id = nf_cpu_ids[nf]
            # print(nf)
            # print(cpu_ids)

            miss_rate = extract_miss_rate(contents, nf, cpu_id, num_nfs, mode)

            rawdata['l2missrate'][cpu][nf][corun_nfs][cachesize][mode] = miss_rate
            print('l2missrate', cpu, nf, corun_nfs, cachesize, mode, miss_rate)
         
        print('')



def get_datavec_vary_cachesize(_type, _cpu, _nf):
    data_vec = list()
    for _cachesize in l2_size:
        tp = rawdata[_type][_cpu][_nf]["standalone"][_cachesize]['tp']
        none = rawdata[_type][_cpu][_nf]["standalone"][_cachesize]['none']
        if _type == 'throughput':
            data_vec.append((none - tp) / none)
        else:
            data_vec.append((tp - none) / none)
    return data_vec

# type: throughput or l2missrate
def plot_vary_cachesize(_type, _cpu):
    N = len(l2_size)
    ind = np.arange(N) * 10 + 10    # the x locations for the groups    
    width = 6.0/N       # the width of the bars: can also be len(x) sequence

    cnt = 0
    legends = list()
    for _nf in singleprog:
        data_vec = get_datavec_vary_cachesize(_type, _cpu, _nf)
        p1, = plt.plot(ind, data_vec, linestyle = linestyles[cnt], marker = markers[cnt], markersize = markersizes[cnt],
            color=colors[cnt], linewidth=3)
        legends.append(p1)
        cnt += 1

    plt.legend(legends, nfinvoke_legend, loc='best', ncol=2, frameon=False)
    if _type == 'throughput':
        plt.ylabel('Throughput degradation')
    elif _type == 'l2missrate':
        plt.ylabel('L2 missing rate increasing')

    plt.xticks(ind, l2_size, rotation=45, ha="right", rotation_mode="anchor")
    # plt.axes().set_ylim(ymin=0)

    # apply offset transform to all x ticklabels.
    for label in plt.axes().xaxis.get_majorticklabels():
        label.set_transform(label.get_transform() + offset)

    plt.tight_layout()
    plt.savefig(f'./figures/gem5/cachesize_{_type}_{_cpu}.pdf')
    plt.clf()

def get_datavec_vary_corun(_type, _cpu, _nf):
    cnt_vec = [0, 0, 0, 0]    
    data_vec = [0.0, 0.0, 0.0, 0.0]
    nf_combs = multiprog.copy()
    nf_combs.extend(singleprog)

    for nf_comb in nf_combs:
        if _nf in nf_comb:
            dot_num = nf_comb.count('.')
            if dot_num == 0:
                tp = rawdata[_type][_cpu][_nf]["standalone"]['4MB']['tp']
                none = rawdata[_type][_cpu][_nf]["standalone"]['4MB']['none']
                if _type == 'throughput':
                    data_vec[dot_num] += (none - tp) / none
                else:
                    data_vec[dot_num] += (tp - none) / none
            else:
                temp = nf_comb.split('.')
                temp.remove(_nf)
                nf_comb_exclude = prog_set_to_cmd(temp)
                tp = rawdata[_type][_cpu][_nf][nf_comb_exclude]['4MB']['tp']
                none = rawdata[_type][_cpu][_nf][nf_comb_exclude]['4MB']['none']
                if _type == 'throughput':
                    data_vec[dot_num] += (none - tp) / none
                else:
                    data_vec[dot_num] += (tp - none) / none
            cnt_vec[dot_num] += 1
    for i in [0, 1, 3]:
        data_vec[i] /= cnt_vec[i] * 1.0
    del data_vec[2]    
    return data_vec

# type: throughput or l2missrate
def plot_vary_corun(_type, _cpu):
    N = 3
    ind = np.arange(N) * 10 + 10    # the x locations for the groups    
    width = 6.0/N       # the width of the bars: can also be len(x) sequence

    cnt = 0
    legends = list()
    for _nf in singleprog:
        data_vec = get_datavec_vary_corun(_type, _cpu, _nf)
        p1, = plt.plot(ind, data_vec, linestyle = linestyles[cnt], marker = markers[cnt], markersize = markersizes[cnt],
            color=colors[cnt], linewidth=3)
        legends.append(p1)
        cnt += 1

    plt.legend(legends, nfinvoke_legend, loc='best', ncol=2, frameon=False)
    if _type == 'throughput':
        plt.ylabel('Throughput degradation')
    elif _type == 'l2missrate':
        plt.ylabel('L2 missing rate increasing')
        
    plt.xticks(ind, ['Standalone', 'Co-locate \nwith 1 NF', 'Co-locate \nwith 3 NFs'], rotation=45, ha="right", rotation_mode="anchor", fontsize=24)
    # plt.axes().set_ylim(ymin=0)

    # apply offset transform to all x ticklabels.
    for label in plt.axes().xaxis.get_majorticklabels():
        label.set_transform(label.get_transform() + offset)

    plt.tight_layout()
    plt.savefig(f'./figures/gem5/corun_{_type}_{_cpu}.pdf')
    plt.clf()


if __name__ == '__main__':
    plt.rc('text', usetex=True)
    font = fm.FontProperties(
       family = 'Gill Sans',
       fname = '/usr/share/fonts/truetype/adf/GilliusADF-Regular.otf')

    # load_data_throughput()
    # load_data_l2cachemiss()
    # write_to_file(rawdata, f'./{datadir}/drawdata/thrput_l2miss.res')

    rawdata = read_from_file(f'./{datadir}/drawdata/thrput_l2miss.res')
    for _type in ['throughput', 'l2missrate']:
        for _cpu in cpus:
            plot_vary_cachesize(_type, _cpu)
            plot_vary_corun(_type, _cpu)

#!/usr/bin/python3

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import rcParams
from collections import defaultdict
from util_patterns import *
import glob
rcParams.update(params_line)

dx = 0/72.; dy = -15/72. 
offset = matplotlib.transforms.ScaledTranslation(dx, dy, plt.gcf().dpi_scale_trans)

def get_thread(ori_name):
    switcher = {
        **dict.fromkeys(["1"], "16"), 
        **dict.fromkeys(["3"], "32"), 
        **dict.fromkeys(["7"], "48")
    }
    return switcher.get(ori_name, "Invalid core name %s" % (ori_name,))

# all_framesizes = ["64", "256", "512", "1024", "1500", "6000", "9000", "2000000"]
# all_legends = ["64B", "256B", "512B", "1KB", "1.5KB", "6KB", "9KB", "2MB"]
all_framesizes = ["64", "512", "1500", "9000"]
all_legends = ["64B", "512B", "1.5KB", "9KB"]
all_threads = ["16", "32", "48"]

t_val = defaultdict(lambda: defaultdict(list))
t_val_med = defaultdict(lambda: defaultdict(float))

# first load **all** files to the dict
def data_load(fileDir):
    f_list = glob.glob(fileDir + '/*')
    print(f_list)
    for f_name in f_list:
        with open(f_name, 'r') as f:
            raw_entry = f.readline()
            while raw_entry:
                entry_array = raw_entry.rstrip("\n").split(",")
                # print(entry_array)
                _framesize = entry_array[3]
                _thread = get_thread(entry_array[4])
                _t = float(entry_array[5])
                t_val[_framesize][_thread].append(float(_t))
                raw_entry = f.readline()
        # currently we only load the data of the first file
        # break 

# then process data to get graph drawing data
def process_draw_data():
    for _framesize in all_framesizes:
        for _thread in all_threads:
            try:
                t_val_med[_framesize][_thread] = np.median(t_val[_framesize][_thread])
            except IndexError:
                t_val_med[_framesize][_thread] = 0
            
def get_t_draw_data_vary_thread(_framesize):
    data_vec = list()
    for _thread in all_threads:
        data_vec.append(t_val_med[_framesize][_thread])
    # print(data_vec)
    return data_vec


def draw_t_trend_for_dpi_threads():
    data_load("./rawdata/dpi")
    process_draw_data()

    N = len(all_threads)
    ind = np.arange(N) * 10 + 10    # the x locations for the groups    

    cnt = 0
    legends = list()
    for _framesize in all_framesizes:
        data_vec = get_t_draw_data_vary_thread(_framesize)
        p1, = plt.plot(ind, data_vec, linestyle = linestyles[cnt], marker = markers[cnt], markersize = markersizes[cnt],
            color=colors[cnt], linewidth=2)
        print(str(all_framesizes[cnt]) + ": " + str(data_vec))        

        legends.append(p1)
        cnt += 1

    plt.legend(legends, all_legends, ncol=2, frameon=False, loc="lower center")
    plt.ylabel('Throughput (Mpps)')
    plt.xticks(ind, all_threads)
    plt.xlabel('\# of hardware threads')

    # apply offset transform to all x ticklabels.
    for label in plt.axes().xaxis.get_majorticklabels():
        label.set_transform(label.get_transform() + offset)

    plt.axes().set_ylim(ymin=0)

    plt.tight_layout()
    plt.savefig('./figures/dpi_thread/t_trend_dpithread.pdf')
    plt.clf()


if __name__ == '__main__':
    plt.rc('text', usetex=True)
    font = fm.FontProperties(
       family = 'Gill Sans',
       fname = '/usr/share/fonts/truetype/adf/GilliusADF-Regular.otf')

    draw_t_trend_for_dpi_threads()
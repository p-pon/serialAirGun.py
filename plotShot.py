# -*- coding: cp1251 -*-

import os, sys
import msvcrt
import time
import numpy
import matplotlib
import matplotlib.pyplot as plt

if len(sys.argv) < 2:  # количество подаваемых на компилятор аргументов
    # print((sys.argv))
    maxN = 0
    maxName = ''
    files = os.listdir()
    for f in files:
        if 'shot' in f:
            i = int(f[4:].split('.')[0])
            if i > maxN:
                maxN = i
                maxName = f

    if maxN == 0:
        sys.exit()
else:
    maxName = sys.argv[1]

print('Plotting ', maxName)

arr = numpy.loadtxt(maxName, dtype="int").astype(numpy.float64)

arr[:, 0] *= 0.1
arr[:, 1] *= 0.01
arr[:, 3] *= 0.1
arr[:, 4] *= 0.01

VCC1 = arr[:, 0]  # напряжение на 1й пушке красный
ICC1 = arr[:, 1]  # ток 1й пушки синий
FB1 = arr[:, 2]  # сигнал срабатывания 1 зеленый
VCC2 = arr[:, 3]  # напряжение на 2й пушке фиолетовый
ICC2 = arr[:, 4]  # ток 2й пушки голубой
FB2 = arr[:, 5]  # сигнал срабатывания 2 желтый

# сглаживание графиков #TODO попробовать разные сглаживания
spiky_data = [FB1, FB2]
for j in spiky_data:
    for i in range(2, len(j) - 2):
        j[i] = (j[i - 2] + j[i - 1] + j[i] + j[i + 1] + j[i + 2]) / 5

t = numpy.arange(0, len(VCC1) / 10, 0.1)

fig, [ax1, ax_feedback] = plt.subplots(1, 2)

color = 'tab:red'
ax1.set_xlabel('time (ms)')
ax1.set_ylabel('VCC, V', color=color)
ax1.plot(t, VCC1, color=color)
ax1.tick_params(axis='y', labelcolor=color)

ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

color = 'tab:blue'
ax2.set_ylabel('ICC, A', color=color)  # we already handled the x-label with ax1
ax2.plot(t, ICC1, color=color)
ax2.tick_params(axis='y', labelcolor=color)

# instantiate a second axes that shares the same x-axis - старый коммент
# графики feedback будут на другом поле
ax_feedback.spines['right'].set_position(('outward', 60))

color = 'tab:green'
ax_feedback.set_xlabel('time (ms)')
ax_feedback.set_ylabel('Feedback', color=color)  # we already handled the x-label with ax1

# if max(FB1) - min(FB1) < 100:
# 	avg = (max(FB1) + min(FB1)) / 2\


FB_list = [*FB1, *FB2]
maxlim = max(FB_list)
minlim = min(FB_list)
ax_feedback.set_ylim(minlim - 50, maxlim + 50)

ax_feedback.plot(t, FB1, color=color)
ax_feedback.tick_params(axis='y', labelcolor=color)

ax1.plot(t, VCC2, color='magenta')
ax2.plot(t, ICC2, color='cyan')
ax_feedback.plot(t, FB2, color='yellow')

fig.tight_layout()  # otherwise the right y-label is slightly clipped

plt.show()

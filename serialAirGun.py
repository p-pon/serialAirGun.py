# Program for interfacing with AirGun Controller

import os
import sys
import time
from array import array

import serial
import serial.tools.list_ports
import msvcrt
import struct
import shutil
import crcmod

import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

import numpy
from numpy import arange, savetxt
from pylab import *
import pandas as pd

import scipy as sp
import scipy.fft

# =========================== НАСТРОЙКИ ==========================================

# ---------- Настройки UART и общие, возможно изменение пользователем ---------------

portName      = 'COM3'  # Номер порта
portSpeed     = 115200  # Должно соответствовать настройке микроконтроллера
TOTAL_SAMPLES = 2000    # Максимальное число отсчетов ЧИСЛО_КАНАЛОВ * SAMPLES, Должно соответствовать настройке микроконтроллера

# ---------- Настройки для изменения пользователем ---------------

CHANNEL_MASK    = 1     # Маска каналов По умолчанию
SAMPLES         = 1000  # Число отсчетов после синхроимпульса По умолчанию
SAMPLING_PERIOD = 100   # Период выборки АЦП в микросекундах По умолчанию
INP_DELAY       = 30    # Задержка запуска после синхроимпульса в миллисекундах По умолчанию
DELAY1          = 0     # Задержка запуска после синхроимпульса в миллисекундах По умолчанию
DELAY2          = 0     # Задержка запуска после синхроимпульса в миллисекундах По умолчанию
min_time_ms     = 10    # Время начала поиска времени запуска в миллисекундах. По умолчанию
window_width    = 20    # Окно поиска времени запуска в миллисекундах. По умолчанию
Nround          = 5     # Количество отсчетов для округления при поиске пиков. По умолчанию
# ================================================================================

# Variables
maxN = 0  # Number of next dump file
inData = b''  # Incoming serial data
root = tk.Tk()  # Tkinter window
freeSpace = shutil.disk_usage('/').free  # Free space on disk
controlState = 0   # Текущее состояние Пушки: вкл/выкл
PickList1 = []  # Список моментов запуска пушки для округления
PickList2 = []  # Список моментов запуска пушки для округления


# расчет CRC32 короткой строки, длина строки должна быть кратной 4
def CalcCRC32(str, initial=0xFFFFFFFF):
    lStr = len(str)
    if lStr % 4:  # Случай длины, не кратной 4
        str += bytes(4 - lStr % 4)
        lStr = ((lStr + 4) // 4) * 4

    str2 = bytearray(lStr)
    for i in range(0, lStr, 4):
        str2[i] = str[i + 3]
        str2[i + 1] = str[i + 2]
        str2[i + 2] = str[i + 1]
        str2[i + 3] = str[i]
    # возвращает новую функцию.  rev-флаг, показывающий реверсивный порядок бит или нет
    if initial != 0xFFFFFFFF:  # если initial не по умолчанию,т.е. введена где-то еще
        crc32_func = crcmod.mkCrcFun(0x104c11db7, initCrc=initial, rev=False)
    else:
        crc32_func = crcmod.mkCrcFun(0x104c11db7, rev=False)
    y = crc32_func(str2)
    return y


# Подсчет единиц в числе
def CountOnes(data):
    return bin(data)[2:].count('1')


def SaveCommand(data):  # запись данных в SaveCommand.txt
    f = open("SaveCommand.txt", "ab")  # append binary
    f.write(data)
    f.close()


def SaveLog(data):
    Log = open("LOGFile.txt", "a")  # append
    Log.write(data)
    Log.close()


# Отправка Заголовка и данных на микроконтроллер (данные - параметр, заголовок создается)
def Send(data):
    header = struct.pack("=4s2L", b'COMM', len(data), CalcCRC32(data))
    header += struct.pack("=L", CalcCRC32(header))

    port.write(header + data)
    SaveCommand(header + data)


# Отправка Команды control на микроконтроллер
def SendControl(control):
    global controlState
    controlState = control
    data = struct.pack("=2H", 2, control)
    SaveCommand(b"[[SendControl %d]]" % control)
    Send(data)


# Отправка Команды Setup на микроконтроллер
def SendSetup(channelMask=CHANNEL_MASK, samples=SAMPLES, samplingPeriod=SAMPLING_PERIOD, delay1=DELAY1, delay2=DELAY2):
    # Проверка параметров
    nChan = CountOnes(channelMask)  # Подсчет единиц в маске = число каналов
    if nChan * samples > TOTAL_SAMPLES:
        samples = (TOTAL_SAMPLES // (nChan * 2)) * 2
        print('nSamples set to ', samples)
    # TODO вот тут менять delay
    data = struct.pack("=HHHHLL", 1, channelMask, samples, samplingPeriod, delay1, delay2)
    SaveCommand(b"[[SendSetup]]")
    SaveLog(str(list(map(str, (channelMask, samples, samplingPeriod, delay1, delay2, '\n')))))
    #TODO добавить Log file системное время, del1, del2, pick1, pick2
    Send(data)


# Sends command to Controller
def Fire():
    print('Fire!')
    global port
    # port.write(b'F')
    SendControl(0)


# Exit from program
def Exit():
    global root
    matplotlib.pyplot.close()
    root.destroy()


# Shows new plot
def Redraw(arr):
    global fig

    VCC1 = array(arr[:, 0] * 0.1)
    ICC1 = array(arr[:, 1] * 0.01)
    FB1 = arr[:, 2]

    VCC2 = array(arr[:, 3] * 0.1)
    ICC2 = array(arr[:, 4] * 0.01)
    FB2 = arr[:, 5]

    # сглаживание графиков #TODO попробовать разные сглаживания
    spiky_data = [FB1, FB2, VCC1, VCC2, ICC1, ICC2]
    for j in spiky_data:
        for i in range(2, len(j) - 2):
            j[i] = (j[i - 2] + j[i - 1] + j[i] + j[i + 1] + j[i + 2]) / 5

    t = arange(0, len(VCC1) / 10, 0.1)

    fig.clf()  # clear figure

    # Create graph with 3 vertical axes
    ax1, ax_feedback = fig.subplots(1, 2)
    # fig.subplots_adjust(left=0.07, bottom=0.04, top=0.97, hspace=0.13)

    color = 'tab:red'
    ax1.set_xlabel('time (ms)')
    ax1.set_ylabel('VCC, V', color=color)  # ''', label = 'Voltage chan 1'''
    ax1.plot(t, VCC1, color=color)
    ax1.tick_params(axis='y', labelcolor=color)

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

    color = 'tab:blue'
    ax2.set_ylabel('ICC, A', color=color)  # we already handled the x-label with ax1 ''', label = 'Voltage chan 1' '''
    ax2.plot(t, ICC1, color=color)
    ax2.tick_params(axis='y', labelcolor=color)

    # ax_feedback.spines['right'].set_position(('outward', 60))
    color = 'tab:green'
    ax_feedback.set_ylabel('Feedback', color=color)  # we already handled the x-label with ax1
    FB_list = [*FB1, *FB2]
    maxlim = max(FB_list)
    minlim = min(FB_list)
    ax_feedback.set_ylim(minlim - 50, maxlim + 50)
    ax_feedback.plot(t, FB1, color=color, label='feedback chan 1')
    ax_feedback.tick_params(axis='y', labelcolor=color)

    ax1.plot(t, VCC2, color='magenta', label='Voltage chan 2')
    ax2.plot(t, ICC2, color='cyan', label='Amperage chan 2')
    ax_feedback.plot(t, FB2, color='yellow', label='feedback chan 2')
    # ax1.legend(loc=2)
    # ax2.legend(loc=1)
    ax_feedback.legend()

    fig.tight_layout()  # repack for better appearance
    fig.canvas.draw()


# Get filename 'shotxxx' with maximum number
def GetMaxFileNumber():
    global freeSpace
    if freeSpace < 1000000:
        print('Free disk space is low. Only 1 file to save')
        return 1

    maxN = 0
    files = os.listdir()
    for f in files:
        if 'shot' in f:
            i = int(f[4:].split('.')[0])
            if i > maxN:
                maxN = i
                maxName = f
    maxN += 1
    return maxN


# Parsing of a Frame. Raw data -> array
def Parse1(inData):
    channelMask, samples, samplingPeriod = struct.unpack("=HHH", inData[:6])
    data = []
    # nChan = CountOnes(channelMask)
    ch2Offset = samples if (channelMask & 1) else 0

    for sample in range(samples):
        chan = []

        if channelMask & 1:
            offset = 8 + 6 * (sample)
            voltage, current, feedback = struct.unpack("=HHH", inData[offset: offset + 6])
            chan += [voltage, current, feedback]
        else:
            chan += [0, 0, 1500]

        if channelMask & 2:
            offset = 8 + 6 * (sample + samples)
            voltage, current, feedback = struct.unpack("=HHH", inData[offset: offset + 6])
            chan += [voltage, current, feedback]
        else:
            chan += [0, 0, 1500]

        data.append(chan)
    return array(data)


# (Periodic) Serial port check for Frame. If found, Calls Redraw()
def CheckSerial():
    global root
    global inData
    global port
    global maxN

    root.after(100, CheckSerial)  # Periodic callback

    try:
        size = port.inWaiting()
    except Exception as e:
        print('Serial exception. Reconnect')
        global portName, portSpeed, controlState
        try:
            time.sleep(3.0)
            port = serial.Serial(portName, portSpeed)
        except Exception as e1:
            print('Port %s Reconnect failed' % portName)
            return
        SendSetup()
        SendControl(controlState)
        print('Port %s Reconnect successfull' % portName)
        return

    if size:
        inData += port.read(size)

    while len(inData) >= 16:

        if b'DATA' not in inData:
            inData = inData[-3:]
            continue

        x = inData.find(b'DATA')
        inData = inData[x:]
        if len(inData) < 16:
            continue

        tag, dataSize, dataCRC, headerCRC = struct.unpack("=LLLL", inData[:16])
        if headerCRC != CalcCRC32(inData[:12]):
            print('headerCRC fail')
            inData = inData[4:]
            continue

        if len(inData) < 16 + dataSize:
            return

        if dataCRC != CalcCRC32(inData[16:16 + dataSize]):
            print('dataCRC fail')
            inData = inData[16 + dataSize:]
            continue

        inData = inData[16:]
        arr = Parse1(inData[:dataSize])
        filename = "shot%d.txt" % maxN

        global freeSpace
        if freeSpace >= 1000000:
            maxN += 1

        savetxt(filename, arr, fmt="%d")
        print('Data saved as:', filename)
        inData = inData[dataSize:]
        Redraw(arr)
        global PickList1, PickList2, DELAY1, DELAY2, del1, del2
        # DELAY1 += 3000

        PICK1, PICK2 = change_delay(arr)
        if PICK1 > 0:
            gun_1_delay = DELAY1 - PICK1 * 100
            print('gun_del= ', gun_1_delay)
            PickList1 = add_picks(PickList1, gun_1_delay)
        if PICK2 > 0:
            gun_2_delay = DELAY2 - PICK2 * 100
            PickList2 = add_picks(PickList2, gun_2_delay)

        if PickList1:
            DELAY1 = INP_DELAY * 1000 + round(numpy.mean(PickList1))
        if PickList2:
            DELAY2 = INP_DELAY * 1000 + round(numpy.mean(PickList2))
        if DELAY1 < 0:
            DELAY1 = 0
        if DELAY1 > INP_DELAY * 1000:
            DELAY1 = INP_DELAY * 1000
        if DELAY2 < 0:
            DELAY2 = 0
        if DELAY2 > INP_DELAY * 1000:
            DELAY2 = INP_DELAY * 1000
        print('DELAY= ', DELAY1)
        SendSetup(delay1=int(DELAY1), delay2=int(DELAY2))

        # Вывод значений DELAY в окно Tk
        del1 = tk.StringVar(value=str(DELAY1 / 1000))
        del2 = tk.StringVar(value=str(DELAY2 / 1000))
        tk.Entry(root, width=5, textvariable=del1, state='disabled').grid(row=2, column=12, sticky='s')
        tk.Entry(root, width=5, textvariable=del2, state='disabled').grid(row=2, column=13, sticky='s')


        # Визуализация сигнала



def change_delay(arr):  # Поиск момента запуска пушки
    def get_ch_delay(FB):
        df = pd.DataFrame(columns=['signal', '1', '2', '3'])
        df['signal'] = FB
        filt_low = []
        for i in range(df.shape[0]):
            filt_low.append(0)
        for i in range(6, df.shape[0] - 6):  # ширина фильтра  #for i in range(5, df.shape[0] - 5): # ширина фильтра
            filt_low[i] = 1
        sigfft_low = sp.fft.fft(df['signal'])
        for i in range(df.shape[0]):
            sigfft_low[i] *= filt_low[i]
        sigres_low = sp.fft.ifft(sigfft_low).real
        maxvalueid = sigres_low[min_time_ms10:min_time_ms10 + window_width10].argmax()

        filt = []  # сглаживание
        for i in range(df.shape[0]):
            filt.append(1)
        for i in range(100, df.shape[0] - 100):  # ширина фильтра
            filt[i] = 0
        sigfft = sp.fft.fft(df['signal'])
        for i in range(df.shape[0]):
            sigfft[i] *= filt[i]
        sigres = sp.fft.ifft(sigfft).real

        for i in range(df.shape[0]):
            df._set_value(i, 'signal', abs(sigres[i]))

        for i in range(1, df.shape[0] - 1):
            df._set_value(i, '3', 0)
            df._set_value(i, '1', df.iloc[i + 1]['signal'] - df.iloc[i]['signal'])  # расчет первая производная
            df._set_value(i, '2', df.iloc[i]['1'] - df.iloc[i - 1]['1'])  # расчет вторая производная

        for i in range(40, df.shape[0] - 4):
            # проверка по второй производной
            if df.iloc[i - 2]['2'] < 0 \
                    and df.iloc[i - 1]['2'] < 0 \
                    and df.iloc[i]['2'] < 0 \
                    and df.iloc[i + 1]['2'] < 0 \
                    and df.iloc[i + 2]['2'] < 0:
                for j in range(-2, 2):
                    df._set_value(i, '3', 570)
            # проверка по знаку первой производной
            if df.iloc[i - 4]['1'] > 0 \
                    and df.iloc[i - 3]['1'] > 0 \
                    and df.iloc[i - 2]['1'] > 0 \
                    and df.iloc[i - 1]['1'] > 0 \
                    and df.iloc[i + 1]['1'] < 0 \
                    and df.iloc[i + 2]['1'] < 0 \
                    and df.iloc[i + 3]['1'] < 0 \
                    and df.iloc[i + 4]['1'] < 0:
                # df.iloc[i]['1'] == 0 and
                df._set_value(i, '3', df.iloc[i]['3'] + 530)

        max_2 = df['2'].max()
        for i in range(10, df.shape[0] - 10):  # проверка по наличию максимального значения 1й производной
            up = False
            down = False
            condition_5 = False
            for j in range(-10, 0):
                if df.iloc[i + j]['1'] > max_2 * 0.9:
                    up = True
            for j in range(10):
                if df.iloc[i + j]['1'] < -max_2 * 0.9:
                    down = True
            if up and down:
                df._set_value(i, '3', df.iloc[i]['3'] + 510)
            for j in range(-10 + i, i + 10):
                if df.iloc[j]['signal'] < df.iloc[i]['signal'] * 0.7:
                    condition_5 = True
            if condition_5:
                df._set_value(i, '3', df.iloc[i]['3'] + 510)

        for i in range(950, df.shape[0]):  # избавляемся от краевых эффектов
            df._set_value(i, '3', 0)
        for i in range(0, min_time_ms10):
            df._set_value(i, '3', 0)

        df._set_value(maxvalueid, '3', df.iloc[maxvalueid]['3'] + 500)

        picks = df[df['3'] > (df['3'].max() * 0.95)].index.tolist()  # получение значений с максимальным совпадением признаков
        # print(picks)
        true_picks = []
        if 0 < len(picks) < 3:
            for i in picks:  # проверка пиков на то, есть в их округе значения меньше max*0.7
                if min_time_ms10 <= i <= (min_time_ms10 + window_width10):
                    true_picks.append(i)
            if true_picks:
                PICK = true_picks[0]
            else:
                PICK = -1
        else:
            PICK = -1
        return PICK
    def get_ch_delay1(FB):
        df = pd.DataFrame(columns=['signal', '1', '2', '3'])
        df['signal'] = FB
        filt_low = []
        for i in range(df.shape[0]):
            filt_low.append(0)
        for i in range(6, df.shape[0] - 6):  # ширина фильтра  #for i in range(5, df.shape[0] - 5): # ширина фильтра
            filt_low[i] = 1
        sigfft_low = sp.fft.fft(df['signal'])
        for i in range(df.shape[0]):
            sigfft_low[i] *= filt_low[i]
        sigres_low = sp.fft.ifft(sigfft_low).real
        maxvalueid = sigres_low[10:-10].argmax()

        filt = []  # сглаживание
        for i in range(df.shape[0]):
            filt.append(1)
        for i in range(100, df.shape[0] - 100):  # ширина фильтра
            filt[i] = 0
        sigfft = sp.fft.fft(df['signal'])
        for i in range(df.shape[0]):
            sigfft[i] *= filt[i]
        sigres = sp.fft.ifft(sigfft).real

        for i in range(df.shape[0]):
            df._set_value(i, 'signal', abs(sigres[i]))

        for i in range(1, df.shape[0] - 1):
            df._set_value(i, '3', 0)
            df._set_value(i, '1', df.iloc[i + 1]['signal'] - df.iloc[i]['signal'])  # расчет первая производная
            df._set_value(i, '2', df.iloc[i]['1'] - df.iloc[i - 1]['1'])  # расчет вторая производная

        for i in range(40, df.shape[0] - 4):
            # проверка по второй производной
            if df.iloc[i - 2]['2'] < 0 \
                    and df.iloc[i - 1]['2'] < 0 \
                    and df.iloc[i]['2'] < 0 \
                    and df.iloc[i + 1]['2'] < 0 \
                    and df.iloc[i + 2]['2'] < 0:
                for j in range(-2, 2):
                    df._set_value(i, '3', 570)
            # проверка по знаку первой производной
            if df.iloc[i - 4]['1'] > 0 \
                    and df.iloc[i - 3]['1'] > 0 \
                    and df.iloc[i - 2]['1'] > 0 \
                    and df.iloc[i - 1]['1'] > 0 \
                    and df.iloc[i + 1]['1'] < 0 \
                    and df.iloc[i + 2]['1'] < 0 \
                    and df.iloc[i + 3]['1'] < 0 \
                    and df.iloc[i + 4]['1'] < 0:
                # df.iloc[i]['1'] == 0 and
                df._set_value(i, '3', df.iloc[i]['3'] + 530)

        max_2 = df['2'].max()
        for i in range(10, df.shape[0] - 10):  # проверка по наличию максимального значения 1й производной
            up = False
            down = False
            condition_5 = False
            for j in range(-10, 0):
                if df.iloc[i + j]['1'] > max_2 * 0.9:
                    up = True
            for j in range(10):
                if df.iloc[i + j]['1'] < -max_2 * 0.9:
                    down = True
            if up and down:
                df._set_value(i, '3', df.iloc[i]['3'] + 510)
            for j in range(-10 + i, i + 10):
                if df.iloc[j]['signal'] < df.iloc[i]['signal'] * 0.7:
                    condition_5 = True
            if condition_5:
                df._set_value(i, '3', df.iloc[i]['3'] + 510)

        for i in range(min_time_ms + window_width, df.shape[0]):  # избавляемся от краевых эффектов
            df._set_value(i, '3', 0)
        for i in range(0, min_time_ms):
            df._set_value(i, '3', 0)

        df._set_value(maxvalueid, '3', df.iloc[maxvalueid]['3'] + 500)

        picks = df[df['3'] > (df['3'].max() * 0.95)].index.tolist()  # получение значений с максимальным совпадением признаков
        print(picks)
        true_picks = []
        if 0 < len(picks) < 3:
            for i in picks:  # проверка пиков на то, есть в их округе значения меньше max*0.7
                # if min_time_ms <= i <= (min_time_ms + window_width):
                #     true_picks.append(i)
                true_picks.append(i)
            PICK = true_picks[0] + min_time_ms
        else:
            PICK = -1
        return PICK
    def get_ch_delay2(FB):
        df = list(FB)
        return df.index(max(df[min_time_ms10:min_time_ms10+window_width10]), min_time_ms10, min_time_ms10+window_width10)

    min_time_ms10 = int(min_time_ms * 10)  # Пересчет из мс в мс/10 для работы программы
    window_width10 = int(window_width * 10)  # Пересчет из мс в мс/10 для работы программы

    FB1 = arr[:, 2]
    # [min_time_ms-10:min_time_ms + window_width+11]
    FB2 = arr[:, 5]
    # [min_time_ms:min_time_ms + window_width+1]
    P1, P2 = 0, 0
    if CHANNEL_MASK in (1, 3):
        P1 = get_ch_delay2(FB1)
        print('getchdel= ',P1)
    if CHANNEL_MASK in (2, 3):
        P2 = get_ch_delay(FB2)
    return P1, P2


def add_picks(pick_list, pick):
    pick_list.append(pick)
    if len(pick_list) > Nround:
        pick_list = pick_list[-Nround:]
    return pick_list


def Reconnect():
    global port
    port.close()
    port = serial.Serial(portName, portSpeed)


def Apply_changes():
    # print('first = ',var1.get(), '  |   second = ',var2.get())
    global CHANNEL_MASK  # включение и выключение каналов с помощью CheckButtons (квадратные)
    if var1.get():
        if var2.get():
            CHANNEL_MASK = 3
        else:
            CHANNEL_MASK = 1
    else:
        if var2.get():
            CHANNEL_MASK = 2
        else:
            CHANNEL_MASK = 0

    global INP_DELAY, Nround, min_time_ms, window_width
    INP_DELAY = float(delay.get())
    Nround = int(nround.get())
    min_time_ms = float(SW_start.get())
    window_width = float(SW_length.get())

    SendSetup(channelMask=CHANNEL_MASK, samples=SAMPLES, samplingPeriod=SAMPLING_PERIOD, delay1=DELAY1, delay2=DELAY2)
    print('Changes Applied')


# Open port
port = serial.Serial(portName, portSpeed)

maxN = GetMaxFileNumber()

# Prepare for drawing Tk + matplotlib
matplotlib.use('TkAgg')  # This defines the Python GUI backend to use for matplotlib
fig = plt.figure(figsize=(16, 8))  # Initialize matplotlib figure for graphing purposes #TODO обсудить размеры окна
canvas = FigureCanvasTkAgg(fig, master=root)  # Special type of "canvas" to allow for matplotlib graphing
plot_widget = canvas.get_tk_widget()
plot_widget.grid(row=0, column=0, columnspan=16)  # Add the plot to the tkinter widget

# create buttons
# num_list = [0, 1, 2, 3, 4, 5]
# col = iter(num_list)
tk.Button(root, text="Start", command=lambda x=1: SendControl(x)).grid(row=1, column=0,
                                                                       sticky='nesw')  # Create a tkinter button
tk.Button(root, text="Stop", command=lambda x=0: SendControl(x)).grid(row=1, column=1,
                                                                      sticky='nesw')  # Create a tkinter button
tk.Button(root, text="Fire", command=lambda x=0xFE: SendControl(x)).grid(row=1, column=2,
                                                                         sticky='nesw')  # Create a tkinter button
tk.Button(root, text="Exit", command=Exit).grid(row=1, column=3, sticky='nesw')  # Create a tkinter button

# Delays input
delay = tk.StringVar(value=str(INP_DELAY))
del1 = tk.StringVar(value=str(DELAY1))
del2 = tk.StringVar(value=str(DELAY2))

tk.Label(root, text='Delay, ms').grid(row=1, column=5, sticky='s')
tk.Spinbox(root, width=5, textvariable=delay, from_=0, to=1000).grid(row=2, column=5, sticky='s')
tk.Label(root, text='Delay 1ch, ms').grid(row=1, column=12, sticky='s')
tk.Entry(root, width=5, textvariable=del1, state='disabled').grid(row=2, column=12, sticky='s')
tk.Label(root, text='Delay 2ch, ms').grid(row=1, column=13, sticky='s')
tk.Entry(root, width=5, textvariable=del2, state='disabled').grid(row=2, column=13, sticky='s')

# Search pick input
SW_start = tk.StringVar(value=str(min_time_ms))
SW_length = tk.StringVar(value=str(window_width))
nround = tk.StringVar(value=str(Nround))


tk.Label(root, text='Search window,\n start, ms').grid(row=1, column=6, sticky='s')
tk.Spinbox(root, width=5, textvariable=SW_start, from_=0, to=1000).grid(row=2, column=6, sticky='s')
tk.Label(root, text='Search window,\n width, ms').grid(row=1, column=7, sticky='s')
tk.Spinbox(root, width=5, textvariable=SW_length, from_=0, to=1000).grid(row=2, column=7, sticky='s')

tk.Label(root, text='Round search pick, pcs').grid(row=1, column=8, sticky='s')
tk.Spinbox(root, width=5, textvariable=nround, from_=0, to=1000).grid(row=2, column=8, sticky='s')

tk.Button(root, text='Apply Changes', command=Apply_changes).grid(row=1, column=15, sticky='nesw')

# Channels checkbuttons
var1 = tk.IntVar(value=1)
var2 = tk.IntVar(value=0)

cb = tk.IntVar(value=1)
# tk.Label(root, text='Channel1').grid(row=2, column=0, sticky='s')
tk.Checkbutton(root, variable=var1, text='Channel1').grid(row=2, column=0, sticky='nesw')
# tk.Label(root, text='Channel2').grid(row=2, column=2, sticky='s')
tk.Checkbutton(root, variable=var2, text='Channel2').grid(row=2, column=2, sticky='nesw')


# send start commands
SendSetup()
SendControl(1)

# start Tk
root.after(100, CheckSerial)  # Periodic callback
root.protocol("WM_DELETE_WINDOW", Exit)  # Close window handler
root.mainloop()

port.close()
sys.exit()

"""Generate reproducible engineering figures from code, using synthetic RF data only.

I use these plots to explain the implementation. They are mathematical illustrations,
not antenna measurements, a calibrated spectrum, or a receiver-compatibility claim.
No serial, MQTT, Home Assistant or network operation is performed.
"""
import json
import math
import re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
from easywave_tx_frame import crc8, integrity_variant, word_bits, manchester_encode

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs/assets'
BLUE,TEAL,ORANGE,INK='#1565c0','#008577','#c46b14','#253344'


def save(fig,name):
    fig.savefig(ASSETS/(name+'.png'),dpi=180,bbox_inches='tight',facecolor='white')
    fig.savefig(ASSETS/(name+'.svg'),bbox_inches='tight',facecolor='white')
    plt.close(fig)


def main():
    ASSETS.mkdir(parents=True,exist_ok=True)
    timing=json.loads((ROOT/'addon/easywave_gateway/tx_timing.json').read_text())
    cpp=(ROOT/'src/main_gateway_v8.cpp').read_text(encoding='utf-8')
    deviation=float(re.search(r'deviationKHz\s*=\s*([\d.]+)F',cpp)[1])
    center=float(re.search(r'frequencyMHz\s*=\s*([\d.]+)F',cpp)[1])
    rate=timing['transport_bitrate_bps']
    chips_per_repeat=timing['physical_chips_per_repeat']
    holds,repeats=timing['hold_chips'],timing['repeats']
    samples_per_chip=(timing['payload_bytes']*8)//((chips_per_repeat+holds)*repeats)
    assert samples_per_chip==4
    chip_rate=rate/samples_per_chip
    chip_ms=1000/chip_rate
    assert math.ceil(timing['payload_bytes']*8/rate*1e6)==timing['burst_airtime_us']

    # The 32-bit integrity byte can be calculated; the independent captured tail
    # cannot. I choose tail=0 explicitly for this synthetic educational example.
    serial,key=0x012345,0
    prefix=(serial<<2)|key
    word=(prefix<<8)|(crc8(prefix.to_bytes(3,'big'))^0xB4)
    assert integrity_variant(word)==0
    data=word_bits(word)+[0]
    chips=np.array(manchester_encode(data),dtype=int)
    cycle=np.concatenate([chips,np.zeros(holds,dtype=int)])
    burst=np.tile(cycle,repeats)
    transport=np.repeat(burst,samples_per_chip)
    assert len(transport)==timing['payload_bytes']*8
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'axes.labelcolor':INK,'text.color':INK,'axes.titleweight':'bold'})

    fig,axes=plt.subplots(3,1,figsize=(11,6),sharex=True,layout='constrained')
    shown=data[:8]
    for ax,values,label,color,dt in [(axes[0],shown,'Source data bits',INK,chip_ms*2),
        (axes[1],chips[:16],'Manchester levels',BLUE,chip_ms),
        (axes[2],transport[:64],'Transport bits (4 per chip)',TEAL,1000/rate)]:
        x=np.arange(len(values)+1)*dt
        ax.step(x,np.r_[values,values[-1]],where='post',color=color,linewidth=2)
        ax.set(ylim=(-.25,1.4),yticks=[0,1],ylabel=label)
        ax.grid(axis='x',alpha=.15)
    for index,value in enumerate(shown):axes[0].text((index+.5)*chip_ms*2,1.13,str(value),ha='center')
    axes[2].plot((np.arange(64)+.5)*1000/rate,transport[:64],'.',color=TEAL,markersize=4)
    axes[2].text(chip_ms*16,1.15,'Each dot = one transport bit',ha='right',fontsize=9)
    axes[0].set_title('Manchester coding and byte-aligned 4× transport',loc='left')
    axes[-1].set_xlabel('Time (ms)')
    fig.supxlabel('Synthetic data · 0 → 01 → 0x0F; 1 → 10 → 0xF0 · no RF measurement',fontsize=9)
    save(fig,'manchester-transport')

    fig,axes=plt.subplots(2,1,figsize=(11,4.8),sharex=True,layout='constrained')
    t=np.arange(len(burst)+1)*chip_ms
    axes[0].step(t,np.r_[burst,burst[-1]],where='post',color=BLUE,linewidth=1)
    axes[0].set(yticks=[0,1],ylim=(-.2,1.5),ylabel='Logical level')
    for index in range(repeats):
        start=index*len(cycle)*chip_ms
        hold=start+chips_per_repeat*chip_ms
        axes[0].axvspan(hold,start+len(cycle)*chip_ms,color=ORANGE,alpha=.2)
        axes[0].text(start+chips_per_repeat*chip_ms/2,1.25,f'Repeat {index+1}: 33 data bits',ha='center',fontsize=9)
    axes[1].plot([0,t[-1]],[1,1],color=TEAL,linewidth=3)
    axes[1].set(ylim=(-.1,1.4),yticks=[0,1],yticklabels=['off','on'],ylabel='RF envelope model',xlabel='Time (ms)')
    axes[0].set_title('One continuous burst: three repeats and held levels',loc='left')
    axes[1].text(t[-1]/2,.55,f'{timing["payload_bytes"]} bytes · {len(transport)} transport bits · {timing["burst_airtime_us"]/1000:.3f} ms budget',ha='center')
    fig.supxlabel('Orange = 8 held chips per repeat, with carrier maintained · schematic envelope, not a recording',fontsize=9)
    save(fig,'continuous-burst')

    fig,axes=plt.subplots(2,1,figsize=(11,5),layout='constrained')
    offsets=(transport*2-1)*deviation
    x=np.arange(97)*1000/rate
    axes[0].step(x,np.r_[offsets[:96],offsets[95]],where='post',color=BLUE)
    axes[0].set(ylabel='Offset from carrier (kHz)',xlabel='Time (ms)',yticks=[-deviation,deviation])
    axes[0].set_title('Unshaped binary FSK: an explanatory frequency model',loc='left')
    # A continuous-phase complex baseband model, not the measured SX1262 output.
    oversampling=16
    fs=rate*oversampling
    frequencies=np.repeat(offsets*1000,oversampling)
    signal=np.exp(1j*2*np.pi*np.cumsum(frequencies)/fs)
    spectrum=np.abs(np.fft.fftshift(np.fft.fft(signal*np.hanning(len(signal)))))**2
    hz=np.fft.fftshift(np.fft.fftfreq(len(signal),1/fs))/1000
    db=10*np.log10(np.maximum(spectrum,1e-20)/spectrum.max())
    axes[1].plot(hz,db,color=TEAL,linewidth=.9)
    axes[1].set(xlim=(-65,65),ylim=(-65,3),xlabel='Baseband frequency offset (kHz)',ylabel='Relative model power (dB)')
    for position in (-deviation,deviation):axes[1].axvline(position,color=ORANGE,alpha=.4,linestyle='--')
    fig.supxlabel('Synthetic CPFSK baseband illustration · polarity shown by convention · no antenna, calibration, mask or certification',fontsize=8.5)
    save(fig,'fsk-model')

    fig,ax=plt.subplots(figsize=(10,3.5),layout='constrained')
    for row,tail in enumerate((0,1)):
        levels=manchester_encode(data[-3:-1]+[tail])
        x=np.arange(7)*chip_ms
        ax.step(x,np.r_[levels,levels[-1]]+row*2,where='post',color=BLUE if tail==0 else TEAL,linewidth=2)
        ax.text(0,row*2+1.3,f'Observed tail = {tail}',fontsize=10)
    ax.axvspan(4*chip_ms,6*chip_ms,color=ORANGE,alpha=.16)
    ax.set(yticks=[],ylim=(-.15,3.75),xlabel='Time (ms)',title='The same 32-bit prefix can require a different final Manchester pair')
    fig.supxlabel('The received final data bit is retained; the integrity model of the 32-bit prefix does not replace it.',fontsize=9)
    save(fig,'captured-tail')

    fig,ax=plt.subplots(figsize=(12,5.2),layout='constrained')
    ax.set(xlim=(0,12),ylim=(0,5.2));ax.axis('off')
    boxes=[(0.2,3.2,'Physical button\nEasywave RF'),(3.1,3.2,'Heltec V3\nSX1262 + firmware'),(6.0,3.2,'Local HA app\nPython + MQTT'),(8.9,3.2,'Home Assistant\nCatalogue + card')]
    for x,y,label in boxes:
        ax.add_patch(FancyBboxPatch((x,y),2.5,1,boxstyle='round,pad=.1',facecolor='#eef5fc',edgecolor=BLUE))
        ax.text(x+1.25,y+.5,label,ha='center',va='center',fontsize=11)
    for left,right in ((2.7,3.0),(5.6,5.9),(8.5,8.8)):
        ax.annotate('',xy=(right,3.9),xytext=(left,3.9),arrowprops={'arrowstyle':'->','color':BLUE,'lw':2})
        ax.annotate('',xy=(left,3.5),xytext=(right,3.5),arrowprops={'arrowstyle':'->','color':TEAL,'lw':2})
    ax.text(6,4.7,'Hell’s Gate: local reception and explicit manual commands',ha='center',fontsize=16,weight='bold')
    ax.text(1.4,2.6,'Receive / reproduce\nphysical radio levels',ha='center',fontsize=9)
    ax.text(4.35,2.6,'USB serial · 115200 baud\nRX events + correlated replies',ha='center',fontsize=9)
    ax.text(7.25,2.6,'Persistence + command queue\nretained observations / non-retained presses',ha='center',fontsize=9)
    ax.text(10.15,2.6,'Per-user language\noptional names and room grouping',ha='center',fontsize=9)
    ax.text(6,1.6,'Receive path → evidence → catalogue → usable button',ha='center',color=BLUE,fontsize=12)
    ax.text(6,1.1,'Manual press ← prepare observed frame ← one-shot TX ← correlated result',ha='center',color=TEAL,fontsize=12)
    ax.text(6,.35,'No cloud runtime dependency · no autonomous retransmission · lamp state is not inferred',ha='center',fontsize=10)
    save(fig,'pipeline-overview')

    metadata=dict(figure_kind='synthetic explanatory models; not RF measurements',synthetic_word=f'{word:08X}',captured_tail_chosen_for_illustration=0,
        transport_bitrate_bps=rate,physical_chip_rate_hz=chip_rate,data_bitrate_bps=chip_rate/2,
        samples_per_chip=samples_per_chip,payload_bytes=timing['payload_bytes'],burst_airtime_us=timing['burst_airtime_us'],
        configured_center_mhz=center,configured_deviation_khz=deviation,files=['manchester-transport','continuous-burst','fsk-model','captured-tail','pipeline-overview'])
    (ASSETS/'figure-parameters.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(figures=len(metadata['files']),synthetic=True,airtime_verified=True,radio_io=False)))


if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""Create a beat/chord timeline from a WAV file and an ordered chord list.

Uses only NumPy/SciPy so it can run in a free GitHub Actions runner.
The audio is an ephemeral input; output is compact JSON.
"""
import argparse, json, math, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks

PITCH = {"C":0,"C#":1,"DB":1,"D":2,"D#":3,"EB":3,"E":4,"F":5,"F#":6,"GB":6,"G":7,"G#":8,"AB":8,"A":9,"A#":10,"BB":10,"B":11}

def chord_template(name):
    m=re.match(r"^([A-Ga-g])([#b]?)([^/]*)",name)
    if not m: return np.ones(12)/12
    root=PITCH[(m.group(1)+m.group(2)).upper()]
    suffix=m.group(3).lower(); minor=suffix.startswith('m') and not suffix.startswith('maj')
    third=3 if minor else 4; fifth=6 if 'dim' in suffix else (8 if 'aug' in suffix else 7)
    t=np.full(12,.035); t[[root,(root+third)%12,(root+fifth)%12]]=1
    if '7' in suffix: t[(root+(11 if 'maj7' in suffix else 10))%12]=.7
    return t/np.linalg.norm(t)

def features(wav_path, hop=2205, frame=8192):
    sr,x=wavfile.read(wav_path)
    if x.ndim>1:x=x.mean(axis=1)
    x=x.astype(np.float32); x/=max(1,np.max(np.abs(x)))
    win=np.hanning(frame); freqs=np.fft.rfftfreq(frame,1/sr)
    valid=(freqs>=55)&(freqs<=4000); vf=freqs[valid]
    midi=np.rint(69+12*np.log2(vf/440)).astype(int); pcs=midi%12
    rows=[]; onset=[]; last=None
    for start in range(0,max(1,len(x)-frame),hop):
        mag=np.abs(np.fft.rfft(x[start:start+frame]*win))[valid]
        mag=np.log1p(10*mag); c=np.zeros(12)
        for p in range(12): c[p]=mag[pcs==p].sum()
        c/=np.linalg.norm(c)+1e-9; rows.append(c)
        onset.append(0 if last is None else np.maximum(c-last,0).sum()); last=c
    return sr,hop,np.asarray(rows),np.asarray(onset)

def tempo(onset,sr,hop):
    y=onset-onset.mean(); ac=np.correlate(y,y,mode='full')[len(y)-1:]
    lo=int((60/180)*sr/hop); hi=int((60/55)*sr/hop)
    lag=lo+int(np.argmax(ac[lo:hi+1])); bpm=60*sr/(hop*lag)
    while bpm>140:bpm/=2
    while bpm<70:bpm*=2
    return round(float(bpm),1)

def align(chroma,chords,seconds_per_frame,bpm):
    templates=np.stack([chord_template(c) for c in chords])
    # Aggregate chroma into half-beat cells. Chord changes can then occur only
    # on a musically meaningful grid rather than arbitrary 100 ms frames.
    cell_seconds=30.0/bpm
    frames_per_cell=cell_seconds/seconds_per_frame
    cells=max(1,int(round(len(chroma)/frames_per_cell)))
    beat_chroma=[]
    for cell in range(cells):
        lo=int(round(cell*frames_per_cell));hi=int(round((cell+1)*frames_per_cell))
        beat_chroma.append(chroma[lo:max(lo+1,min(len(chroma),hi))].mean(axis=0))
    emit=np.asarray(beat_chroma)@templates.T
    n,m=emit.shape; neg=-1e15
    # Allowed lengths: 2,3,4,5,6,8,10,12,16 beats (in half-beat cells).
    lengths=np.array([4,6,8,10,12,16,20,24,32],dtype=int)
    target=n/m
    prefix=np.vstack([np.zeros(m),np.cumsum(emit,axis=0)])
    dp=np.full((m+1,n+1),neg); back=np.full((m+1,n+1),-1,np.int32);dp[0,0]=0
    for j in range(1,m+1):
        earliest=j*int(lengths.min()); latest=min(n,j*int(lengths.max()))
        for end in range(earliest,latest+1):
            valid=lengths[(end-lengths>=0)&(dp[j-1,end-lengths]>neg/2)]
            if not len(valid):continue
            starts=end-valid
            seg=prefix[end,j-1]-prefix[starts,j-1]
            # Mild prior: prefer four/eight beats while allowing real variation.
            duration_penalty=.035*np.abs(valid-target)+np.where(np.isin(valid,[8,16]),-.08,0)
            values=dp[j-1,starts]+seg-duration_penalty
            k=int(np.argmax(values));dp[j,end]=values[k];back[j,end]=starts[k]
    # Permit a short unscored tail after the last written chord.
    candidates=np.where(dp[m]>neg/2)[0]
    end=int(candidates[np.argmax(dp[m,candidates]-.15*np.abs(candidates-n))])
    starts=np.zeros(m,dtype=int);cursor=end
    for j in range(m,0,-1):
        starts[j-1]=back[j,cursor];cursor=starts[j-1]
    timeline=[]
    for s,i in enumerate(starts):
        timeline.append({'time':round(float(i)*cell_seconds,3),'chord':chords[s],'sequenceIndex':s})
    return timeline

def main():
    ap=argparse.ArgumentParser();ap.add_argument('wav');ap.add_argument('song_json');ap.add_argument('output')
    a=ap.parse_args(); meta=json.loads(Path(a.song_json).read_text())
    sr,hop,chroma,onset=features(a.wav); bpm=tempo(onset,sr,hop)
    timeline=align(chroma,meta['chords'],hop/sr,bpm)
    out={k:v for k,v in meta.items() if k!='chords'}
    output_path=Path(a.output)
    if output_path.exists():
        try:
            previous=json.loads(output_path.read_text())
            if previous.get('sheet'): out['sheet']=previous['sheet']
        except (OSError,ValueError):
            pass
    out.update({'schemaVersion':1,'analysis':{'engine':'kc-numpy-chroma-v1','bpm':bpm,'timelineEntries':len(timeline)},'timeline':timeline})
    output_path.parent.mkdir(parents=True,exist_ok=True);output_path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()

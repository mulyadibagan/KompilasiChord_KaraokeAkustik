(function(global){
  'use strict';
  var engines=new WeakMap();
  function formant(c,s,out,f,q,l){var x=c.createBiquadFilter(),g=c.createGain();x.type='bandpass';x.frequency.value=f;x.Q.value=q;g.gain.value=l;s.connect(x);x.connect(g);g.connect(out);}
  function engineFor(c){
    var e=engines.get(c);if(e)return e;
    var env=c.createGain(),body=c.createGain(),warm=c.createGain(),hp=c.createBiquadFilter(),lp=c.createBiquadFilter(),comp=c.createDynamicsCompressor();
    var main=c.createOscillator(),chorus=c.createOscillator(),vib=c.createOscillator(),vibDepth=c.createGain(),pulse=c.createOscillator(),pulseDepth=c.createGain();
    var real=new Float32Array(14),imag=new Float32Array(14);imag[1]=1;imag[2]=.46;imag[3]=.29;imag[4]=.18;imag[5]=.12;imag[6]=.08;imag[7]=.055;imag[8]=.038;imag[9]=.025;
    main.setPeriodicWave(c.createPeriodicWave(real,imag,{disableNormalization:false}));chorus.type='triangle';main.frequency.value=220;chorus.frequency.value=220;chorus.detune.value=-7;
    body.gain.value=.72;warm.gain.value=.12;env.gain.value=.0001;hp.type='highpass';hp.frequency.value=95;hp.Q.value=.65;lp.type='lowpass';lp.frequency.value=3900;lp.Q.value=.5;
    comp.threshold.value=-29;comp.knee.value=24;comp.ratio.value=2.4;comp.attack.value=.025;comp.release.value=.24;
    main.connect(body);chorus.connect(warm);body.connect(env);warm.connect(env);formant(c,main,env,760,4.8,.30);formant(c,main,env,1180,6.2,.16);formant(c,main,env,2550,8.5,.045);
    vib.frequency.value=4.75;vibDepth.gain.value=0;vib.connect(vibDepth);vibDepth.connect(main.detune);vibDepth.connect(chorus.detune);
    pulse.frequency.value=1.9;pulseDepth.gain.value=.018;pulse.connect(pulseDepth);pulseDepth.connect(env.gain);
    env.connect(hp);hp.connect(lp);lp.connect(comp);comp.connect(c.destination);main.start();chorus.start();vib.start();pulse.start();
    e={env:env,main:main,chorus:chorus,vibDepth:vibDepth,lastEnd:0,frequency:220,level:.0001};engines.set(c,e);return e;
  }
  function attack(c,f,t,l){var o=c.createOscillator(),g=c.createGain();o.type='sine';o.frequency.setValueAtTime(f*2,t);g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(Math.max(.0002,l*.16),t+.008);g.gain.exponentialRampToValueAtTime(.0001,t+.105);o.connect(g);g.connect(c.destination);o.start(t);o.stop(t+.11);}
  function play(c,f,d,v,offset,opt){
    if(!c||!Number.isFinite(f)||f<=0)return false;opt=opt||{};var e=engineFor(c),start=c.currentTime+Math.max(0,offset||0),len=Math.max(.12,d||.25),end=start+len,level=Math.max(.0001,v||.03);
    var legato=e.lastEnd>c.currentTime&&start<=e.lastEnd+.11,glide=legato?Math.min(.11,Math.max(.035,len*.16)):.022,release=end+.035,releaseEnd=release+Math.min(.18,Math.max(.085,len*.22));
    e.main.frequency.cancelScheduledValues(start);e.chorus.frequency.cancelScheduledValues(start);e.main.frequency.setValueAtTime(Math.max(20,e.frequency),start);e.chorus.frequency.setValueAtTime(Math.max(20,e.frequency),start);e.main.frequency.exponentialRampToValueAtTime(f,start+glide);e.chorus.frequency.exponentialRampToValueAtTime(f,start+glide);
    e.vibDepth.gain.cancelScheduledValues(start);e.vibDepth.gain.setValueAtTime(0,start);if(len>.42){var vs=start+Math.min(.36,len*.48);e.vibDepth.gain.linearRampToValueAtTime(opt.vibrato?5.2:2.1,vs+.12);}
    e.env.gain.cancelScheduledValues(start);if(legato){e.env.gain.setValueAtTime(Math.max(.0001,e.level),start);e.env.gain.linearRampToValueAtTime(level,start+Math.min(.055,glide));}else{e.env.gain.setValueAtTime(.0001,start);e.env.gain.exponentialRampToValueAtTime(level,start+Math.min(.095,len*.28));attack(c,f,start,level);}
    e.env.gain.setValueAtTime(level,release);e.env.gain.exponentialRampToValueAtTime(.0001,releaseEnd);e.frequency=f;e.level=level;e.lastEnd=release;return true;
  }
  function stop(c){if(!c)return;var e=engines.get(c);if(!e)return;var now=c.currentTime;try{e.env.gain.cancelScheduledValues(now);e.env.gain.setValueAtTime(Math.max(.0001,e.level),now);e.env.gain.exponentialRampToValueAtTime(.0001,now+.055);e.vibDepth.gain.cancelScheduledValues(now);e.vibDepth.gain.linearRampToValueAtTime(0,now+.04);}catch(ignore){}e.lastEnd=0;e.level=.0001;}
  global.KCVocalGuide={play:play,stop:stop};
})(window);

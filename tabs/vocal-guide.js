(function(global){
  'use strict';

  var engines=new WeakMap();

  function engineFor(context){
    var engine=engines.get(context);
    if(engine)return engine;

    var voice=context.createGain();
    var direct=context.createGain();
    var input=context.createGain();
    var highpass=context.createBiquadFilter();
    var lowpass=context.createBiquadFilter();
    var compressor=context.createDynamicsCompressor();
    var source=context.createOscillator();
    var vibrato=context.createOscillator();
    var vibratoDepth=context.createGain();
    var real=new Float32Array(12),imag=new Float32Array(12);

    imag[1]=1;
    imag[2]=.58;
    imag[3]=.36;
    imag[4]=.24;
    imag[5]=.17;
    imag[6]=.12;
    imag[7]=.09;
    imag[8]=.065;
    source.setPeriodicWave(context.createPeriodicWave(real,imag,{disableNormalization:false}));
    source.frequency.value=220;

    voice.gain.value=.0001;
    direct.gain.value=.16;
    input.gain.value=.9;
    highpass.type='highpass';
    highpass.frequency.value=105;
    highpass.Q.value=.7;
    lowpass.type='lowpass';
    lowpass.frequency.value=3450;
    lowpass.Q.value=.55;
    compressor.threshold.value=-27;
    compressor.knee.value=22;
    compressor.ratio.value=2.2;
    compressor.attack.value=.018;
    compressor.release.value=.2;

    source.connect(direct);
    direct.connect(voice);
    [
      {frequency:720,q:5.2,gain:.72},
      {frequency:1160,q:6.4,gain:.34},
      {frequency:2520,q:8.5,gain:.13}
    ].forEach(function(spec){
      var filter=context.createBiquadFilter(),gain=context.createGain();
      filter.type='bandpass';
      filter.frequency.value=spec.frequency;
      filter.Q.value=spec.q;
      gain.gain.value=spec.gain;
      source.connect(filter);
      filter.connect(gain);
      gain.connect(voice);
    });

    vibrato.frequency.value=4.7;
    vibratoDepth.gain.value=1.2;
    vibrato.connect(vibratoDepth);
    vibratoDepth.connect(source.detune);
    voice.connect(input);
    input.connect(highpass);
    highpass.connect(lowpass);
    lowpass.connect(compressor);
    compressor.connect(context.destination);
    source.start();
    vibrato.start();

    engine={voice:voice,source:source,vibratoDepth:vibratoDepth,lastEnd:0,frequency:220,level:.0001};
    engines.set(context,engine);
    return engine;
  }

  function play(context,frequency,duration,volume,offset,options){
    if(!context||!Number.isFinite(frequency)||frequency<=0)return false;
    options=options||{};
    var engine=engineFor(context);
    var start=context.currentTime+Math.max(0,offset||0);
    var length=Math.max(.12,duration||.25);
    var end=start+length;
    var level=Math.max(.0001,volume||.03);
    var legato=engine.lastEnd>context.currentTime&&start<=engine.lastEnd+.09;
    var glide=Math.min(.065,Math.max(.026,length*.12));
    var releaseStart=end+.025;
    var releaseEnd=releaseStart+Math.min(.105,Math.max(.06,length*.2));

    engine.source.frequency.cancelScheduledValues(start);
    engine.source.frequency.setValueAtTime(engine.frequency,start);
    engine.source.frequency.exponentialRampToValueAtTime(frequency,start+(legato?glide:.018));
    engine.vibratoDepth.gain.cancelScheduledValues(start);
    engine.vibratoDepth.gain.setValueAtTime(options.vibrato?4.1:1.25,start);

    engine.voice.gain.cancelScheduledValues(start);
    if(legato){
      engine.voice.gain.setValueAtTime(Math.max(.0001,engine.level),start);
      engine.voice.gain.linearRampToValueAtTime(level,start+Math.min(.045,glide));
    }else{
      engine.voice.gain.setValueAtTime(.0001,start);
      engine.voice.gain.exponentialRampToValueAtTime(level,start+Math.min(.065,length*.25));
    }
    engine.voice.gain.setValueAtTime(level,releaseStart);
    engine.voice.gain.exponentialRampToValueAtTime(.0001,releaseEnd);

    engine.frequency=frequency;
    engine.level=level;
    engine.lastEnd=releaseStart;
    return true;
  }

  function stop(context){
    if(!context)return;
    var engine=engines.get(context);
    if(!engine)return;
    var now=context.currentTime;
    try{
      engine.voice.gain.cancelScheduledValues(now);
      engine.voice.gain.setValueAtTime(Math.max(.0001,engine.level),now);
      engine.voice.gain.exponentialRampToValueAtTime(.0001,now+.035);
    }catch(ignore){}
    engine.lastEnd=0;
    engine.level=.0001;
  }

  global.KCVocalGuide={play:play,stop:stop};
})(window);

(function(global){
  'use strict';

  var engines=new WeakMap();

  function engineFor(context){
    var engine=engines.get(context);
    if(engine)return engine;

    var input=context.createGain();
    var body=context.createBiquadFilter();
    var presence=context.createBiquadFilter();
    var compressor=context.createDynamicsCompressor();
    input.gain.value=.92;
    body.type='highpass';
    body.frequency.value=105;
    body.Q.value=.7;
    presence.type='lowpass';
    presence.frequency.value=3150;
    presence.Q.value=.55;
    compressor.threshold.value=-25;
    compressor.knee.value=20;
    compressor.ratio.value=2.4;
    compressor.attack.value=.012;
    compressor.release.value=.18;
    input.connect(body);
    body.connect(presence);
    presence.connect(compressor);
    compressor.connect(context.destination);
    engine={input:input,voices:[]};
    engines.set(context,engine);
    return engine;
  }

  function fadeVoice(voice,at,fast){
    if(!voice||voice.stopped)return;
    var end=Math.max(at+.012,at+(fast?.026:.055));
    try{
      voice.output.gain.cancelScheduledValues(at);
      voice.output.gain.setValueAtTime(Math.max(.0001,voice.level),at);
      voice.output.gain.exponentialRampToValueAtTime(.0001,end);
      voice.sources.forEach(function(source){source.stop(end+.025);});
    }catch(ignore){}
    voice.end=end;
    voice.stopped=true;
  }

  function play(context,frequency,duration,volume,offset,options){
    if(!context||!Number.isFinite(frequency)||frequency<=0)return false;
    options=options||{};
    var engine=engineFor(context);
    var start=context.currentTime+Math.max(0,offset||0);
    var length=Math.max(.12,duration||.25);
    var end=start+length;
    var level=Math.max(.0001,volume||.03);

    engine.voices=engine.voices.filter(function(voice){
      if(voice.end<=context.currentTime-.1)return false;
      if(!voice.stopped&&voice.end>start-.018)fadeVoice(voice,Math.max(context.currentTime,start-.016),true);
      return voice.end>context.currentTime-.1;
    });

    var output=context.createGain();
    var fundamental=context.createOscillator();
    var fundamentalGain=context.createGain();
    var warmth=context.createOscillator();
    var warmthGain=context.createGain();
    var formant=context.createBiquadFilter();
    var vibrato=context.createOscillator();
    var vibratoDepth=context.createGain();
    var attack=Math.min(.032,length*.2);
    var release=Math.min(.075,length*.3);

    output.gain.setValueAtTime(.0001,start);
    output.gain.exponentialRampToValueAtTime(level,start+attack);
    output.gain.setValueAtTime(level,Math.max(start+attack,end-release));
    output.gain.exponentialRampToValueAtTime(.0001,end);
    output.connect(engine.input);

    fundamental.type='triangle';
    fundamental.frequency.setValueAtTime(frequency,start);
    fundamentalGain.gain.value=.76;
    fundamental.connect(fundamentalGain);
    fundamentalGain.connect(output);

    warmth.type='sawtooth';
    warmth.frequency.setValueAtTime(frequency,start);
    warmthGain.gain.value=.16;
    formant.type='bandpass';
    formant.frequency.value=frequency<210?720:880;
    formant.Q.value=2.1;
    warmth.connect(formant);
    formant.connect(warmthGain);
    warmthGain.connect(output);

    vibrato.frequency.value=4.8;
    vibratoDepth.gain.setValueAtTime(0,start);
    vibratoDepth.gain.linearRampToValueAtTime(options.vibrato?4.2:1.15,Math.min(end,start+.28));
    vibrato.connect(vibratoDepth);
    vibratoDepth.connect(fundamental.detune);
    vibratoDepth.connect(warmth.detune);

    [fundamental,warmth,vibrato].forEach(function(source){source.start(start);source.stop(end+.025);});
    engine.voices.push({output:output,sources:[fundamental,warmth,vibrato],level:level,end:end,stopped:false});
    return true;
  }

  function stop(context){
    if(!context)return;
    var engine=engines.get(context);
    if(!engine)return;
    var now=context.currentTime;
    engine.voices.forEach(function(voice){fadeVoice(voice,now,true);});
    engine.voices=[];
  }

  global.KCVocalGuide={play:play,stop:stop};
})(window);

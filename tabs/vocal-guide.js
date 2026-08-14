(function(global){
  'use strict';

  function play(context,frequency,duration,volume,offset,options){
    if(!context||!Number.isFinite(frequency)||frequency<=0)return false;
    options=options||{};
    var start=context.currentTime+Math.max(0,offset||0);
    var length=Math.max(.13,duration||.25);
    var end=start+length;
    var release=Math.min(.09,length*.28);
    var level=Math.max(.0001,volume||.03);
    var clearPitch=!!options.clearPitch;

    var output=context.createGain();
    var compressor=context.createDynamicsCompressor();
    compressor.threshold.value=-24;
    compressor.knee.value=18;
    compressor.ratio.value=3;
    compressor.attack.value=.004;
    compressor.release.value=.12;
    output.gain.setValueAtTime(.0001,start);
    output.gain.exponentialRampToValueAtTime(level,start+.012);
    output.gain.setValueAtTime(level,Math.max(start+.018,end-release));
    output.gain.exponentialRampToValueAtTime(.0001,end);
    output.connect(compressor);
    compressor.connect(context.destination);

    // Jalur nada dasar dipertahankan agar tinggi nada tetap jelas di speaker tablet.
    var fundamental=context.createOscillator();
    var fundamentalGain=context.createGain();
    fundamental.type=clearPitch?'sine':'triangle';
    fundamental.frequency.setValueAtTime(frequency,start);
    fundamentalGain.gain.value=clearPitch?1:.78;
    fundamental.connect(fundamentalGain);
    fundamentalGain.connect(output);

    // Harmonik vokal memberi warna "aa" tanpa menutupi nada dasarnya.
    var harmonic=context.createOscillator();
    var harmonicGain=context.createGain();
    var formant=context.createBiquadFilter();
    harmonic.type=clearPitch?'sine':'sawtooth';
    harmonic.frequency.setValueAtTime(clearPitch?frequency*2:frequency,start);
    harmonicGain.gain.value=clearPitch?.11:.22;
    formant.type='bandpass';
    formant.frequency.value=frequency<220?780:920;
    formant.Q.value=2.4;
    if(clearPitch)harmonic.connect(harmonicGain);
    else{harmonic.connect(formant);formant.connect(harmonicGain);}
    harmonicGain.connect(output);

    // Penanda singkat pada awal nada membantu membedakan perpindahan not.
    var marker=context.createOscillator();
    var markerGain=context.createGain();
    marker.type='sine';
    marker.frequency.setValueAtTime(frequency,start);
    markerGain.gain.setValueAtTime(level*(clearPitch?.48:.32),start);
    markerGain.gain.exponentialRampToValueAtTime(.0001,start+Math.min(clearPitch?.075:.055,length*.35));
    marker.connect(markerGain);
    markerGain.connect(compressor);

    var vibrato=context.createOscillator();
    var vibratoDepth=context.createGain();
    vibrato.frequency.value=5.0;
    vibratoDepth.gain.setValueAtTime(0,start);
    vibratoDepth.gain.linearRampToValueAtTime(clearPitch?0:(options.vibrato?5:1.5),Math.min(end,start+.24));
    vibrato.connect(vibratoDepth);
    vibratoDepth.connect(fundamental.detune);
    vibratoDepth.connect(harmonic.detune);

    [fundamental,harmonic,marker,vibrato].forEach(function(source){source.start(start);});
    fundamental.stop(end);
    harmonic.stop(end);
    marker.stop(Math.min(end,start+.065));
    vibrato.stop(end);
    return true;
  }

  global.KCVocalGuide={play:play};
})(window);

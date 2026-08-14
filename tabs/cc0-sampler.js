(function(global){
  'use strict';
  var scriptBase=new URL('.',document.currentScript.src);
  function asset(path){return new URL('../samples/cc0/'+path,scriptBase).href;}
  var manifest={
    guitar:[
      {note:'A2',url:asset('emilyguitar/a2.wav')},{note:'D#3',url:asset('emilyguitar/eb3.wav')},
      {note:'A3',url:asset('emilyguitar/a3.wav')},{note:'D#4',url:asset('emilyguitar/eb4.wav')},
      {note:'A4',url:asset('emilyguitar/a4.wav')},{note:'D#5',url:asset('emilyguitar/eb5.wav')}
    ],
    bass:[
      {note:'E2',url:asset('big-little-bass/e2.wav')},{note:'A2',url:asset('big-little-bass/a2.wav')},
      {note:'D3',url:asset('big-little-bass/d3.wav')},{note:'G3',url:asset('big-little-bass/g3.wav')},
      {note:'C4',url:asset('big-little-bass/c4.wav')}
    ],
    drums:{
      kick:asset('virtuosity-drums/kick.flac'),snare:asset('virtuosity-drums/snare.flac'),
      hihat:asset('virtuosity-drums/hihat.flac'),crash:asset('virtuosity-drums/crash.flac')
    }
  };
  var state={context:null,buffers:{guitar:[],bass:[],drums:{}},loadPromise:null,loaded:false,failures:0,active:[]};
  function noteMidi(note){var match=/^([A-G])(#?)(-?\d)$/.exec(note||'');if(!match)return 69;var semis={C:0,D:2,E:4,F:5,G:7,A:9,B:11};return(Number(match[3])+1)*12+semis[match[1]]+(match[2]?1:0);}
  function midiName(midi){var names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];return names[midi%12]+(Math.floor(midi/12)-1);}
  function decode(url){return fetch(url).then(function(response){if(!response.ok)throw new Error('HTTP '+response.status);return response.arrayBuffer();}).then(function(data){return state.context.decodeAudioData(data);});}
  function load(context){
    if(state.loadPromise)return state.loadPromise;
    state.context=context;var jobs=[];
    ['guitar','bass'].forEach(function(group){manifest[group].forEach(function(item){jobs.push(decode(item.url).then(function(buffer){state.buffers[group].push({note:item.note,midi:noteMidi(item.note),buffer:buffer});}).catch(function(){state.failures++;}));});});
    Object.keys(manifest.drums).forEach(function(name){jobs.push(decode(manifest.drums[name]).then(function(buffer){state.buffers.drums[name]=buffer;}).catch(function(){state.failures++;}));});
    state.loadPromise=Promise.all(jobs).then(function(){state.loaded=state.buffers.guitar.length>0||state.buffers.bass.length>0||Object.keys(state.buffers.drums).length>0;return state.loaded;});
    return state.loadPromise;
  }
  function remember(source){state.active.push(source);source.onended=function(){var index=state.active.indexOf(source);if(index>=0)state.active.splice(index,1);};}
  function stopAll(){state.active.slice().forEach(function(source){try{source.stop();}catch(ignore){}});state.active=[];}
  function nearest(group,note){var list=state.buffers[group]||[],target=noteMidi(note),best=null;list.forEach(function(sample){if(!best||Math.abs(sample.midi-target)<Math.abs(best.midi-target))best=sample;});return best;}
  function playNote(context,group,note,duration,volume,offset,options){
    var sample=nearest(group,note);if(!sample)return false;
    var source=context.createBufferSource(),gain=context.createGain(),t=context.currentTime+(offset||0),rate=Math.pow(2,(noteMidi(note)-sample.midi)/12),available=sample.buffer.duration/rate,end=t+Math.max(.05,Math.min(duration,available-.01));source.buffer=sample.buffer;source.playbackRate.value=rate;
    gain.gain.setValueAtTime(.0001,t);gain.gain.exponentialRampToValueAtTime(Math.max(.0002,volume),t+.008);gain.gain.setValueAtTime(Math.max(.0002,volume*.82),Math.max(t+.01,end-.06));gain.gain.exponentialRampToValueAtTime(.0001,end);
    if(options&&options.drive){var drive=context.createWaveShaper(),filter=context.createBiquadFilter(),curve=new Float32Array(512);for(var i=0;i<curve.length;i++){var x=i*2/(curve.length-1)-1;curve[i]=Math.tanh(x*(options.strong?3.4:2.35));}drive.curve=curve;drive.oversample='2x';filter.type='lowpass';filter.frequency.value=options.strong?4200:3300;source.connect(drive);drive.connect(filter);filter.connect(gain);}else source.connect(gain);
    gain.connect(context.destination);remember(source);source.start(t);source.stop(end+.015);return true;
  }
  function playFreq(context,group,freq,duration,volume,offset,options){return playNote(context,group,midiName(Math.round(69+12*Math.log(freq/440)/Math.LN2)),duration,volume,offset,options);}
  function playDrum(context,name,volume,offset){var buffer=state.buffers.drums[name];if(!buffer)return false;var source=context.createBufferSource(),gain=context.createGain(),t=context.currentTime+(offset||0);source.buffer=buffer;gain.gain.value=Math.max(.0001,volume);source.connect(gain);gain.connect(context.destination);remember(source);source.start(t);return true;}
  function status(){return{loaded:state.loaded,failures:state.failures};}
  global.KCSampler={load:load,playNote:playNote,playFreq:playFreq,playDrum:playDrum,stopAll:stopAll,status:status};
})(window);

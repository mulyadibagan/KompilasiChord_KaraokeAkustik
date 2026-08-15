(function(){
  'use strict';
  if(window.KCHarmony)return;
  var PITCH={C:0,'C#':1,D:2,'D#':3,E:4,F:5,'F#':6,G:7,'G#':8,A:9,'A#':10,B:11};
  var RANGE={lead:[52,81,64],vocal:[48,76,61],bass:[28,55,40]};

  function chordInfo(name){
    var match=/^([A-G](?:#)?)(.*)$/.exec(String(name||'').split('/')[0].trim());
    if(!match)return null;
    var root=PITCH[match[1]],suffix=match[2]||'',minor=suffix.charAt(0)==='m'&&suffix.indexOf('maj')!==0;
    var fifth=suffix.indexOf('dim')>=0||suffix.indexOf('b5')>=0?6:7;
    return{root:root,tones:[root,(root+(minor?3:4))%12,(root+fifth)%12]};
  }
  function inRangeCandidates(midi,range){
    var out=[];for(var n=midi-36;n<=midi+36;n+=12)if(n>=range[0]&&n<=range[1])out.push(n);
    return out.length?out:[Math.max(range[0],Math.min(range[1],midi))];
  }
  function octaveSmooth(midi,previous,range){
    var target=previous==null?range[2]:previous,candidates=inRangeCandidates(midi,range);
    return candidates.reduce(function(best,n){return Math.abs(n-target)<Math.abs(best-target)?n:best;},candidates[0]);
  }
  function nearestTone(midi,tones,range,rootOnly){
    var allowed=rootOnly?[tones[0],tones[2]]:tones,best=midi,distance=99;
    for(var n=range[0];n<=range[1];n++)if(allowed.indexOf((n%12+12)%12)>=0&&Math.abs(n-midi)<distance){best=n;distance=Math.abs(n-midi);}
    return{midi:best,distance:distance};
  }
  function harmonize(kind,midi,chord,slot,duration,range){
    var info=chordInfo(chord);if(!info)return midi;
    var pitch=(midi%12+12)%12;if(info.tones.indexOf(pitch)>=0)return midi;
    var strong=slot%4===0||duration>=4,nearest=nearestTone(midi,info.tones,range,kind==='bass');
    if(kind==='bass'&&strong&&nearest.distance<=3)return nearest.midi;
    if((kind==='lead'||kind==='vocal')&&strong&&nearest.distance<=1)return nearest.midi;
    return midi;
  }
  function removePitchSpikes(events){
    return events.filter(function(event,index){
      if(event[1]>1||index===0||index===events.length-1)return true;
      var before=events[index-1][2],after=events[index+1][2],note=event[2];
      return !(Math.abs(before-after)<=4&&Math.abs(note-before)>=8&&Math.abs(note-after)>=8);
    });
  }
  function limitDensity(events,kind){
    var maximum=kind==='bass'?5:kind==='vocal'?6:7;if(events.length<=maximum)return events;
    var ranked=events.map(function(event,index){var beat=event[0]%4===0?4:0;return{event:event,index:index,score:event[1]*3+beat};});
    ranked.sort(function(a,b){return b.score-a.score||a.index-b.index;});
    var keep=ranked.slice(0,maximum).map(function(item){return item.index;});
    return events.filter(function(_,index){return keep.indexOf(index)>=0;});
  }
  function cleanBar(raw,kind,barIndex,chordAt,previous){
    var range=RANGE[kind],events=(raw||[]).filter(function(e){return e&&e.length>=3&&isFinite(e[0])&&isFinite(e[1])&&isFinite(e[2]);}).map(function(e){return[Math.max(0,Math.min(15,Math.round(e[0]))),Math.max(1,Math.round(e[1])),Math.round(e[2])];});
    events.sort(function(a,b){return a[0]-b[0]||b[1]-a[1];});
    events=events.filter(function(e,index){return index===0||e[0]!==events[index-1][0];});
    events.forEach(function(event){var midi=octaveSmooth(event[2],previous.value,range);midi=harmonize(kind,midi,chordAt(barIndex,event[0]),event[0],event[1],range);midi=octaveSmooth(midi,previous.value,range);event[2]=midi;previous.value=midi;});
    events=removePitchSpikes(events);events=limitDensity(events,kind);events.sort(function(a,b){return a[0]-b[0];});
    events.forEach(function(event,index){var next=index+1<events.length?events[index+1][0]:16;event[1]=Math.max(1,Math.min(event[1],next-event[0],16-event[0]));});
    return events;
  }
  function clean(transcription,chordAt){
    if(!transcription||transcription.__harmonyCleaned)return transcription;
    ['lead','vocal','bass'].forEach(function(kind){
      var bars=transcription[kind]||[],previous={value:null};
      transcription[kind]=bars.map(function(events,barIndex){return cleanBar(events,kind,barIndex,chordAt,previous);});
    });
    try{Object.defineProperty(transcription,'__harmonyCleaned',{value:true});}catch(ignore){transcription.__harmonyCleaned=true;}
    return transcription;
  }
  function resetMix(storageKey,defaults){
    try{if(localStorage.getItem('kcTabMixVersion')!==storageKey){localStorage.setItem('kcTabVolumes',JSON.stringify(defaults));localStorage.setItem('kcTabMixVersion',storageKey);return true;}}catch(ignore){}
    return false;
  }
  window.KCHarmony={clean:clean,resetMix:resetMix};
})();

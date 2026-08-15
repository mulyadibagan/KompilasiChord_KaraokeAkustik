(function(){
  'use strict';
  var sections=[
    {key:'intro',label:'Intro',length:8},
    {key:'verse1',label:'Verse 1',length:16},
    {key:'reff',label:'Verse 2',length:16},
    {key:'verse2',label:'Pengantar Reff',length:8},
    {key:'reff2',label:'Reff',length:16},
    {key:'interlude',label:'Interlude',length:8},
    {key:'verse3',label:'Verse Akhir',length:16},
    {key:'reff3',label:'Reff Akhir',length:14},
    {key:'outro',label:'Outro',length:4}
  ];
  function repeat(pattern,times){var out=[];for(var i=0;i<times;i++)out=out.concat(pattern.map(function(chord){return[chord];}));return out;}
  var chords=[];
  chords=chords.concat(repeat(['Bb','C','Dm','F'],2));
  chords=chords.concat(repeat(['Bb','C','Dm','F'],4));
  chords=chords.concat(repeat(['Bb','C','Dm','F'],4));
  chords=chords.concat(repeat(['Bb','C','Dm','F'],2));
  chords=chords.concat(repeat(['Dm','Bb','F','C'],4));
  chords=chords.concat(repeat(['Bb','C','Dm','F'],2));
  chords=chords.concat(repeat(['Bb','C','Dm','F'],4));
  chords=chords.concat(repeat(['Bb','C','Dm','F'],3),[['Bb'],['C']]);
  chords=chords.concat([['Dm'],['F'],['Bb'],['Bb']]);

  var tones={F:[65,69,72,69],C:[64,67,72,67],Dm:[65,69,74,69],Bb:[65,70,74,70],Am:[64,69,72,69],Gm:[67,70,74,70]};
  var bass={F:[41,48],C:[36,43],Dm:[38,45],Bb:[34,41],Am:[33,40],Gm:[31,38]};
  var lead=[],bassLine=[],guitar=[],drums=[],vocal=[];
  var cursor=0,partByBar=[];
  sections.forEach(function(section){for(var i=0;i<section.length;i++)partByBar[cursor++]={key:section.key,local:i};});
  chords.forEach(function(pair,index){
    var chord=pair[0],notes=tones[chord],part=partByBar[index],quiet=part.key==='intro'&&part.local<2,strong=part.key==='reff2'||part.key==='reff3'||part.key==='outro';
    var pattern=quiet?[[0,4,notes[0]],[8,4,notes[2]]]:[[0,3,notes[0]],[4,3,notes[1]],[8,3,notes[2]],[12,3,notes[3]]];
    if(part.key==='interlude'||part.key==='intro')pattern=[[0,2,notes[0]],[2,2,notes[1]],[4,3,notes[2]],[8,2,notes[3]],[10,2,notes[2]],[12,4,notes[1]]];
    lead.push(pattern);
    bassLine.push(quiet?[]:[[0,4,bass[chord][0]],[8,3,bass[chord][1]],[12,4,bass[chord][0]]]);
    guitar.push(quiet?[0,8]:(strong?[0,2,4,6,8,10,12,14]:[0,4,6,8,12,14]));
    drums.push(quiet?{h:[0,4,8,12],s:[],k:[0,8],c:[],t:[]}:{
      h:strong?[0,2,4,6,8,10,12,14]:[0,2,4,6,8,10,12,14],
      s:[4,12],k:strong?[0,6,8,10,14]:[0,8,14],
      c:(part.local===0||part.key==='outro')?[0]:[],
      t:(part.local===partByBar.filter(function(x){return x.key===part.key;}).length-1)?[13,14,15]:[]
    });
    vocal.push([]);
  });
  window.KC_JAKARTA_TRANSCRIPTION={meta:{bpm:114,start:3.3,grid:'1/16',bars:106},sections:sections,chords:chords,lead:lead,bass:bassLine,guitar:guitar,drums:drums,vocal:vocal};
})();

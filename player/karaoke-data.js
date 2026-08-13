(function(global){
  'use strict';
  var DEFAULT_BASE='https://raw.githubusercontent.com/mulyadibagan/KompilasiChord_KaraokeAkustik/master/';
  function youtubeId(value){
    try{
      var u=new URL(value),id=u.hostname.indexOf('youtu.be')>=0?u.pathname.slice(1):u.searchParams.get('v');
      return (id||value).split(/[/?&]/)[0];
    }catch(e){return String(value||'').trim()}
  }
  function Store(base){this.base=(base||DEFAULT_BASE).replace(/\/?$/,'/')}
  Store.prototype.json=async function(path){
    var r=await fetch(this.base+path,{cache:'no-cache'});
    if(!r.ok)throw new Error('Data karaoke tidak tersedia ('+r.status+').');
    return r.json();
  };
  Store.prototype.catalog=function(){return this.json('catalog.json')};
  Store.prototype.find=async function(linkOrId){
    var id=youtubeId(linkOrId),catalog=await this.catalog();
    var song=(catalog.songs||[]).find(function(x){return x.youtubeId===id});
    if(!song)return null;
    var data=await this.json(song.timeline);
    return {catalog:song,data:data};
  };
  Store.youtubeId=youtubeId;
  global.KCKaraokeStore=Store;
})(window);
